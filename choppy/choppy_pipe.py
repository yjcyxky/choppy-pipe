#!/usr/bin/env python
# -*- coding:utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
    choppy.choppy_pipe
    ~~~~~~~~~~~~~~~~~~

    Command-line to the cromwell execution engine servers.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
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
import verboselogs
from choppy.config import init_config, get_global_config
from choppy import exit_code
from choppy.check_utils import (is_valid_label, is_valid_project_name, is_valid,
                                is_valid_oss_link, check_dir, check_identifier,
                                is_valid_zip_or_dir, is_valid_app_name)
from choppy.version import get_version
from choppy.utils import (clean_temp, set_logger)
from choppy.exceptions import NotFoundApp

init_config()
global_config = get_global_config()
logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger('choppy')


def call_submit(args):
    """Optionally validates inputs and starts a workflow on the Cromwell execution engine if validation passes. Validator returns an empty list if valid, otherwise, a list of errors discovered.

    :param args: submit subparser arguments.
    :return: JSON response with Cromwell workflow ID.
    """
    from choppy.core.json_checker import check_json
    from choppy.core.cromwell import Cromwell
    from choppy.core.app_utils import generate_dependencies_zip, kv_list_to_dict

    dependencies = args.dependencies
    if dependencies and os.path.isdir(dependencies):
        dependencies = generate_dependencies_zip(dependencies)

    check_json(json_file=args.json)

    if args.validate:
        call_validate(args)

    # prep labels and add user
    labels_dict = kv_list_to_dict(args.label) if kv_list_to_dict(args.label) is not None else {}
    labels_dict['username'] = args.username.lower()
    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
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
    print('workflow_id: %s' % result['id'])

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
    """Get various types of data on a particular workflow ID.

    :param args:  query subparser arguments.
    :return: A list of json responses based on queries selected by the user.
    """
    from choppy.core.cromwell import Cromwell
    from choppy.core.app_utils import kv_list_to_dict, parse_json

    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
    responses = []
    if args.workflow_id is None or args.workflow_id == "None" and not args.label:
        return call_list(args)
    if args.label:
        logger.debug("Label query requested.")
        labeled = cromwell.query_labels(labels=kv_list_to_dict(args.label))
        responses.append(labeled)
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
    print("\n%s\n" % json.dumps(parse_json(responses), indent=2, sort_keys=True))
    sys.stdout.flush()
    return responses


def call_validate(args):
    """Calls the Validator to validate input json. Exits with feedback to user regarding errors in json or reports no errors found.

    :param args: validation subparser arguments.
    :return:
    """
    from choppy.core.validator import Validator

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
    """Abort a workflow with a given workflow id.

    :param args: abort subparser args.
    :return: JSON containing abort response.
    """
    from choppy.core.cromwell import Cromwell

    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
    logger.info("Abort requested")
    return cromwell.stop_workflow(workflow_id=args.workflow_id)


def call_monitor(args):
    """Calls Monitoring to report to user the status of their workflow at regular intervals.

    :param args: 'monitor' subparser arguments.
    :return:
    """
    from choppy.core.cromwell import print_log_exit
    from choppy.core.monitor import Monitor

    logger.info("Monitoring requested")

    logger.info("-------------Monitoring Workflow-------------")
    try:
        if args.daemon:
            m = Monitor(host=args.server, user="*", no_notify=args.no_notify,
                        verbose=args.verbosity, interval=args.interval)
            m.run()
        else:
            m = Monitor(host=args.server, user=args.username.lower(),
                        no_notify=args.no_notify, verbose=args.verbosity,
                        interval=args.interval)
            if args.workflow_id:
                m.monitor_workflow(args.workflow_id)
            else:
                m.monitor_user_workflows()
    except Exception as e:
        print_log_exit(msg=str(e), sys_exit=False, ple_logger=logger)


def call_restart(args):
    """Call cromwell restart to restart a failed workflow.

    :param args: restart subparser arguments.
    :return:
    """
    from choppy.core.cromwell import Cromwell

    logger.info("Restart requested")
    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
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
    """Get metadata and timing graph URLs.

    :param server: cromwell host
    :param workflow_id: UUID for workflow
    :param port: port for cromwell server of interest
    :return: Dictionary containing useful links
    """
    return {'metadata': 'http://{}:{}/api/workflows/v1/{}/metadata'.format(server, port, workflow_id),
            'timing': 'http://{}:{}/api/workflows/v1/{}/timing'.format(server, port, workflow_id)}


def call_explain(args):
    from choppy.core.cromwell import Cromwell

    logger.info("Explain requested")
    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
    (result, additional_res, stdout_res) = cromwell.explain_workflow(workflow_id=args.workflow_id,
                                                                     include_inputs=args.input)

    def my_safe_repr(object, context, maxlevels, level):
        # typ = pprint._type(object)
        # try:
        #     if typ is unicode:  # noqa
        #         object = str(object)
        # except Exception:
        #     pass
        return pprint._safe_repr(object, context, maxlevels, level)

    printer = pprint.PrettyPrinter()
    printer.format = my_safe_repr
    if result is not None:
        logger.info("-------------Workflow Status-------------")
        printer.pprint(result)

        if len(additional_res) > 0:
            print("-------------Additional Parameters-------------")
            printer.pprint(additional_res)

        if len(stdout_res) > 0:
            for log in stdout_res["failed_jobs"]:
                print("-------------Failed Stdout-------------")
                print("Shard: " + log["stdout"]["label"])
                print(log["stdout"]["name"] + ":")
                print(log["stdout"]["log"])
                print("-------------Failed Stderr-------------")
                print("Shard: " + log["stderr"]["label"])
                print(log["stderr"]["name"] + ":")
                print(log["stderr"]["log"])

        logger.info("-------------Cromwell Links-------------")
        links = get_cromwell_links(args.server, result['id'], cromwell.port)
        logger.info(links['metadata'])
        logger.info(links['timing'])

    else:
        logger.warn("Workflow not found.")

    args.monitor = True
    return None


def call_list(args):
    from choppy.core.monitor import Monitor
    from choppy.core.app_utils import parse_json

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
        # typ = pprint._type(object)
        # try:
        #     if typ is unicode:  # noqa: python2+
        #         object = str(object)
        # except Exception:
        #     pass
        return pprint._safe_repr(object, context, maxlevels, level)

    start_date_str = get_iso_date(datetime.datetime.now() - datetime.timedelta(days=int(args.days)))
    q = m.get_user_workflows(raw=True, start_time=start_date_str)
    try:
        result = q["results"]
        if args.filter:
            result = [res for res in result if res['status'] in args.filter]
        result = list(map(lambda j: process_job(j), result))
        print("\n%s\n" % json.dumps(parse_json(result), indent=2, sort_keys=True))
        args.monitor = True
        return result
    except KeyError as e:
        logger.critical('KeyError: Unable to find key {}'.format(e))


def call_label(args):
    """Apply labels to a workflow that currently exists in the database.

    :param args: label subparser arguments
    :return:
    """
    from choppy.core.cromwell import Cromwell
    from choppy.core.app_utils import kv_list_to_dict

    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
    labels_dict = kv_list_to_dict(args.label)
    response = cromwell.label_workflow(workflow_id=args.workflow_id, labels=labels_dict)
    if response.status_code == 200:
        logger.info("Labels successfully applied:\n{}".format(response.content))
    else:
        logger.critical("Unable to apply specified labels:\n{}".format(response.content))


def call_log(args):
    """Get workflow logs via cromwell API.

    :param args: log subparser arguments.
    :return:
    """
    from choppy.core.cromwell import Cromwell
    from choppy.core.oss import run_copy_files
    from choppy.core.app_utils import parse_json

    matchedWorkflowId = re.match(r'^[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}$',
                                 args.workflow_id, re.M | re.I)

    if matchedWorkflowId:
        section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
        host, port, auth = global_config.get_conn_info(args.server, section_name)

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
                dest_script = os.path.join(global_config.get_path('general', 'tmp_dir'),
                                           "%s/%s" % (fuuid, "script"))
                run_copy_files(script, dest_script, recursive=False, silent=True)
                with open(dest_script, 'r') as f:
                    command_log = f.read()

                logger.info(key + ":")
                logger.info("\n" + command_log)

            return None
        else:
            metadata = cromwell.query_metadata(args.workflow_id)
            print("\n%s\n" % json.dumps(parse_json(metadata), indent=2, sort_keys=True))
    else:
        project_logs = os.path.join(global_config.get_path('general', 'log_dir'), "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(args.workflow_id))
        if os.path.isfile(logfile):
            with open(logfile, 'r') as f:
                print(f.read())
        else:
            logger.warn("No such project: %s" % args.workflow_id)


def call_cat_remote_file(args):
    from choppy.core.oss import run_copy_files

    remote_file = args.oss_link
    fuuid = uuid.uuid1()
    dest_file = os.path.join(global_config.get_path('general', 'tmp_dir'), str(fuuid))
    run_copy_files(remote_file, dest_file, recursive=False, silent=True)

    if os.path.isfile(dest_file):
        with open(dest_file, 'r') as f:
            for line in f.readlines():
                print(line.strip('\n'))
                sys.stdout.flush()
    else:
        logger.warn("Not a file.")


def call_email(args):
    """MVP pass-through function for testing desirability of a call_email feature. If users want a full-fledged function we can rework this.

    :param args: email subparser args.
    :return:
    """
    args.verbose = False
    args.no_notify = False
    args.interval = 0
    call_monitor(args)


def call_list_apps(args):
    from choppy.core.app_utils import listapps

    apps = listapps()
    if len(apps) > 0:
        print(apps)
    else:
        print("No any installed app.")


def call_batch(args):
    from choppy.core.workflow import run_batch
    from choppy.core.app_utils import is_valid_app, get_app_root_dir

    app_root_dir = get_app_root_dir()
    app_dir = os.path.join(app_root_dir, args.app_name)
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
    from choppy.core.workflow import run_batch
    from choppy.core.app_utils import get_app_root_dir

    app_root_dir = get_app_root_dir()
    app_dir = os.path.join(app_root_dir, args.app_name)
    project_name = args.project_name
    samples = os.path.join(app_root_dir, 'test', 'samples')
    if not os.path.isfile(samples):
        print("No test file for %s" % args.app_name)
        sys.exit(exit_code.NO_TEST_FILE)

    label = args.label
    server = args.server
    dry_run = args.dry_run
    username = args.username.lower()
    force = args.force
    run_batch(project_name, app_dir, samples, label, server, username, dry_run, force)


def call_testapp(args):
    from choppy.core.workflow import run_batch

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
    from choppy.core.app_utils import parse_app_name, install_app, get_app_root_dir
    choppy_app = args.choppy_app
    force = args.force

    # Try Parse Choppy App Name with Zip Format
    app_name_lst = [os.path.splitext(os.path.basename(choppy_app))[0], ]
    # Try Parse Choppy App Name with Git Repo Format
    parsed_dict = parse_app_name(choppy_app)
    if parsed_dict:
        namespace = parsed_dict.get('namespace')
        app_name = parsed_dict.get('app_name')
        version = parsed_dict.get('version')
        app_name_lst.append('%s/%s-%s' % (namespace, app_name, version))

    app_root_dir = get_app_root_dir()
    for app_name in app_name_lst:
        app_path = os.path.join(app_root_dir, app_name)
        # Overwrite If an app is installed.
        if os.path.exists(app_path):
            if force:
                shutil.rmtree(app_path, ignore_errors=True)
            else:
                print("%s is installed. If you want to reinstall, you can specify a --force flag." % app_name)
                sys.exit(exit_code.APP_IS_INSTALLED)

    install_app(app_root_dir, choppy_app)


def call_uninstallapp(args):
    from choppy.core.app_utils import uninstall_app, get_app_root_dir

    app_root_dir = get_app_root_dir()
    app_dir = os.path.join(app_root_dir, args.app_name)
    if not os.path.isdir(app_dir):
        raise NotFoundApp("The %s doesn't exist" % args.app_name)

    uninstall_app(app_dir)


def call_list_files(args):
    from subprocess import CalledProcessError, check_output

    oss_link = args.oss_link
    recursive = args.recursive
    long_format = args.long_format

    oss_bin = global_config.get('oss', 'oss_bin')
    if not oss_bin:
        oss_bin_name = 'ossutil64' if os.uname().sysname == 'Linux' else 'ossutilmac64'
        oss_bin = os.path.join(global_config.resource_dir, 'lib', oss_bin_name)

    access_key = global_config.get('oss', 'access_key')
    access_secret = global_config.get('oss', 'access_secret')
    endpoint = global_config.get('oss', 'endpoint')

    try:
        shell_cmd = [oss_bin, "ls", oss_link, "-i", access_key, "-k",
                     access_secret, "-e", endpoint]

        if not long_format:
            if not recursive:
                shell_cmd.append('-d')
            else:
                shell_cmd.append('-s')

        logger.debug('Running command: %s' % ' '.join(shell_cmd))
        output = check_output(shell_cmd).decode().splitlines()

        if len(output) > 2:
            for i in output[0:-2]:
                print("%s" % i)
                sys.stdout.flush()
    except (CalledProcessError, TypeError) as err:
        logger.critical("access_key/access_secret or oss_link is not valid.")
        logger.debug("Error msg: %s" % str(err))


def call_upload_files(args):
    from choppy.core.oss import run_copy_files

    oss_link = args.oss_link
    local_path = args.local_path
    include = args.include
    exclude = args.exclude
    run_copy_files(local_path, oss_link, include, exclude)


def call_download_files(args):
    from choppy.core.oss import run_copy_files

    oss_link = args.oss_link
    oss_link_file = args.input_file
    local_path = args.output_dir
    include = args.include
    exclude = args.exclude
    recursive = args.recursive

    if oss_link_file:
        with open(oss_link_file, 'r') as f:
            oss_links = [line.strip() for line in f.readlines() if line.strip()]
    else:
        is_valid_oss_link(oss_link)
        oss_links = oss_link
    run_copy_files(oss_links, local_path, include, exclude, recursive=recursive)


def call_cp_remote_files(args):
    from choppy.core.oss import run_copy_files

    src_oss_link = args.src_oss_link
    dest_oss_link = args.dest_oss_link
    include = args.include
    exclude = args.exclude
    run_copy_files(src_oss_link, dest_oss_link, include, exclude)


def call_search(args):
    from choppy.core.cromwell import Cromwell
    from choppy.core.app_utils import parse_json

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

    section_name = 'remote_%s' % args.server if args.server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(args.server, section_name)
    cromwell = Cromwell(host, port, auth)
    res = cromwell.query(query_dict)

    if short_format:
        print("workflow-id\tsample-id")
        for result in res['results']:
            sample_id = result.get('labels').get('sample-id')
            if not sample_id:
                sample_id = ""

            print("%s\t%s" % (result.get('id'), sample_id.upper()))
    else:
        results = parse_json(res['results'])
        if len(results) > 0:
            print(json.dumps(results, indent=2, sort_keys=True))
        else:
            print("Not found.")


def call_samples(args):
    from choppy.core.app_utils import (get_header, check_variables,
                                       get_all_variables, get_app_root_dir)

    checkfile = args.checkfile
    output = args.output
    app_name = args.app_name
    no_default = args.no_default
    app_root_dir = get_app_root_dir()
    app_dir = os.path.join(app_root_dir, app_name)

    if checkfile:
        if not os.path.isfile(checkfile):
            raise argparse.ArgumentTypeError('%s: No such file.' % checkfile)
        else:
            header_lst = get_header(checkfile)
            if check_variables(app_dir, 'inputs', header_list=header_lst, no_default=no_default) and \
               check_variables(app_dir, 'workflow.wdl', header_list=header_lst, no_default=no_default):  # noqa
                print("%s is valid." % checkfile)
    else:
        variables = get_all_variables(app_dir, no_default)

        if output:
            with open(output, 'w') as f:
                f.write(','.join(variables))
        else:
            print(','.join(variables))
            sys.stdout.flush()


def call_version(args):
    print("Choppy %s" % get_version())


def call_readme(args):
    from choppy.core.app_utils import render_readme, get_app_root_dir

    output = args.output
    format = args.format
    app_name = args.app_name
    app_root_dir = get_app_root_dir()
    results = render_readme(app_root_dir, app_name, readme="README.md",
                            format=format, output=output)
    print(results)
    sys.stdout.flush()


def call_config(args):
    from choppy.core.app_utils import (AppDefaultVar, get_all_variables,
                                       get_app_root_dir)

    key = args.key
    value = args.value
    app_name = args.app_name
    if app_name:
        app_root_dir = get_app_root_dir()
        app_path = os.path.join(app_root_dir, app_name)
        app_default_var = AppDefaultVar(app_path)

        variables = get_all_variables(app_path)

        if args.show:
            all_default_value = app_default_var.show_default_value()
            print(json.dumps(all_default_value, indent=2, sort_keys=True))
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
                print(json.dumps(default_value, indent=2, sort_keys=True))
    else:
        conf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config'))
        choppy_conf = os.path.join(conf_dir, 'choppy.conf.example')

        if args.output:
            shutil.copyfile(choppy_conf, args.output)
        else:
            with open(choppy_conf, 'r') as f:
                print(f.read())
                sys.stdout.flush()


def call_scaffold(args):
    from choppy.core.scaffold import Scaffold

    output_dir = args.output_dir
    template_name = args.templ_name
    scaffold = Scaffold(output_dir=output_dir)
    scaffold.generate(template=template_name)


def call_save(args):
    from choppy.core.project_revision import Git

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
    logger.success('Save project files successfully.')

    if url:
        # Remote Push
        project_name = os.path.basename(project_path)
        git.add_remote(url, name=project_name, username=username)
        git.push()
        logger.success('Sync project files successfully.')


def call_clone(args):
    from choppy.core.project_revision import Git

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
    from choppy.core.project_revision import Git

    project_path = args.project_path

    check_dir(project_path, skip=True)
    git = Git()
    git.init_repo(project_path)
    if git.is_dirty():
        print("Warning: Changes not staged for commit")
    else:
        print("Nothing to commit, working tree clean")


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
"""


def parse_args():
    from choppy.core.app_utils import listapps

    parser = argparse.ArgumentParser(
        description='Description: A tool for executing and monitoring WDLs to Cromwell instances.',
        usage='choppy <positional argument> [<args>]',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--handler', action='store', default='stream', choices=('stream', 'file'),
                        help="Log handler, stream or file?")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--debug', action='store_true', default=False, help="Debug mode.")
    group.add_argument('-q', '--quite', action='store_true', default=False, help="Only display key message.")
    group.add_argument('-v', '--verbose', action='count', default=0, help='Increase output verbosity')

    sub = parser.add_subparsers(title='commands', description=description)
    restart = sub.add_parser(name='restart',
                             description='Restart a submitted workflow.',
                             usage='choppy restart <workflow id> [<args>]',
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    restart.add_argument('workflow_id', action='store', help='workflow id of workflow to restart.')
    restart.add_argument('-S', '--server', action='store', default="localhost", type=str,
                         choices=global_config.servers,
                         help='Choose a cromwell server from {}'.format(global_config.servers))
    restart.add_argument('-M', '--monitor', action='store_true', default=False, help=argparse.SUPPRESS)
    restart.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
    restart.set_defaults(func=call_restart)

    explain = sub.add_parser(name='explain',
                             description='Explain the status of a workflow.',
                             usage='choppy explain <workflowid> [<args>]',
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    explain.add_argument('workflow_id', action='store', help='workflow id of workflow to abort.')
    explain.add_argument('-S', '--server', action='store', default="localhost", type=str,
                         choices=global_config.servers,
                         help='Choose a cromwell server from {}'.format(global_config.servers))
    explain.add_argument('-I', '--input', action='store_true', default=False, help=argparse.SUPPRESS)
    explain.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
    explain.set_defaults(func=call_explain)

    log = sub.add_parser(name='log',
                         description='Print the log of a workflow or a project.',
                         usage='choppy log <workflow_id>/<project_name> [<args>]',
                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    log.add_argument('workflow_id', action='store', help='workflow_id or project_name')
    log.add_argument('-S', '--server', action='store', default="localhost", type=str,
                     choices=global_config.servers,
                     help='Choose a cromwell server from {}'.format(global_config.servers))
    log.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
    log.set_defaults(func=call_log)

    abort = sub.add_parser(name='abort',
                           description='Abort a submitted workflow.',
                           usage='choppy abort <workflow id> [<args>]',
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    abort.add_argument('workflow_id', action='store', help='workflow id of workflow to abort.')
    abort.add_argument('-S', '--server', action='store', default="localhost", type=str,
                       choices=global_config.servers,
                       help='Choose a cromwell server from {}'.format(global_config.servers))
    abort.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
    abort.set_defaults(func=call_abort)

    monitor = sub.add_parser(name='monitor',
                             description='Monitor a particular workflow and notify user via e-mail upon completion. If a'
                             'workflow ID is not provided, user-level monitoring is assumed.',
                             usage='choppy monitor <workflow_id> [<args>]',
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    monitor.add_argument('workflow_id', action='store', nargs='?',
                         help='workflow id for workflow to monitor. Do not specify if user-level monitoring is desired.')
    monitor.add_argument('-u', '--username', action='store', default=global_config.getuser(),
                         type=is_valid_label, help='Owner of workflows to monitor.')
    monitor.add_argument('-i', '--interval', action='store', default=30, type=int,
                         help='Amount of time in seconds to elapse between status checks.')
    monitor.add_argument('-V', '--verbosity', action='store_true', default=False,
                         help='When selected, choppy will write the current status to STDOUT until completion.')
    monitor.add_argument('-n', '--no_notify', action='store_true', default=False,
                         help='When selected, disable choppy e-mail notification of workflow completion.')
    monitor.add_argument('-S', '--server', action='store', default="localhost", type=str,
                         choices=global_config.servers,
                         help='Choose a cromwell server from {}'.format(global_config.servers))
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
    query.add_argument('-u', '--username', action='store', default=global_config.getuser(), type=is_valid_label,
                       help='Owner of workflows to query.')
    query.add_argument('-L', '--label', action='append', help='Query status of all workflows with specific label(s).')
    query.add_argument('-d', '--days', action='store', default=7, help='Last n days to query.')
    query.add_argument('-S', '--server', action='store', default="localhost", type=str,
                       choices=global_config.servers,
                       help='Choose a cromwell server from {}'.format(global_config.servers))
    query.add_argument('-f', '--filter', action='append', type=str, choices=global_config.status_list,
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
    submit.add_argument('-V', '--verbosity', action='store_true', default=False,
                        help='If selected, choppy will write the current status to STDOUT until completion while monitoring.')
    submit.add_argument('-n', '--no_notify', action='store_true', default=False,
                        help='When selected, disable choppy e-mail notification of workflow completion.')
    submit.add_argument('-d', '--dependencies', action='store', default=None, type=is_valid_zip_or_dir,
                        help='A zip file or a directory containing one or more WDL files that the main WDL imports.')
    submit.add_argument('-D', '--disable_caching', action='store_true', default=False, help="Don't used cached data.")
    submit.add_argument('-S', '--server', action='store', type=str, choices=global_config.servers, default='localhost',
                        help='Choose a cromwell server from {}'.format(global_config.servers))
    submit.add_argument('-u', '--username', action='store', default=global_config.getuser(), help=argparse.SUPPRESS)
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
    label.add_argument('-S', '--server', action='store', type=str, choices=global_config.servers, default="localhost",
                       help='Choose a cromwell server from {}'.format(global_config.servers))
    label.add_argument('-l', '--label', action='append', help='A key:value pair to assign. May be used multiple times.')
    label.add_argument('-M', '--monitor', action='store_false', default=False, help=argparse.SUPPRESS)
    label.set_defaults(func=call_label)

    email = sub.add_parser(name='email',
                           description='Email data to user regarding a workflow.',
                           usage='choppy label <workflow_id> [<args>]',
                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    email.add_argument('workflow_id', nargs='?', default="None", help='workflow id for workflow to label.')
    email.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=global_config.servers,
                       help='Choose a cromwell server from {}'.format(global_config.servers))
    email.add_argument('-u', '--username', action='store', default=global_config.getuser(), type=is_valid_label,
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
    batch.add_argument('-p', '--project-name', action='store', type=is_valid_project_name,
                       required=True, help='Your project name.')
    batch.add_argument('-D', '--dry-run', action='store_true', default=False,
                       help='Generate all workflow but skipping running.')
    batch.add_argument('-l', '--label', action='append',
                       help='A key:value pair to assign. May be used multiple times.')
    batch.add_argument('-S', '--server', action='store', default='localhost', type=str,
                       help='Choose a cromwell server.', choices=global_config.servers)
    batch.add_argument('-f', '--force', action='store_true', default=False,
                       help='Force to overwrite files.')
    batch.add_argument('-u', '--username', action='store', default=global_config.getuser(),
                       type=is_valid_label, help=argparse.SUPPRESS)
    batch.set_defaults(func=call_batch)

    test = sub.add_parser(name="test",
                          description="Submit test jobs for execution on a Cromwell VM.",
                          usage="choppy test <app_name> [<args>]",
                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    test.add_argument('app_name', action='store', choices=listapps(), metavar="app_name",
                      help='The app name for your project.')
    test.add_argument('-p', '--project-name', action='store', type=is_valid_project_name,
                      required=True, help='Your project name.')
    test.add_argument('-D', '--dry-run', action='store_true', default=False,
                      help='Generate all workflow but skipping running.')
    test.add_argument('-l', '--label', action='append',
                      help='A key:value pair to assign. May be used multiple times.')
    test.add_argument('-S', '--server', action='store', default='localhost', type=str,
                      help='Choose a cromwell server.', choices=global_config.servers)
    test.add_argument('-f', '--force', action='store_true', default=False,
                      help='Force to overwrite files.')
    test.add_argument('-u', '--username', action='store', default=global_config.getuser(),
                      type=is_valid_label, help=argparse.SUPPRESS)
    test.set_defaults(func=call_test)

    testapp = sub.add_parser(name="testapp",
                             description="Test an app.",
                             usage="choppy testapp <app_dir> <samples> [<args>]",
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    testapp.add_argument('app_dir', action='store', type=is_valid, help='The app path for your project.')
    testapp.add_argument('samples', action='store', type=is_valid, help='Path the samples file to validate.')
    testapp.add_argument('-p', '--project-name', action='store', type=is_valid_project_name,
                         required=True, help='Your project name.')
    testapp.add_argument('-D', '--dry-run', action='store_true', default=False,
                         help='Generate all workflow but skipping running.')
    testapp.add_argument('-l', '--label', action='append',
                         help='A key:value pair to assign. May be used multiple times.')
    testapp.add_argument('-S', '--server', action='store', choices=global_config.servers,
                         default='localhost', type=str, help='Choose a cromwell server.')
    testapp.add_argument('-f', '--force', action='store_true',
                         default=False, help='Force to overwrite files.')
    testapp.add_argument('-u', '--username', action='store', default=global_config.getuser(),
                         type=is_valid_label, help=argparse.SUPPRESS)
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
                                    description="Download file/directory from the specified bucket.",
                                    usage="choppy download <oss_link>/<oss_link_file> [<args>]",
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    download_files.add_argument('oss_link', action='store', help='OSS Link.', nargs='?', default=None)
    download_files.add_argument('-i', '--input-file', action='store', type=is_valid, help='OSS link file.')
    download_files.add_argument('-o', '--output-dir', action='store', default='.', type=is_valid, help='local_path.')
    download_files.add_argument('--include', action='store', help='Include Pattern of key, e.g., *.jpg')
    download_files.add_argument('--exclude', action='store', help='Exclude Pattern of key, e.g., *.txt')
    download_files.add_argument('-r', '--recursive', action='store_true', default=False, help='Operate recursively')
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
    samples.add_argument('-o', '--output', action='store', help='Samples file name.')
    samples.add_argument('-c', '--checkfile', action='store', help="Your samples file.")
    samples.add_argument('--no-default', action="store_true", default=False,
                         help="Don't list default keys that have been config in an app.")
    samples.set_defaults(func=call_samples)

    search = sub.add_parser(name='search',
                            description='Query cromwell for information on the submitted workflow.',
                            usage='choppy search [<args>]',
                            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    search.add_argument('-s', '--status', action='store', default=None, choices=global_config.status_list,
                        help='Print status for workflow to stdout')
    search.add_argument('-p', '--project-name', action="store", required=True, help="Project name",
                        type=is_valid_project_name)
    search.add_argument('--short-format', action="store_true", default=False,
                        help="Show by short format, if the option is not specified, show long format by default.")
    search.add_argument('-u', '--username', action='store', default=global_config.getuser(), type=is_valid_label,
                        help='Owner of workflows to query.')
    search.add_argument('-S', '--server', action='store', default="localhost", type=str, choices=global_config.servers,
                        help='Choose a cromwell server from {}'.format(global_config.servers))
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

    scaffold = sub.add_parser(name="scaffold",
                              description="Generate scaffold for a choppy app.",
                              usage="choppy scaffold",
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    scaffold.add_argument('-o', '--output-dir', action='store', default='./', help='Scaffold output directory.')
    scaffold.add_argument('-t', '--templ-name', action='store', choices=('report',),
                          help='Template name that you want to generate')
    scaffold.set_defaults(func=call_scaffold)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    # Fix bug1: user need to set choppy.conf before running choppy.
    # Fix bug2: Python argparse args has no attribute func
    # For more details: https://stackoverflow.com/a/54161510
    try:
        if args.func != call_config and args.func != call_version and\
           global_config.get_config_file() == global_config.get_conf_example(return_path=True):
            logger.fatal("Error: Not Found choppy.conf.\n\n"
                         "You need to run `choppy config` to generate "
                         "config template, modify it and copy to the one of directories %s.\n"
                         % global_config.get_conf_lst(filter='.*.example$'))
            sys.exit(exit_code.CONFIG_FILE_NOT_EXIST)
    except AttributeError:
        pass

    return args


def main():
    args = parse_args()

    if args.debug:
        loglevel = logging.DEBUG
    elif args.verbose:
        verbose = args.verbose
        # Configure logger for requested verbosity.
        if verbose >= 3:
            loglevel = logging.SPAM
        elif verbose >= 2:
            loglevel = logging.DEBUG
        elif verbose >= 1:
            loglevel = logging.VERBOSE
    elif args.quite:
        loglevel = logging.ERROR
    else:
        loglevel = global_config.get('general', 'log_level')

    user = global_config.getuser()
    # Get user's username so we can tag workflows and logs for them.
    log_dir = global_config.get_path('general', 'log_dir')
    if hasattr(args, 'project_name'):
        check_identifier(args.project_name)
        set_logger(args.project_name, loglevel=loglevel,
                   handler=args.handler, log_dir=log_dir)
    else:
        set_logger(user, loglevel=loglevel, handler=args.handler,
                   subdir=None, log_dir=log_dir)

    # Clean up the temp directory
    if global_config.get_boolean('general', 'clean_cache'):
        clean_temp(global_config.get_path('general', 'tmp_dir'))

    try:
        args.func(args)
    except AttributeError:
        print("Missing argument('%s --help' for help)" % sys.argv[0])
        print(description)


if __name__ == "__main__":
    sys.exit(main())
