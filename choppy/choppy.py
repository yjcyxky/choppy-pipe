import argparse
import sys
import os
import re
import csv
import shutil
import logging
import getpass
import json
import zipfile
import uuid
import pprint
import time
import pytz
import datetime
from subprocess import CalledProcessError, check_output, PIPE, Popen, call as subprocess_call
from . import config as c
from .utils import (parse_samples, render_app, write, kv_list_to_dict, submit_workflow, \
                    install_app, uninstall_app, check_identifier)
from .cromwell import Cromwell, print_log_exit
from .monitor import Monitor
from .validator import Validator

__author__ = "Jingcheng Yang"
__copyright__ = "Copyright 2018, The Genius Medicine Consortium."
__credits__ = ["Jun Shang", "Yechao Huang"]
__license__ = "GPL"
__version__ = "0.2.0"
__maintainer__ = "Jingcheng Yang"
__email__ = "yjcyxky@163.com"
__status__ = "Production"


logger = logging.getLogger('choppy')

def set_logger(log_name, subdir="project_logs"):
    global logger
    # Logging setup
    logger.setLevel(c.log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # create file handler which logs even debug messages
    if subdir:
        project_logs = os.path.join(c.log_dir, "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(log_name))
    else:
        logfile = os.path.join(c.log_dir, '{}_{}_choppy.log'.format(str(time.strftime("%Y-%m-%d")), log_name))
    fh = logging.FileHandler(logfile)
    fh.setLevel(c.log_level)
    fh.setFormatter(formatter)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def is_valid_oss_link(path):
    matchObj = re.match(r'^oss://[a-zA-Z0-9\-_\./]+$', path, re.M|re.I)
    if matchObj:
        return path
    else:
        raise argparse.ArgumentTypeError("%s is not a valid oss link.\n" % path)


def check_dir(path, skip=None):
    if not os.path.isdir(path):
        os.makedirs(path)
    elif not skip:
        raise Exception("%s is not empty" % path)


def is_valid_app(path):
    if not os.path.exists(path):
        raise Exception("%s is not a valid app.\n" % os.path.basename(path))


def is_valid(path):
    """
    Integrates with ArgParse to validate a file path.
    :param path: Path to a file.
    :return: The path if it exists, otherwise raises an error.
    """
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(("{} is not a valid file path.\n".format(path)))
    else:
        return path


def is_valid_zip(path):
    """
    Integrates with argparse to validate a file path and verify that the file is a zip file.
    :param path: Path to a file.
    :return: The path if it exists and is a zip file, otherwise raises an error.
    """
    is_valid(path)
    if not zipfile.is_zipfile(path):
        e = "{} is not a valid zip file.\n".format(path)
        logger.error(e)
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def call_submit(args):
    """
    Optionally validates inputs and starts a workflow on the Cromwell execution engine if validation passes. Validator
    returns an empty list if valid, otherwise, a list of errors discovered.
    :param args: submit subparser arguments.
    :return: JSON response with Cromwell workflow ID.
    """
    if args.validate:
        call_validate(args)

    #prep labels and add user
    labels_dict = kv_list_to_dict(args.label) if kv_list_to_dict(args.label) != None else {}
    labels_dict['username'] = args.username
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    result = cromwell.jstart_workflow(wdl_file=args.wdl, json_file=args.json, dependencies=args.dependencies,
                                      disable_caching=args.disable_caching,
                                      extra_options=kv_list_to_dict(args.extra_options),
                                      custom_labels=labels_dict)

    print("-------------Cromwell Links-------------")
    links = get_cromwell_links(args.server, result['id'], cromwell.port)
    print(links['metadata'])
    print(links['timing'])
    logger.info("Metadata:{}".format(links['metadata']))
    logger.info("Timing Graph:{}".format(links['timing']))

    args.workflow_id = result['id']

    if args.monitor:
        # this sleep is to allow job to get started in Cromwell before labeling or monitoring.
        # Probably better ways to do this but for now this works.
        time.sleep(5)

        print ("These will also be e-mailed to you when the workflow completes.")
        retry = 4
        while retry != 0:
            try:
                call_monitor(args)
                retry = 0
            except KeyError as e:
                logger.debug(e)
                retry = retry - 1
    return result


def call_query(args):
    """
    Get various types of data on a particular workflow ID.
    :param args:  query subparser arguments.
    :return: A list of json responses based on queries selected by the user.
    """
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    responses = []
    if args.workflow_id == None or args.workflow_id == "None" and not args.label:
        return call_list(args)
    if args.label:
        logger.info("Label query requested.")
        labeled = cromwell.query_labels(labels=kv_list_to_dict(args.label))
        return labeled
    if args.status:
        logger.info("Status requested.")
        status = cromwell.query_status(args.workflow_id)
        responses.append(status)
    if args.metadata:
        logger.info("Metadata requested.")
        metadata = cromwell.query_metadata(args.workflow_id)
        responses.append(metadata)
    if args.logs:
        logger.info("Logs requested.")
        logs = cromwell.query_logs(args.workflow_id)
        responses.append(logs)
    logger.debug("Query Results:\n" + str(responses))
    return responses


def call_validate(args):
    """
    Calls the Validator to validate input json. Exits with feedback to user regarding errors in json or reports no
    errors found.
    :param args: validation subparser arguments.
    :return:
    """
    logger.info("Validation requested.")
    validator = Validator(wdl=args.wdl, json=args.json)
    result = validator.validate_json()
    if len(result) != 0:
        e = "{} input file contains the following errors:\n{}".format(args.json, "\n".join(result))
        # This will also print to stdout so no need for a print statement
        logger.critical(e)
        sys.exit(1)
    else:
        s = 'No errors found in {}'.format(args.wdl)
        print(s)
        logger.info(s)


def call_abort(args):
    """
    Abort a workflow with a given workflow id.
    :param args: abort subparser args.
    :return: JSON containing abort response.
    """
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    logger.info("Abort requested")
    return cromwell.stop_workflow(workflow_id=args.workflow_id)


def call_monitor(args):
    """
    Calls Monitoring to report to user the status of their workflow at regular intervals.
    :param args: 'monitor' subparser arguments.
    :return:
    """
    logger.info("Monitoring requested")

    print("-------------Monitoring Workflow-------------")
    try:
        if args.daemon:
            m = Monitor(host=args.server, user="*", no_notify=args.no_notify, verbose=args.verbose,
                        interval=args.interval)
            m.run()
        else:
            m = Monitor(host=args.server, user=args.username, no_notify=args.no_notify, verbose=args.verbose,
                        interval=args.interval)
            if args.workflow_id:
                m.monitor_workflow(args.workflow_id)
            else:
                m.monitor_user_workflows()
    except Exception as e:
        print_log_exit(msg=str(e), sys_exit=False, ple_logger=logger)


def call_restart(args):
    """
    Call cromwell restart to restart a failed workflow.
    :param args: restart subparser arguments.
    :return:
    """
    logger.info("Restart requested")
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    result = cromwell.restart_workflow(workflow_id=args.workflow_id, disable_caching=args.disable_caching)

    if result is not None and "id" in result:
        msg = "Workflow restarted successfully; new workflow-id: " + str(result['id'])
        print(msg)
        logger.info(msg)
    else:
        msg = "Workflow was not restarted successfully; server response: " + str(result)
        print(msg)
        logger.critical(msg)


def get_cromwell_links(server, workflow_id, port):
    """
    Get metadata and timing graph URLs.
    :param server: cromwell host
    :param workflow_id: UUID for workflow
    :param port: port for cromwell server of interest
    :return: Dictionary containing useful links
    """
    return {'metadata': 'http://{}:{}/api/workflows/v1/{}/metadata'.format(server, port, workflow_id),
            'timing': 'http://{}:{}/api/workflows/v1/{}/timing'.format(server, port, workflow_id)}


def call_explain(args):
    logger.info("Explain requested")
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    (result, additional_res, stdout_res) = cromwell.explain_workflow(workflow_id=args.workflow_id,
                                                                     include_inputs=args.input)

    def my_safe_repr(object, context, maxlevels, level):
        typ = pprint._type(object)
        if typ is unicode:
            object = str(object)
        return pprint._safe_repr(object, context, maxlevels, level)

    printer = pprint.PrettyPrinter()
    printer.format = my_safe_repr
    if result is not None:
        print("-------------Workflow Status-------------")
        printer.pprint(result)

        if len(additional_res) > 0:
            print("-------------Additional Parameters-------------")
            printer.pprint(additional_res)

        if len(stdout_res) > 0:
            for log in stdout_res["failed_jobs"]:
                print("-------------Failed Stdout-------------")
                print ("Shard: "+ log["stdout"]["label"])
                print (log["stdout"]["name"] + ":")
                print (log["stdout"]["log"])
                print ("-------------Failed Stderr-------------")
                print ("Shard: " + log["stderr"]["label"])
                print (log["stderr"]["name"] + ":")
                print (log["stderr"]["log"])

        print("-------------Cromwell Links-------------")
        links = get_cromwell_links(args.server, result['id'], cromwell.port)
        print (links['metadata'])
        print (links['timing'])

    else:
        print("Workflow not found.")

    args.monitor = True
    return None


def call_list(args):
    username = "*" if args.all else args.username
    m = Monitor(host=args.server, user=username, no_notify=True, verbose=True,
                interval=None)

    def get_iso_date(dt):
        tz = pytz.timezone("US/Eastern")
        return tz.localize(dt).isoformat()

    def process_job(job):
        links = get_cromwell_links(args.server, job['id'], m.cromwell.port)
        job['metadata'] = links['metadata']
        job['timing'] = links['timing']
        return job

    def my_safe_repr(object, context, maxlevels, level):
        typ = pprint._type(object)
        if typ is unicode:
            object = str(object)
        return pprint._safe_repr(object, context, maxlevels, level)

    start_date_str = get_iso_date(datetime.datetime.now() - datetime.timedelta(days=int(args.days)))
    q = m.get_user_workflows(raw=True, start_time=start_date_str)
    try:
        result = q["results"]
        if args.filter:
            result = [res for res in result if res['status'] in args.filter]
        result = map(lambda j: process_job(j), result)
        printer = pprint.PrettyPrinter()
        printer.format = my_safe_repr
        printer.pprint(result)
        args.monitor = True
        return result
    except KeyError as e:
        logger.critical('KeyError: Unable to find key {}'.format(e))


def call_label(args):
    """
    Apply labels to a workflow that currently exists in the database.
    :param args: label subparser arguments
    :return:
    """
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    labels_dict = kv_list_to_dict(args.label)
    response = cromwell.label_workflow(workflow_id=args.workflow_id, labels=labels_dict)
    if response.status_code == 200:
        print("Labels successfully applied:\n{}".format(response.content))
    else:
        logger.critical("Unable to apply specified labels:\n{}".format(response.content))


def call_log(args):
    """
    Get workflow logs via cromwell API.
    :param args: log subparser arguments.
    :return:
    """
    matchedWorkflowId = re.match(r'^[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}$', 
                                 args.workflow_id, re.M|re.I)

    if matchedWorkflowId:
        host, port, auth = c.get_conn_info(args.server)
        cromwell = Cromwell(host, port, auth)
        res = cromwell.get('logs', args.workflow_id)
        print(json.dumps(res["calls"], indent=2, sort_keys=True))

        command = ""

        # for each task, extract the command used
        for key in res["calls"]:
            stderr = res["calls"][key][0]["stderr"]
            script = "/".join(stderr.split("/")[:-1]) + "/script"
            fuuid = uuid.uuid1()
            dest_script = "/tmp/%s" % fuuid
            run_copy_files(script, dest_script)

            dest_script = os.path.join(dest_script, "script")
            with open(dest_script, 'r') as f:
                command_log = f.read()

            command = command + key + ":\n\n"
            command = command + command_log + "\n\n"

        print(command)  # print to stdout
        return None
    else:
        project_logs = os.path.join(c.log_dir, "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(args.workflow_id))
        if os.path.isfile(logfile):
            with open(logfile, 'r') as f:
                print(f.read())
        else:
            print("No such project: %s" % args.workflow_id)


def call_cat_remote_file(args):
    remote_file = args.oss_link
    fuuid = uuid.uuid1()
    dest_file = "/tmp/%s" % fuuid
    run_copy_files(remote_file, dest_file, recursive=False)

    if os.path.isfile(dest_file):
        with open(dest_file, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                print(line)
    else:
        print("Not a file.")


def call_email(args):
    """
    MVP pass-through function for testing desirability of a call_email feature. If users want a full-fledged function
    we can rework this.
    :param args: email subparser args.
    :return:
    """
    args.verbose = False
    args.no_notify = False
    args.interval = 0
    call_monitor(args)


def call_list_apps(args):
    if os.path.isdir(c.app_dir):
        files = os.listdir(c.app_dir)
        print(files)
    else:
        raise Exception("choppy.conf.general.app_dir is wrong.")


def run_batch(project_name, app_dir, samples, label, server='localhost', 
              username=None, dry_run=False):
    is_valid_app(app_dir)
    working_dir = os.getcwd()
    project_path = os.path.join(working_dir, project_name)
    check_dir(project_path)

    samples_data = parse_samples(samples)
    successed_samples = []
    failed_samples = []

    for sample in samples_data:
        if 'sample_id' not in sample.keys():
            raise Exception("Your samples file must contain sample_id column.")
        else:
            # make project_name/sample_id directory
            sample_path = os.path.join(project_path, sample.get('sample_id'))
            check_dir(sample_path)

            sample['project_name'] = project_name

            inputs = render_app(app_dir, 'inputs', sample)
            write(sample_path, 'inputs', inputs)
            inputs_path = os.path.join(sample_path, 'inputs')

            wdl = render_app(app_dir, 'workflow.wdl', sample)
            write(sample_path, 'workflow.wdl', wdl)
            wdl_path = os.path.join(sample_path, 'workflow.wdl')

            src_dependencies = os.path.join(app_dir, 'tasks.zip')
            dest_dependencies = os.path.join(sample_path, 'tasks.zip')
            shutil.copyfile(src_dependencies, dest_dependencies)
            
            if not dry_run:
                try:
                    result = submit_workflow(wdl_path, inputs_path, dest_dependencies, label, 
                                             username=username, server=server)

                    links = get_cromwell_links(server, result['id'], result.get('port'))

                    sample['metadata_link'] = links['metadata']
                    sample['timing_link'] = links['timing']
                    sample['workflow_id'] = result['id']
                    logger.info("Sample ID: %s, Workflow ID: %s" % (sample.get('sample_id'), result['id']))
                except Exception as e:
                    logger.error("Sample ID: %s, %s" % (sample.get('sample_id'), str(e)))
                    failed_samples.append(sample)
                    continue

            successed_samples.append(sample)

    submitted_file_path =  os.path.join(project_path, 'submitted.csv')
    failed_file_path = os.path.join(project_path, 'failed.csv')
    if len(successed_samples) > 0:
        keys = successed_samples[0].keys()
        with open(submitted_file_path, 'wb') as fsuccess:
            dict_writer = csv.DictWriter(fsuccess, keys)
            dict_writer.writeheader()
            dict_writer.writerows(successed_samples)
    
    if len(failed_samples) > 0:
        keys = failed_samples[0].keys()
        with open(failed_file_path, 'wb') as ffail:
            dict_writer = csv.DictWriter(ffail, keys)
            dict_writer.writeheader()
            dict_writer.writerows(failed_samples)
    
    if len(successed_samples) > 0:
        if len(failed_samples) == 0:
            logger.info("Successed: %s, %s" % (len(successed_samples), submitted_file_path))
        else:
            logger.info("Successed: %s, %s" % (len(successed_samples), submitted_file_path))
            logger.error("Failed: %s, %s" % (len(failed_samples), failed_file_path))
    else:
        logger.error("Failed: %s, %s" % (len(failed_samples), failed_file_path))


def call_batch(args):
    app_dir = os.path.join(c.app_dir, args.app_name)
    project_name = args.project_name
    if not check_identifier(project_name):
        raise Exception("Not valid project_name.")

    samples = args.samples
    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username
    run_batch(project_name, app_dir, samples, label, server, username, dry_run)


def call_testapp(args):
    # app_dir is not same with call_batch.
    app_dir = args.app_dir
    project_name = args.project_name
    if not check_identifier(project_name):
        raise Exception("Not valid project_name.")

    samples = args.samples
    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username
    run_batch(project_name, app_dir, samples, label, server, username, dry_run)


def call_installapp(args):
    app_zip_file = args.zip_file
    install_app(c.app_dir, app_zip_file)


def call_uninstallapp(args):
    app_dir = os.path.join(c.app_dir, args.app_name)
    if not os.path.isdir(app_dir):
        raise Exception("The %s doesn't exist" % args.app_name)

    uninstall_app(app_dir)


def call_list_files(args):
    oss_link = args.oss_link
    try:
        shell_cmd = [c.oss_bin, "ls", oss_link, "-s", "-d", "-i", c.access_key, "-k", c.access_secret]
        output = check_output(shell_cmd).splitlines()
        if len(output) > 2:
            for i in output[1:-2]:
                print("%s" % i)
    except CalledProcessError:
        print("access_key/access_secret or oss_link is not valid.")


def run_copy_files(first_path, second_path, include=None, exclude=None, recursive=True):
    output_dir = os.path.join(c.log_dir, 'oss_outputs')
    checkpoint_dir = os.path.join(c.log_dir, 'oss_checkpoint')

    try:
        shell_cmd = [c.oss_bin, "cp", "-u", "-i", c.access_key, "-k", c.access_secret, 
                     "--output-dir=%s" % output_dir, "--checkpoint-dir=%s" % checkpoint_dir,
                     "-e", c.endpoint]
        if include:
            shell_cmd.extend(["--include", include])

        if exclude:
            shell_cmd.extend(["--exclude", exclude])

        if recursive:
            shell_cmd.extend(["-r"])
        
        shell_cmd.extend([first_path, second_path])
        subprocess_call(shell_cmd)
    except CalledProcessError as e:
        print(e)
        print("access_key/access_secret or oss_link is not valid.")


def call_upload_files(args):
    oss_link = args.oss_link
    local_path = args.local_path
    include = args.include
    exclude = args.exclude
    run_copy_files(local_path, oss_link, include, exclude)


def call_download_files(args):
    oss_link = args.oss_link
    local_path = args.local_path
    include = args.include
    exclude = args.exclude
    run_copy_files(oss_link, local_path, include, exclude)


def call_cp_remote_files(args):
    src_oss_link = args.src_oss_link
    dest_oss_link = args.dest_oss_link
    include = args.include
    exclude = args.exclude
    run_copy_files(src_oss_link, dest_oss_link, include, exclude)    


parser = argparse.ArgumentParser(
    description='Description: A tool for executing and monitoring WDLs to Cromwell instances.',
    usage='choppy <positional argument> [<args>]',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--silent', action='store_true', default=False, help="Silent mode.")

sub = parser.add_subparsers()
restart = sub.add_parser(name='restart',
                         description='Restart a submitted workflow.',
                         usage='choppy restart <workflow id>',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
restart.add_argument('workflow_id', action='store', help='workflow id of workflow to restart.')
restart.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                     help='Choose a cromwell server from {}'.format(c.servers))
restart.add_argument('-M', '--monitor', action='store_true', default=True, help=argparse.SUPPRESS)
restart.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
restart.set_defaults(func=call_restart)

explain = sub.add_parser(name='explain',
                         description='Explain the status of a workflow.',
                         usage='choppy explain <workflowid>',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
explain.add_argument('workflow_id', action='store', help='workflow id of workflow to abort.')
explain.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                     help='Choose a cromwell server from {}'.format(c.servers))
explain.add_argument('-I', '--input', action='store_true', default=False, help=argparse.SUPPRESS)
explain.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
explain.set_defaults(func=call_explain)

log = sub.add_parser(name='log',
                     description='Print the log of a workflow or a project.',
                     usage='choppy log <workflow_id>/<project_name>',
                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
log.add_argument('workflow_id', action='store', help='workflow_id or project_name')
log.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                 help='Choose a cromwell server from {}'.format(c.servers))
log.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
log.set_defaults(func=call_log)

abort = sub.add_parser(name='abort',
                       description='Abort a submitted workflow.',
                       usage='choppy abort <workflow id>',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
abort.add_argument('workflow_id', action='store', help='workflow id of workflow to abort.')
abort.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                   help='Choose a cromwell server from {}'.format(c.servers))
abort.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
abort.set_defaults(func=call_abort)

monitor = sub.add_parser(name='monitor',
                         description='Monitor a particular workflow and notify user via e-mail upon completion. If a'
                                     'workflow ID is not provided, user-level monitoring is assumed.',
                         usage='choppy monitor <workflow_id> [<args>]',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
monitor.add_argument('workflow_id', action='store', nargs='?',
                     help='workflow id for workflow to monitor. Do not specify if user-level monitoring is desired.')
monitor.add_argument('-u', '--username', action='store', default=getpass.getuser(),
                     help='Owner of workflows to monitor.')
monitor.add_argument('-i', '--interval', action='store', default=30, type=int,
                     help='Amount of time in seconds to elapse between status checks.')
monitor.add_argument('-V', '--verbose', action='store_true', default=False,
                     help='When selected, choppy will write the current status to STDOUT until completion.')
monitor.add_argument('-n', '--no_notify', action='store_true', default=False,
                     help='When selected, disable choppy e-mail notification of workflow completion.')
monitor.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                     help='Choose a cromwell server from {}'.format(c.servers))
monitor.add_argument('-M', '--monitor', action='store_true', default=True, help=argparse.SUPPRESS)
monitor.add_argument('-D', '--daemon', action='store_true', default=False,
                     help="Specify if this is a daemon for all users.")
monitor.set_defaults(func=call_monitor)

query = sub.add_parser(name='query',
                       description='Query cromwell for information on the submitted workflow.',
                       usage='choppy query <workflow id> [<args>]',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
query.add_argument('workflow_id', nargs='?', default="None", help='workflow id for workflow execution of interest.')
query.add_argument('-s', '--status', action='store_true', default=False, help='Print status for workflow to stdout')
query.add_argument('-m', '--metadata', action='store_true', default=False, help='Print metadata for workflow to stdout')
query.add_argument('-l', '--logs', action='store_true', default=False, help='Print logs for workflow to stdout')
query.add_argument('-u', '--username', action='store', default=getpass.getuser(), help='Owner of workflows to query.')
query.add_argument('-L', '--label', action='append', help='Query status of all workflows with specific label(s).')
query.add_argument('-d', '--days', action='store', default=7, help='Last n days to query.')
query.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                   help='Choose a cromwell server from {}'.format(c.servers))
query.add_argument('-f', '--filter', action='append', type=str, choices=c.run_states + c.terminal_states,
                   help='Filter by a workflow status from those listed above. May be specified more than once.')
query.add_argument('-a', '--all', action='store_true', default=False, help='Query for all users.')
query.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
query.set_defaults(func=call_query)

submit = sub.add_parser(name='submit',
                     description='Submit a WDL & JSON for execution on a Cromwell VM.',
                     usage='choppy submit <wdl file> <json file> [<args>]',
                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
submit.add_argument('wdl', action='store', type=is_valid, help='Path to the WDL to be executed.')
submit.add_argument('json', action='store', type=is_valid, help='Path the json inputs file.')
submit.add_argument('-v', '--validate', action='store_true', default=False,
                    help='Validate WDL inputs in json file.')
submit.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
submit.add_argument('-m', '--monitor', action='store_true', default=False,
                    help='Monitor the workflow and receive an e-mail notification when it terminates.')
submit.add_argument('-i', '--interval', action='store', default=30, type=int,
                    help='If --monitor is selected, the amount of time in seconds to elapse between status checks.')
submit.add_argument('-o', '--extra_options', action='append',
                    help='Additional workflow options to pass to Cromwell. Specify as k:v pairs. May be specified multiple'
                         + 'times for multiple options. See https://github.com/broadinstitute/cromwell#workflow-options' +
                         'for available options.')
submit.add_argument('-V', '--verbose', action='store_true', default=False,
                    help='If selected, choppy will write the current status to STDOUT until completion while monitoring.')
submit.add_argument('-n', '--no_notify', action='store_true', default=False,
                    help='When selected, disable choppy e-mail notification of workflow completion.')
submit.add_argument('-d', '--dependencies', action='store', default=None, type=is_valid_zip,
                    help='A zip file containing one or more WDL files that the main WDL imports.')
submit.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
submit.add_argument('-S', '--server', action='store', type=str, choices=c.servers, default='localhost',
                    help='Choose a cromwell server from {}'.format(c.servers))
submit.add_argument('-u', '--username', action='store', default=getpass.getuser(), help=argparse.SUPPRESS)
submit.add_argument('-w', '--workflow_id', help=argparse.SUPPRESS)
submit.add_argument('-x', '--daemon', action='store_true', default=False, help=argparse.SUPPRESS)
submit.set_defaults(func=call_submit)

validate = sub.add_parser(name='validate',
                          description='Validate (but do not run) a json for a specific WDL file.',
                          usage='choppy validate <wdl_file> <json_file>',
                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
validate.add_argument('wdl', action='store', type=is_valid, help='Path to the WDL associated with the json file.')
validate.add_argument('json', action='store', type=is_valid, help='Path the json inputs file to validate.')
validate.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
validate.set_defaults(func=call_validate)

label = sub.add_parser(name='label',
                       description='Label a specific workflow with one or more key/value pairs.',
                       usage='choppy label <workflow_id> [<args>]',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
label.add_argument('workflow_id', nargs='?', default="None", help='workflow id for workflow to label.')
label.add_argument('-S', '--server', action='store', type=str, choices=c.servers, default="localhost",
                   help='Choose a cromwell server from {}'.format(c.servers))
label.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
label.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
label.set_defaults(func=call_label)

email = sub.add_parser(name ='email',
                       description='Email data to user regarding a workflow.',
                       usage='choppy label <workflow_id> [<args>]',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
email.add_argument('workflow_id', nargs='?', default="None", help='workflow id for workflow to label.')
email.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                   help='Choose a cromwell server from {}'.format(c.servers))
email.add_argument('-u', '--username', action='store', default=getpass.getuser(), help='username of user to e-mail to')
email.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
email.add_argument('-D', '--daemon', action='store_true', default=False,
                   help=argparse.SUPPRESS)
email.set_defaults(func=call_email)

batch = sub.add_parser(name="batch",
                       description="Submit batch jobs for execution on a Cromwell VM.",
                       usage="choppy batch <app_name> <samples>",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
batch.add_argument('app_name', action='store', help='The app name for your project.')
batch.add_argument('samples', action='store', type=is_valid, help='Path the samples file to validate.')
batch.add_argument('--project-name', action='store', required=True, help='Your project name.')
batch.add_argument('--dry-run', action='store_true', default=False, help='Generate all workflow but skipping running.')
batch.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
batch.add_argument('-S', '--server', action='store', default='localhost', type=str, help='Choose a cromwell server.')
batch.add_argument('-u', '--username', action='store', default=getpass.getuser(), help=argparse.SUPPRESS)
batch.set_defaults(func=call_batch)

testapp = sub.add_parser(name="testapp",
                       description="Test an app.",
                       usage="choppy testapp <app_dir> <samples>",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
testapp.add_argument('app_dir', action='store', type=is_valid, help='The app path for your project.')
testapp.add_argument('samples', action='store', type=is_valid, help='Path the samples file to validate.')
testapp.add_argument('--project-name', action='store', required=True, help='Your project name.')
testapp.set_defaults(func=call_testapp)

installapp = sub.add_parser(name="install",
                       description="Install an app.",
                       usage="choppy install <zip_file>",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
installapp.add_argument('zip_file', action='store', type=is_valid_zip, help='The app zip file.')
installapp.set_defaults(func=call_installapp)

uninstallapp = sub.add_parser(name="uninstall",
                       description="Uninstall an app.",
                       usage="choppy uninstall app_name",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
uninstallapp.add_argument('app_name', action='store', help='App name.')
uninstallapp.set_defaults(func=call_uninstallapp)

wdllist = sub.add_parser(name="apps",
                         description="List all apps that is supported by choppy.",
                         usage="choppy apps",
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
wdllist.set_defaults(func=call_list_apps)

listfiles = sub.add_parser(name="listfiles",
                           description="List all files where are in the specified bucket.",
                           usage="choppy listfiles <oss_link>",
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
listfiles.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
listfiles.set_defaults(func=call_list_files)

upload_files = sub.add_parser(name="upload",
                           description="Upload file/directory to the specified bucket.",
                           usage="choppy upload <local_path> <oss_link>",
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
upload_files.add_argument('local_path', action='store', type=is_valid, help='local_path.')
upload_files.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
upload_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
upload_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
upload_files.set_defaults(func=call_upload_files)

download_files = sub.add_parser(name="download",
                           description="Download file/directory to the specified bucket.",
                           usage="choppy download <oss_link> <local_path>",
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
download_files.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
download_files.add_argument('local_path', action='store', type=is_valid, help='local_path.')
download_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
download_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
download_files.set_defaults(func=call_download_files)

copy_files = sub.add_parser(name="copy",
                           description="Copy file/directory from an oss path to another.",
                           usage="choppy copy <src_oss_link> <dest_oss_link>",
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
copy_files.add_argument('src_oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
copy_files.add_argument('dest_oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
copy_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
copy_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
copy_files.set_defaults(func=call_cp_remote_files)

cat_file = sub.add_parser(name="catlog",
                          description="Cat log file.",
                          usage="choppy cat <oss_link>",
                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cat_file.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
cat_file.set_defaults(func=call_cat_remote_file)


def main():
    args = parser.parse_args()
    user = getpass.getuser()
    # Get user's username so we can tag workflows and logs for them.
    if hasattr(args, 'project_name'):
        check_identifier(args.project_name)
        set_logger(args.project_name)
    else:
        set_logger(user, subdir=None)

    if not args.silent:
        logger.debug("\n-------------New Choppy Execution by {}-------------".format(user))
        logger.debug("Parameters chosen: {}".format(vars(args)))

    result = args.func(args)

    if not args.silent:
        logger.debug("Result: {}".format(result))
        # If we aren't using persistent monitoring, we'll give the user a basically formated json dump to stdout.
        try:
            if not args.monitor and result:
                print(json.dumps(result, indent=4))
        except AttributeError:
            pass
        logger.debug("\n-------------End Choppy Execution by {}-------------\n\n".format(user))


