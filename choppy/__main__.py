#!/usr/bin/env python
# -*- coding:utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
Choppy is a tool for submitting workflows via command-line to the cromwell execution engine servers.
"""
from __future__ import unicode_literals, absolute_import
import argcomplete
import argparse
import sys
import os
import re
import shutil
import logging
import json
import uuid
import pprint
import time
import pytz
import datetime
import getpass
import coloredlogs
import choppy.config as c
from choppy import exit_code
from choppy.app_utils import (kv_list_to_dict, install_app, uninstall_app,
                              parse_json, get_header, parse_app_name, listapps,
                              render_readme, generate_dependencies_zip,
                              AppDefaultVar, is_valid_app)
from choppy.check_utils import (is_valid_label, is_valid_project_name, is_valid,
                                is_valid_oss_link, check_dir, check_identifier,
                                is_valid_zip_or_dir, is_valid_app_name,
                                get_all_variables, check_variables, is_valid_url)
from choppy.version import get_version
from choppy.docker_mgmt import get_parser, get_default_image, get_base_images
from choppy.report_mgmt import get_mode
from choppy.utils import (get_copyright, BashColors, ReportTheme, print_obj,
                          clean_temp_dir)
from choppy.exceptions import NotFoundApp, WrongAppDir

__author__ = "Jingcheng Yang"
__copyright__ = "Copyright 2018, The Genius Medicine Consortium."
__credits__ = ["Jun Shang", "Yechao Huang"]
__license__ = "GPL"
__version__ = get_version()
__maintainer__ = "Jingcheng Yang"
__email__ = "yjcyxky@163.com"
__status__ = "Production"


logger = logging.getLogger('choppy')


def set_logger(log_name, loglevel, handler='stream', subdir="project_logs"):
    if subdir:
        project_logs = os.path.join(c.log_dir, "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(log_name))
    else:
        logfile = os.path.join(c.log_dir, '{}_{}_choppy.log'.format(str(time.strftime("%Y-%m-%d")), log_name))

    if handler != 'stream':
        fhandler = logging.FileHandler(logfile)
    else:
        fhandler = None

    if loglevel == logging.DEBUG:
        fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        coloredlogs.install(level=loglevel, fmt=fmt, stream=fhandler)
    else:
        fmt = '%(message)s'
        coloredlogs.install(level=loglevel, fmt=fmt, stream=fhandler)


def call_submit(args):
    """
    Optionally validates inputs and starts a workflow on the Cromwell execution engine if validation passes. Validator
    returns an empty list if valid, otherwise, a list of errors discovered.

    :param args: submit subparser arguments.
    :return: JSON response with Cromwell workflow ID.
    """
    from choppy.json_checker import check_json
    from choppy.cromwell import Cromwell

    dependencies = args.dependencies
    if os.path.isdir(dependencies):
        dependencies = generate_dependencies_zip(dependencies)

    if args.validate:
        call_validate(args)

    # prep labels and add user
    labels_dict = kv_list_to_dict(args.label) if kv_list_to_dict(args.label) is not None else {}
    labels_dict['username'] = args.username.lower()
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    check_json(json_file=args.json)
    result = cromwell.jstart_workflow(wdl_file=args.wdl, json_file=args.json,
                                      dependencies=dependencies,
                                      disable_caching=args.disable_caching,
                                      extra_options=kv_list_to_dict(args.extra_options),
                                      custom_labels=labels_dict)

    logger.info("-------------Cromwell Links-------------")
    links = get_cromwell_links(args.server, result['id'], cromwell.port)
    logger.info(links['metadata'])
    logger.info(links['timing'])

    args.workflow_id = result['id']
    logger.info('workflow_id: %s' % result['id'])

    if args.monitor:
        # this sleep is to allow job to get started in Cromwell before labeling or monitoring. # noqa
        # Probably better ways to do this but for now this works.
        time.sleep(5)

        logger.info("These will also be e-mailed to you when the workflow completes.")
        retry = 4
        while retry != 0:
            try:
                call_monitor(args)
                retry = 0
            except KeyError as e:
                logger.debug(e)
                retry = retry - 1


def call_query(args):
    """
    Get various types of data on a particular workflow ID.
    :param args:  query subparser arguments.
    :return: A list of json responses based on queries selected by the user.
    """
    from choppy.cromwell import Cromwell

    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    responses = []
    if args.workflow_id is None or args.workflow_id == "None" and not args.label:
        return call_list(args)
    if args.label:
        logger.debug("Label query requested.")
        labeled = cromwell.query_labels(labels=kv_list_to_dict(args.label))
        return labeled
    if args.status:
        logger.debug("Status requested.")
        status = cromwell.query_status(args.workflow_id)
        responses.append(status)
    if args.metadata:
        logger.debug("Metadata requested.")
        metadata = cromwell.query_metadata(args.workflow_id)
        responses.append(metadata)
    if args.logs:
        logger.debug("Logs requested.")
        logs = cromwell.query_logs(args.workflow_id)
        responses.append(logs)
    print_obj("\n%s\n" % json.dumps(parse_json(responses), indent=2, sort_keys=True))
    sys.stdout.flush()
    return responses


def call_validate(args):
    """
    Calls the Validator to validate input json. Exits with feedback to user regarding errors in json or reports no # noqa
    errors found.
    :param args: validation subparser arguments.
    :return:
    """
    from choppy.validator import Validator

    logger.info("Validation requested.")
    validator = Validator(wdl=args.wdl, json=args.json)
    result = validator.validate_json()
    if len(result) != 0:
        e = "{} input file contains the following errors:\n{}".format(args.json, "\n".join(result))
        # This will also print to stdout so no need for a print statement
        logger.critical(e)
        sys.exit(exit_code.VALIDATE_ERROR)
    else:
        s = 'No errors found in {}'.format(args.wdl)
        logger.info(s)


def call_abort(args):
    """
    Abort a workflow with a given workflow id.
    :param args: abort subparser args.
    :return: JSON containing abort response.
    """
    from choppy.cromwell import Cromwell

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
    from choppy.cromwell import print_log_exit
    from choppy.monitor import Monitor

    logger.info("Monitoring requested")

    logger.info("-------------Monitoring Workflow-------------")
    try:
        if args.daemon:
            m = Monitor(host=args.server, user="*", no_notify=args.no_notify,
                        verbose=args.verbose, interval=args.interval)
            m.run()
        else:
            m = Monitor(host=args.server, user=args.username.lower(),
                        no_notify=args.no_notify, verbose=args.verbose,
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
    from choppy.cromwell import Cromwell

    logger.info("Restart requested")
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    result = cromwell.restart_workflow(workflow_id=args.workflow_id,
                                       disable_caching=args.disable_caching)

    if result is not None and "id" in result:
        msg = "Workflow restarted successfully; new workflow-id: " + str(result['id'])
        logger.info(msg)
    else:
        msg = "Workflow was not restarted successfully; server response: " + str(result)
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
    from choppy.cromwell import Cromwell

    logger.info("Explain requested")
    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    (result, additional_res, stdout_res) = cromwell.explain_workflow(workflow_id=args.workflow_id,
                                                                     include_inputs=args.input)

    def my_safe_repr(object, context, maxlevels, level):
        typ = pprint._type(object)
        try:
            if typ is unicode:  # noqa
                object = str(object)
        except Exception:
            pass
        return pprint._safe_repr(object, context, maxlevels, level)

    printer = pprint.PrettyPrinter()
    printer.format = my_safe_repr
    if result is not None:
        logger.info("-------------Workflow Status-------------")
        printer.pprint(result)

        if len(additional_res) > 0:
            print_obj("-------------Additional Parameters-------------")
            printer.pprint(additional_res)

        if len(stdout_res) > 0:
            for log in stdout_res["failed_jobs"]:
                print_obj("-------------Failed Stdout-------------")
                print_obj("Shard: " + log["stdout"]["label"])
                print_obj(log["stdout"]["name"] + ":")
                print_obj(log["stdout"]["log"])
                print_obj("-------------Failed Stderr-------------")
                print_obj("Shard: " + log["stderr"]["label"])
                print_obj(log["stderr"]["name"] + ":")
                print_obj(log["stderr"]["log"])

        logger.info("-------------Cromwell Links-------------")
        links = get_cromwell_links(args.server, result['id'], cromwell.port)
        logger.info(links['metadata'])
        logger.info(links['timing'])

    else:
        logger.warn("Workflow not found.")

    args.monitor = True
    return None


def call_list(args):
    from choppy.monitor import Monitor

    username = "*" if args.all else args.username.lower()
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
        try:
            if typ is unicode: # noqa: python2+
                object = str(object)
        except Exception:
            pass
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
        logger.info(result)
        return result
    except KeyError as e:
        logger.critical('KeyError: Unable to find key {}'.format(e))


def call_label(args):
    """
    Apply labels to a workflow that currently exists in the database.
    :param args: label subparser arguments
    :return:
    """
    from choppy.cromwell import Cromwell

    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    labels_dict = kv_list_to_dict(args.label)
    response = cromwell.label_workflow(workflow_id=args.workflow_id, labels=labels_dict)
    if response.status_code == 200:
        logger.info("Labels successfully applied:\n{}".format(response.content))
    else:
        logger.critical("Unable to apply specified labels:\n{}".format(response.content))


def call_log(args):
    """
    Get workflow logs via cromwell API.
    :param args: log subparser arguments.
    :return:
    """
    from choppy.cromwell import Cromwell
    from choppy.oss import run_copy_files

    matchedWorkflowId = re.match(r'^[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}$',
                                 args.workflow_id, re.M | re.I)

    if matchedWorkflowId:
        host, port, auth = c.get_conn_info(args.server)
        cromwell = Cromwell(host, port, auth)
        res = cromwell.get('logs', args.workflow_id)
        if res.get('calls'):
            logger.info("\n%s\n" % json.dumps(parse_json(res["calls"]), indent=2, sort_keys=True))

            logger.info("-------------Commands-------------")
            # for each task, extract the command used
            for key in res["calls"]:
                stderr = res["calls"][key][0]["stderr"]
                script = "/".join(stderr.split("/")[:-1]) + "/script"
                fuuid = uuid.uuid1()
                dest_script = "/tmp/choppy/%s/%s" % (fuuid, "script")
                run_copy_files(script, dest_script, recursive=False, silent=True)
                with open(dest_script, 'r') as f:
                    command_log = f.read()

                logger.info(key + ":")
                logger.info("\n" + command_log)

            return None
        else:
            metadata = cromwell.query_metadata(args.workflow_id)
            logger.info("\n%s\n" % json.dumps(parse_json(metadata), indent=2, sort_keys=True))
    else:
        project_logs = os.path.join(c.log_dir, "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(args.workflow_id))
        if os.path.isfile(logfile):
            with open(logfile, 'r') as f:
                logger.info(f.read())
        else:
            logger.warn("No such project: %s" % args.workflow_id)


def call_cat_remote_file(args):
    from choppy.oss import run_copy_files

    remote_file = args.oss_link
    fuuid = uuid.uuid1()
    dest_file = "/tmp/choppy/%s" % fuuid
    run_copy_files(remote_file, dest_file, recursive=False, silent=True)

    if os.path.isfile(dest_file):
        with open(dest_file, 'r') as f:
            for line in f.readlines():
                print_obj(line.strip('\n'))
                sys.stdout.flush()
    else:
        logger.warn("Not a file.")


def call_email(args):
    """
    MVP pass-through function for testing desirability of a call_email feature. # noqa
    If users want a full-fledged function we can rework this.
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
        logger.info(files)
    else:
        raise WrongAppDir("choppy.conf.general.app_dir is wrong.")


def call_batch(args):
    from choppy.workflow import run_batch

    app_dir = os.path.join(c.app_dir, args.app_name)
    project_name = args.project_name
    samples = args.samples
    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username.lower()
    force = args.force
    is_valid_app(app_dir)
    run_batch(project_name, app_dir, samples, label, server, username, dry_run, force)


def call_test(args):
    from choppy.workflow import run_batch

    app_dir = os.path.join(c.app_dir, args.app_name)
    project_name = args.project_name
    samples = os.path.join(c.app_dir, 'test', 'samples')
    if not os.path.isfile(samples):
        print_obj("No test file for %s" % args.app_name)
        sys.exit(exit_code.NO_TEST_FILE)

    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username.lower()
    force = args.force
    run_batch(project_name, app_dir, samples, label, server, username, dry_run, force)


def call_testapp(args):
    from choppy.workflow import run_batch

    # app_dir is not same with call_batch.
    app_dir = args.app_dir
    project_name = args.project_name
    samples = args.samples
    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username.lower()
    force = args.force
    run_batch(project_name, app_dir, samples, label, server, username, dry_run, force=force)


def call_installapp(args):
    choppy_app = args.choppy_app
    force = args.force

    # Try Parse Choppy App Name with Zip Format
    app_name_lst = [os.path.splitext(os.path.basename(choppy_app))[0], ]
    # Try Parse Choppy App Name with Git Repo Format
    parsed_dict = parse_app_name(choppy_app)
    if parsed_dict:
        app_name = parsed_dict.get('app_name')
        version = parsed_dict.get('version')
        app_name_lst.append('%s-%s' % (app_name, version))

    for app_name in app_name_lst:
        app_path = os.path.join(c.app_dir, app_name)
        # Overwrite If an app is installed.
        if os.path.exists(app_path):
            if force:
                shutil.rmtree(app_path, ignore_errors=True)
            else:
                print("%s is installed. If you want to reinstall, you can specify a --force flag." % app_name)
                sys.exit(exit_code.APP_IS_INSTALLED)

    install_app(c.app_dir, choppy_app)


def call_uninstallapp(args):
    app_dir = os.path.join(c.app_dir, args.app_name)
    if not os.path.isdir(app_dir):
        raise NotFoundApp("The %s doesn't exist" % args.app_name)

    uninstall_app(app_dir)


def call_list_files(args):
    from subprocess import CalledProcessError, check_output

    oss_link = args.oss_link
    recursive = args.recursive
    long_format = args.long_format
    try:
        shell_cmd = [c.oss_bin, "ls", oss_link, "-i", c.access_key, "-k",
                     c.access_secret, "-e", c.endpoint]

        if not long_format:
            if not recursive:
                shell_cmd.append('-d')
            else:
                shell_cmd.append('-s')

        output = check_output(shell_cmd).splitlines()

        if len(output) > 2:
            for i in output[0:-2]:
                print_obj("%s" % i)
                sys.stdout.flush()
    except CalledProcessError:
        logger.critical("access_key/access_secret or oss_link is not valid.")


def call_upload_files(args):
    from choppy.oss import run_copy_files

    oss_link = args.oss_link
    local_path = args.local_path
    include = args.include
    exclude = args.exclude
    run_copy_files(local_path, oss_link, include, exclude)


def call_download_files(args):
    from choppy.oss import run_copy_files

    oss_link = args.oss_link
    local_path = args.local_path
    include = args.include
    exclude = args.exclude
    run_copy_files(oss_link, local_path, include, exclude)


def call_cp_remote_files(args):
    from choppy.oss import run_copy_files

    src_oss_link = args.src_oss_link
    dest_oss_link = args.dest_oss_link
    include = args.include
    exclude = args.exclude
    run_copy_files(src_oss_link, dest_oss_link, include, exclude)


def call_search(args):
    from choppy.cromwell import Cromwell

    status = args.status
    project_name = args.project_name
    username = args.username.lower()
    short_format = args.short_format
    query_dict = {
        "label": [
            "username:%s" % username.lower()
        ],
        "name": project_name,
        "additionalQueryResultFields": ["labels"]
    }

    if status:
        query_dict.update({"status": status})

    host, port, auth = c.get_conn_info(args.server)
    cromwell = Cromwell(host, port, auth)
    res = cromwell.query(query_dict)

    if short_format:
        logger.info("workflow-id\tsample-id")
        for result in res['results']:
            sample_id = result.get('labels').get('sample-id')
            if not sample_id:
                sample_id = ""

            logger.info("%s\t%s" % (result.get('id'), sample_id.upper()))
    else:
        logger.info(json.dumps(parse_json(res['results']), indent=2, sort_keys=True))


def call_samples(args):
    checkfile = args.checkfile
    output = args.output
    app_name = args.app_name
    no_default = args.no_default
    app_dir = os.path.join(c.app_dir, app_name)

    if checkfile:
        if not os.path.isfile(checkfile):
            raise argparse.ArgumentTypeError('%s: No such file.' % checkfile)
        else:
            header_lst = get_header(checkfile)
            if check_variables(app_dir, 'inputs', header_list=header_lst, no_default=no_default) and \
               check_variables(app_dir, 'workflow.wdl', header_list=header_lst, no_default=no_default): # noqa
                logger.info("%s is valid." % checkfile)
    else:
        variables = get_all_variables(app_dir)

        if output:
            with open(output, 'w') as f:
                f.write(','.join(variables))
        else:
            print_obj(variables)
            sys.stdout.flush()


def call_version(args):
    logger.info("Choppy %s" % get_version())


def call_config(args):
    key = args.key
    value = args.value
    app_name = args.app_name
    if app_name:
        app_path = os.path.join(c.app_dir, app_name)
        app_default_var = AppDefaultVar(app_path)

        variables = get_all_variables(app_path)

        if args.show:
            all_default_value = app_default_var.show_default_value()
            print_obj(json.dumps(all_default_value, indent=2, sort_keys=True))
            sys.exit(exit_code.NORMAL_EXIT)

        if key not in variables:
            raise argparse.ArgumentTypeError('Key not in %s' % str(variables))

        if key and value:
            app_default_var.set_default_value(key, value)
            app_default_var.save()
        elif key:
            if args.delete:
                app_default_var.delete(key)
            elif args.show:
                default_value = app_default_var.show_default_value([key, ])
                print_obj(json.dumps(default_value, indent=2, sort_keys=True))
    else:
        conf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'conf'))
        choppy_conf = os.path.join(conf_dir, 'choppy.conf.example')

        if args.output:
            shutil.copyfile(choppy_conf, args.output)
        else:
            with open(choppy_conf, 'r') as f:
                print_obj(f.read())
                sys.stdout.flush()


def call_readme(args):
    output = args.output
    format = args.format
    app_name = args.app_name
    results = render_readme(c.app_dir, app_name, readme="README.md",
                            format=format, output=output)
    print_obj(results)
    sys.stdout.flush()


def call_save(args):
    from choppy.project_revision import Git

    project_path = args.project_path
    url = args.url  # remote git repo
    username = args.username
    msg = args.message

    check_dir(project_path, skip=True)
    git = Git()
    git.init_repo(project_path)

    # Local Commit
    if msg is None:
        msg = 'Add new files.'

    git.commit(msg)
    BashColors.print_color('SUCCESS', 'Save project files successfully.')

    if url:
        # Remote Push
        project_name = os.path.basename(project_path)
        git.add_remote(url, name=project_name, username=username)
        git.push()
        BashColors.print_color('SUCCESS', 'Sync project files successfully.')


def call_clone(args):
    from choppy.project_revision import Git

    username = args.username
    url = args.url
    dest_path = args.dest_path
    branch = args.branch

    check_dir(dest_path, skip=True)
    git = Git()

    git.clone_from(url, dest_path, branch, username)
    print("Clone all files successfully. %s" % dest_path)


def call_archive(args):
    # TODO: 保存所有workflow相关metadata
    pass


def call_status(args):
    from choppy.project_revision import Git

    project_path = args.project_path

    check_dir(project_path, skip=True)
    git = Git()
    git.init_repo(project_path)
    if git.is_dirty():
        print("Warning: Changes not staged for commit")
    else:
        print("Nothing to commit, working tree clean")


def call_docker_builder(args):
    from choppy.docker_mgmt import Docker

    software_name = args.software_name
    software_version = args.software_version
    summary = args.summary
    home = args.home
    software_doc = args.doc
    software_tags = args.software_tags
    tag = args.tag
    username = args.username
    channels = args.channel
    main_program_lst = args.main_program
    raw_deps = args.dep
    parser = args.parser
    dry_run = args.dry_run
    base_image = args.base_image

    deps = [{'name': dep.split(':')[0], 'version': dep.split(':')[1]}
            for dep in raw_deps if re.match(r'^[-\w.]+:[-\w.]+$', dep)]

    if len(raw_deps) != len(deps):
        BashColors.print_color('DANGER',
                               'Choppy parse some deps unsuccessfully.\n'
                               'Maybe some deps can not match the <software_name>:<version> pattern.'
                               'The regex pattern is ^[-\\w.]+:[-\\w.]+$')
        sys.exit(exit_code.VALIDATE_ERROR)

    BashColors.print_color('BLUE',
                           "dependences: %s, parser: %s, main_program: %s, channels: %s" %
                           (str(deps), str(parser), str(main_program_lst), str(channels)))

    if len(main_program_lst) > 0:
        for main_program in main_program_lst:
            if not os.path.isfile(main_program):
                raise argparse.ArgumentTypeError("%s not in %s" % (main_program, os.getcwd()))
    elif parser:
        raise argparse.ArgumentTypeError("You need to specify --main-program argument "
                                         "when you use --parser argument.")

    for channel in channels:
        if not is_valid_url(channel):
            raise argparse.ArgumentTypeError(
                "Invalid url: {} did not match the regex "
                "'(https?)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]'".format(channel))

    if username:
        password = getpass.getpass()
    else:
        username = None
        password = None

    if not tag:
        tag = 'choppy/%s:%s' % (software_name, software_version)

    docker_instance = Docker(username=username, password=password)
    success = docker_instance.build(software_name, software_version, tag, summary=summary,
                                    home=home, software_doc=software_doc, tags=software_tags,
                                    channels=channels, parser=parser, main_program_lst=main_program_lst,
                                    deps=deps, dry_run=dry_run, base_image=base_image)

    if success:
        BashColors.print_color('SUCCESS', 'Dockerfile Path: %s/Dockerfile' % success)

    if not args.no_clean and not success:
        docker_instance.clean_all()


def call_scaffold(args):
    from choppy.scaffold import Scaffold

    output_dir = args.output_dir
    scaffold = Scaffold(output_dir=output_dir)
    scaffold.generate()


def call_server(args):
    from choppy.server import run_server

    run_server(args)


def call_report(args):
    from choppy.report_mgmt import build as build_report

    app_name = args.app_name
    repo_url = args.repo_url
    site_name = args.site_name
    site_description = args.site_description
    site_author = args.site_author
    copyright = get_copyright(site_author)
    theme = args.theme

    server = args.server
    project_dir = args.project_dir
    # sample_id = args.sample_id
    dev_addr = args.dev_addr
    force = args.force
    mode = args.mode
    editable = mode == 'livereload'

    build_report(app_name, project_dir, repo_url=repo_url, site_description=site_description,
                 site_author=site_author, copyright=copyright, site_name=site_name,
                 mode=mode, dev_addr=dev_addr, force=force, server=server,
                 theme_name=theme, editable=editable)


description = """Global Management:
    config      Generate config template / config app default values.
    version     Show the version.

Single Workflow Management:
    submit      Submit a WDL & JSON for execution on a Cromwell VM.
    abort       Abort a submitted workflow.
    restart     Restart a submitted workflow.
    explain     Explain the status of a workflow.
    log         Print the log of a workflow or a project.
    monitor     Monitor a particular workflow and notify user via e-mail upon completion. If a workflow ID is not provided, user-level monitoring is assumed.
    query       Query cromwell for information on the submitted workflow.
    validate    Validate (but do not run) a json for a specific WDL file.
    label       Label a specific workflow with one or more key/value pairs.
    email       Email data to user regarding a workflow.

Choppy App Management:
    batch       Submit batch jobs for execution on a Cromwell VM.
    apps        List all apps that is supported by choppy.
    test        Run app test case.
    testapp     Test an app.
    scaffold    Generate scaffold for a choppy app.
    install     Install an app.
    uninstall   Uninstall an app.
    samples     Generate or check samples file.
    search      Query cromwell for information on the submitted workflow.
    man         Get manual about app.
    report      Generate report for your app results.

OSS Management:
    listfiles   List all files where are in the specified bucket.
    upload      Upload file/directory to the specified bucket.
    download    Download file/directory to the specified bucket.
    copy        Copy file/directory from an oss path to another.
    catlog      Cat log file.

Project Management:
    save        Save all project files to Choppy Version Storage.
    clone       Clone all project files from Choppy Version Storage.
    archive     Generate all metadata files related with the project and save to Choppy Version Storage.
    status      Dirty or clean.

Server Management:
    server      Run server mode.

Docker Management:
    build       Auto build docker image for a software.
"""


parser = argparse.ArgumentParser(
    description='Description: A tool for executing and monitoring WDLs to Cromwell instances.',
    usage='choppy <positional argument> [<args>]',
    formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument('--handler', action='store', default='stream', choices=('stream', 'file'),
                    help="Log handler, stream or file?")
parser.add_argument('--debug', action='store_true', default=False, help="Debug mode.")

sub = parser.add_subparsers(title='commands', description=description)
restart = sub.add_parser(name='restart',
                         description='Restart a submitted workflow.',
                         usage='choppy restart <workflow id> [<args>]',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
restart.add_argument('workflow_id', action='store', help='workflow id of workflow to restart.')
restart.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                     help='Choose a cromwell server from {}'.format(c.servers))
restart.add_argument('-M', '--monitor', action='store_true', default=False, help=argparse.SUPPRESS)
restart.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
restart.set_defaults(func=call_restart)

explain = sub.add_parser(name='explain',
                         description='Explain the status of a workflow.',
                         usage='choppy explain <workflowid> [<args>]',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
explain.add_argument('workflow_id', action='store', help='workflow id of workflow to abort.')
explain.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                     help='Choose a cromwell server from {}'.format(c.servers))
explain.add_argument('-I', '--input', action='store_true', default=False, help=argparse.SUPPRESS)
explain.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
explain.set_defaults(func=call_explain)

log = sub.add_parser(name='log',
                     description='Print the log of a workflow or a project.',
                     usage='choppy log <workflow_id>/<project_name> [<args>]',
                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
log.add_argument('workflow_id', action='store', help='workflow_id or project_name')
log.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                 help='Choose a cromwell server from {}'.format(c.servers))
log.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
log.set_defaults(func=call_log)

abort = sub.add_parser(name='abort',
                       description='Abort a submitted workflow.',
                       usage='choppy abort <workflow id> [<args>]',
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
monitor.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
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
query.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                   help='Owner of workflows to query.')
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
                         'times for multiple options. See https://github.com/broadinstitute/cromwell#workflow-options'
                         'for available options.')
submit.add_argument('-V', '--verbose', action='store_true', default=False,
                    help='If selected, choppy will write the current status to STDOUT until completion while monitoring.')
submit.add_argument('-n', '--no_notify', action='store_true', default=False,
                    help='When selected, disable choppy e-mail notification of workflow completion.')
submit.add_argument('-d', '--dependencies', action='store', default=None, type=is_valid_zip_or_dir,
                    help='A zip file or a directory containing one or more WDL files that the main WDL imports.')
submit.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
submit.add_argument('-S', '--server', action='store', type=str, choices=c.servers, default='localhost',
                    help='Choose a cromwell server from {}'.format(c.servers))
submit.add_argument('-u', '--username', action='store', default=c.getuser(), help=argparse.SUPPRESS)
submit.add_argument('-w', '--workflow_id', help=argparse.SUPPRESS)
submit.add_argument('-x', '--daemon', action='store_true', default=False, help=argparse.SUPPRESS)
submit.set_defaults(func=call_submit)

validate = sub.add_parser(name='validate',
                          description='Validate (but do not run) a json for a specific WDL file.',
                          usage='choppy validate <wdl_file> <json_file> [<args>]',
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

email = sub.add_parser(name='email',
                       description='Email data to user regarding a workflow.',
                       usage='choppy label <workflow_id> [<args>]',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
email.add_argument('workflow_id', nargs='?', default="None", help='workflow id for workflow to label.')
email.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                   help='Choose a cromwell server from {}'.format(c.servers))
email.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                   help='username of user to e-mail to')
email.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
email.add_argument('-D', '--daemon', action='store_true', default=False,
                   help=argparse.SUPPRESS)
email.set_defaults(func=call_email)

batch = sub.add_parser(name="batch",
                       description="Submit batch jobs for execution on a Cromwell VM.",
                       usage="choppy batch <app_name> <samples> [<args>]",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
batch.add_argument('app_name', action='store', choices=listapps(), metavar="app_name",
                   help='The app name for your project.')
batch.add_argument('samples', action='store', type=is_valid, help='Path the samples file to validate.')
batch.add_argument('--project-name', action='store', type=is_valid_project_name, required=True, help='Your project name.')
batch.add_argument('--dry-run', action='store_true', default=False, help='Generate all workflow but skipping running.')
batch.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
batch.add_argument('-S', '--server', action='store', default='localhost', type=str,
                   help='Choose a cromwell server.', choices=c.servers)
batch.add_argument('-f', '--force', action='store_true', default=False, help='Force to overwrite files.')
batch.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                   help=argparse.SUPPRESS)
batch.set_defaults(func=call_batch)

test = sub.add_parser(name="test",
                      description="Submit test jobs for execution on a Cromwell VM.",
                      usage="choppy test <app_name> [<args>]",
                      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
test.add_argument('app_name', action='store', choices=listapps(), metavar="app_name",
                  help='The app name for your project.')
test.add_argument('--project-name', action='store', type=is_valid_project_name, required=True, help='Your project name.')
test.add_argument('--dry-run', action='store_true', default=False, help='Generate all workflow but skipping running.')
test.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
test.add_argument('-S', '--server', action='store', default='localhost', type=str,
                  help='Choose a cromwell server.', choices=c.servers)
test.add_argument('-f', '--force', action='store_true', default=False, help='Force to overwrite files.')
test.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                  help=argparse.SUPPRESS)
test.set_defaults(func=call_test)

testapp = sub.add_parser(name="testapp",
                         description="Test an app.",
                         usage="choppy testapp <app_dir> <samples> [<args>]",
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
testapp.add_argument('app_dir', action='store', type=is_valid, help='The app path for your project.')
testapp.add_argument('samples', action='store', type=is_valid, help='Path the samples file to validate.')
testapp.add_argument('--project-name', action='store', type=is_valid_project_name, required=True, help='Your project name.')
testapp.add_argument('--dry-run', action='store_true', default=False,
                     help='Generate all workflow but skipping running.')
testapp.add_argument('-l', '--label', action='append',
                     help='A key:value pair to assign. May be used multiple times.')
testapp.add_argument('-S', '--server', action='store', choices=c.servers,
                     default='localhost', type=str, help='Choose a cromwell server.')
testapp.add_argument('-f', '--force', action='store_true',
                     default=False, help='Force to overwrite files.')
testapp.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                     help=argparse.SUPPRESS)
testapp.set_defaults(func=call_testapp)

installapp = sub.add_parser(name="install",
                            description="Install an app from a zip file or choppy store.",
                            usage="choppy install <choppy_app> [<args>]",
                            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
installapp.add_argument('choppy_app', action='store', type=is_valid_app_name,
                        help="App name or app zip file, the default version is latest. eg. choppy/dna_seq:v0.1.0")
installapp.add_argument('-f', '--force', action='store_true',
                        default=False, help='Force to overwrite app.')
installapp.set_defaults(func=call_installapp)

uninstallapp = sub.add_parser(name="uninstall",
                              description="Uninstall an app.",
                              usage="choppy uninstall app_name",
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
uninstallapp.add_argument('app_name', action='store', metavar="app_name",
                          help='App name.', choices=listapps())
uninstallapp.set_defaults(func=call_uninstallapp)

wdllist = sub.add_parser(name="apps",
                         description="List all apps that is supported by choppy.",
                         usage="choppy apps",
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
wdllist.set_defaults(func=call_list_apps)

listfiles = sub.add_parser(name="listfiles",
                           description="List all files where are in the specified bucket.",
                           usage="choppy listfiles <oss_link> [<args>]",
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
listfiles.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
listfiles.add_argument('-l', '--long-format', action="store_true", default=False,
                       help="Show by long format, if the option is not specified, show short format by default.")
listfiles.add_argument('-r', '--recursive', action='store_true',
                       default=False, help='Recursively list subdirectories encountered.')
listfiles.set_defaults(func=call_list_files)

upload_files = sub.add_parser(name="upload",
                              description="Upload file/directory to the specified bucket.",
                              usage="choppy upload <local_path> <oss_link> [<args>]",
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
upload_files.add_argument('local_path', action='store', type=is_valid, help='local_path.')
upload_files.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
upload_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
upload_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
upload_files.set_defaults(func=call_upload_files)

download_files = sub.add_parser(name="download",
                                description="Download file/directory to the specified bucket.",
                                usage="choppy download <oss_link> <local_path> [<args>]",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
download_files.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
download_files.add_argument('local_path', action='store', type=is_valid, help='local_path.')
download_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
download_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
download_files.set_defaults(func=call_download_files)

copy_files = sub.add_parser(name="copy",
                            description="Copy file/directory from an oss path to another.",
                            usage="choppy copy <src_oss_link> <dest_oss_link> [<args>]",
                            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
copy_files.add_argument('src_oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
copy_files.add_argument('dest_oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
copy_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
copy_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
copy_files.set_defaults(func=call_cp_remote_files)

cat_file = sub.add_parser(name="catlog",
                          description="Cat log file.",
                          usage="choppy catlog <oss_link>",
                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cat_file.add_argument('oss_link', action='store', type=is_valid_oss_link, help='OSS Link.')
cat_file.set_defaults(func=call_cat_remote_file)

config = sub.add_parser(name="config",
                        description="Generate config template.",
                        usage="choppy config",
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
config.add_argument('--output', action='store', help='Choppy config file name.')
config.add_argument('-k', '--key', action="store", help='Set default value for an app.')
config.add_argument('-v', '--value', action="store", help='Set default value for an app.')
config.add_argument('--app-name', action='store', choices=listapps(),
                    help='The app name for your project.', metavar="app_name")
config.add_argument('-d', '--delete', action="store_true", default=False,
                    help="Delete default key.")
config.add_argument('-s', '--show', action="store_true", default=False,
                    help="Show default variable.")
config.set_defaults(func=call_config)

samples = sub.add_parser(name="samples",
                         description="samples file.",
                         usage="choppy samples <app_name> [<args>]",
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
samples.add_argument('app_name', action='store', choices=listapps(),
                     help='The app name for your project.', metavar="app_name")
samples.add_argument('--output', action='store', help='Samples file name.')
samples.add_argument('--checkfile', action='store', help="Your samples file.")
samples.add_argument('--no-default', action="store_true", default=False,
                     help="Don't list default keys that have been config in an app.")
samples.set_defaults(func=call_samples)

search = sub.add_parser(name='search',
                        description='Query cromwell for information on the submitted workflow.',
                        usage='choppy search [<args>]',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
search.add_argument('-s', '--status', action='store', default="Running", choices=c.status_list,
                    help='Print status for workflow to stdout')
search.add_argument('--project-name', action="store", required=True, help="Project name")
search.add_argument('--short-format', action="store_true", default=False,
                    help="Show by short format, if the option is not specified, show long format by default.")
search.add_argument('-u', '--username', action='store', default=c.getuser(), type=is_valid_label,
                    help='Owner of workflows to query.')
search.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                    help='Choose a cromwell server from {}'.format(c.servers))
search.set_defaults(func=call_search)

version = sub.add_parser(name="version",
                         description="Show the version.",
                         usage="choppy version",
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
version.set_defaults(func=call_version)

manual = sub.add_parser(name="man",
                        description="Get manual about app.",
                        usage="choppy man <app_name> [<args>]",
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
manual.add_argument('app_name', action='store', choices=listapps(),
                    help='The app name for your project.', metavar="app_name")
manual.add_argument('-o', '--output', action='store', help='output file name.')
manual.add_argument('-f', '--format', action='store', help='output format.', default='html',
                    choices=('html', 'markdown'))
manual.set_defaults(func=call_readme)

save = sub.add_parser(name="save",
                      description="Save all project files to Choppy Version Storage.",
                      usage="choppy save <project_path> <url> [<args>]",
                      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
save.add_argument('project_path', action='store', help='Your project path.')
save.add_argument('--url', action='store', help='Git Remote Repo.')
save.add_argument('-u', '--username', action='store', type=is_valid_label,
                  help='Owner of remote git repo.')
save.add_argument('-m', '--message', action='store', help='The comment of your project.')
save.set_defaults(func=call_save)

clone = sub.add_parser(name="clone",
                       description="Clone all project files from Choppy Version Storage.",
                       usage="choppy clone <url> <dest_path> [<args>]",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
clone.add_argument('url', action='store', help='Git Remote Repo.')
clone.add_argument('dest_path', action='store', help='Your destination path.')
clone.add_argument('-u', '--username', action='store', type=is_valid_label,
                   help='Owner of remote git repo.')
clone.add_argument('-b', '--branch', action='store',
                   help='The branch of your project.')
clone.set_defaults(func=call_clone)

status = sub.add_parser(name="status",
                        description="Dirty or clean.",
                        usage="choppy status <project_path>",
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
status.add_argument('project_path', action='store', help='Your project path.')
status.set_defaults(func=call_status)

server = sub.add_parser(name="server",
                        description="Run server mode.",
                        usage="choppy server [<args>]",
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
server.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                    help='Choose a cromwell server from {}'.format(c.servers))
server.add_argument('-D', '--daemon', action='store_true', default=False,
                    help='Run server with daemon mode')
server.add_argument('-f', '--framework', action='store', default='BJOERN',
                    choices=['BJOERN', 'GEVENT'], help='Run server with framework.')
server.add_argument('-s', '--swagger', action='store_true', default=False, help="Enable swagger documentation.")
server.set_defaults(func=call_server)

docker_builder = sub.add_parser(name="build",
                                description="Auto build docker image for a software.",
                                usage="choppy build software_name software_version [<args>]",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
docker_builder.add_argument('software_name', action='store', help='Software name.')
docker_builder.add_argument('software_version', action='store', help='Software version.')
docker_builder.add_argument('-s', '--summary', action='store', default='', help='The summary about a software.')
docker_builder.add_argument('--home', action='store', default='', help='Home page for a software.')
docker_builder.add_argument('--doc', action='store', default='', help='Doc page for a software. May be a website.')
docker_builder.add_argument('-t', '--tag', action='store', default='', help="Tag for docker image. Need to follow docker tag's convention.")
docker_builder.add_argument('--software-tags', action='store', default='', help="Software tag, eg: Genomics, Rlang.")
docker_builder.add_argument('-u', '--username', action='store', type=is_valid_label,
                            help='Account of docker registry.')
docker_builder.add_argument('--channel', action='append', default=[], help='Add conda channel url.')
docker_builder.add_argument('--dep', action='append', default=[], help='Add dependencie, be similar as software:version.')
docker_builder.add_argument('--main-program', action='append', default=[], help='Your main script, may be several.')
docker_builder.add_argument('--parser', action='store', help='What script language.', choices=get_parser())
docker_builder.add_argument('--base-image', action='store', default=get_default_image(), choices=get_base_images(),
                            help='Base docker image, MUST BE based on alpine linux.')
docker_builder.add_argument('--dry-run', action='store_true', default=False, help='Generate all related files but skipping running.')
docker_builder.add_argument('--no-clean', action='store_true', default=False,
                            help='NOT clean containers and images.')
docker_builder.set_defaults(func=call_docker_builder)


scaffold = sub.add_parser(name="scaffold",
                          description="Generate scaffold for a choppy app.",
                          usage="choppy scaffold",
                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
scaffold.add_argument('--output-dir', action='store', default='./', help='Scaffold output directory.')
scaffold.set_defaults(func=call_scaffold)


report = sub.add_parser(name="report",
                        description="Generate report for your app results.",
                        usage="choppy report <app_name> [<args>]",
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
report.add_argument('app_name', action='store', choices=listapps(),
                    help='The app name for your project.', metavar="app_name")
report.add_argument('--mode', action='store', default='build', choices=get_mode(), help='Which mode for your report.')
report.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=c.servers,
                    help='Choose a cromwell server from {}'.format(c.servers))
report.add_argument('--dev-addr', action='store', default='127.0.0.1:8000', help='Development server address.',
                    metavar='<IP:PORT>')
report.add_argument('-f', '--force', action='store_true', default=False, help='Force to regenerate files.')
report.add_argument('--project-dir', action='store', required=True, help='Your project directory',
                    type=is_valid)
report.add_argument('--theme', action='store', default='mkdocs', choices=ReportTheme.get_theme_lst(),
                    help='Theming your report by using the specified theme.')
report.add_argument('--repo-url', action='store', help='Your project repo url', type=is_valid_url)
report.add_argument('--site-name', action='store', help='The site name for your report website', default='Choppy Report')
report.add_argument('--site-author', action='store', help='The site author', default='choppy')
report.add_argument('--site-description', action='store', help='The site description',
                    default='Choppy is a painless reproducibility manager.')
report.set_defaults(func=call_report)


def main():
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Fix bug: user need to set choppy.conf before running choppy.
    if args.func != call_config and c.conf_path == c.conf_file_example:
        BashColors.print_color('DANGER', "Error: Not Found choppy.conf.\n\n"
                               "You need to run `choppy config` to generate "
                               "config template, modify it and copy to the one of directories %s.\n"
                               % c.CONFIG_FILES)
        sys.exit(exit_code.CONFIG_FILE_NOT_EXIST)

    user = c.getuser()

    if args.debug:
        loglevel = logging.DEBUG
    else:
        loglevel = c.log_level

    # Get user's username so we can tag workflows and logs for them.
    if hasattr(args, 'project_name'):
        check_identifier(args.project_name)
        set_logger(args.project_name, loglevel=loglevel, handler=args.handler)
    else:
        set_logger(user, loglevel=loglevel, handler=args.handler, subdir=None)

    # Clean up the temp directory
    clean_temp_dir('/tmp/choppy/')

    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
