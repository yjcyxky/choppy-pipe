# -*- coding: utf-8 -*-
"""
    choppy.core.app_utils
    ~~~~~~~~~~~~~~~~~~~~~

    App Utility.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import json
import os
import sys
import re
import csv
import uuid
import shutil
import zipfile
import logging
import verboselogs
from choppy.config import get_global_config
from markdown2 import Markdown
from subprocess import Popen, PIPE, check_output
from jinja2 import Environment, FileSystemLoader, meta
from choppy.core.cromwell import Cromwell
from choppy import exit_code
from choppy.exceptions import (InValidApp, AppInstallationFailed,
                               AppUnInstallationFailed)

global_config = get_global_config()
logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger(__name__)

try:
    basestring = basestring  # noqa: python2
except Exception:
    basestring = str  # noqa: python3


class AppDefaultVar:
    def __init__(self, app_path):
        self.app_path = app_path
        self.default = os.path.join(self.app_path, 'defaults')
        self.default_vars = self._parse()

    def _parse(self):
        if os.path.isfile(self.default):
            with open(self.default, 'r') as f:
                vars = json.load(f)
                return vars
        else:
            return dict()

    def get(self, key):
        return self.default_vars.get(key)

    def has_key(self, key):
        if self.default_vars.get(key):
            return True
        else:
            return False

    def diff(self, key_list):
        keys = self.default_vars.keys()
        # key_list need to have more key.
        diff_sets = set(key_list) - set(keys)
        return diff_sets

    def set_default_value(self, key, value):
        self.default_vars.update({key: value})

    def set_default_vars(self, vars_dict):
        self.default_vars.update(vars_dict)

    def get_default_vars(self, key_list):
        keys = self.default_vars.keys()
        inter_keys = list(set(key_list).intersection(set(keys)))
        return inter_keys

    def show_default_value(self, key_list=list()):
        if len(key_list) > 0:
            inter_keys = self.get_default_vars(key_list)
        else:
            inter_keys = self.default_vars.keys()

        results = dict()
        for key in inter_keys:
            results.update({
                key: self.get(key)
            })

        return results

    def save(self):
        with open(self.default, 'w') as f:
            json.dump(self.default_vars, f, indent=2, sort_keys=True)


def is_valid_app(path, ignore_error=False):
    """Validate a directory path and verify the directory is an valid app directory. # noqa

    :param path: Path to a directory.
    :return: The path if it exists and is an app directory, otherwise raises an error. # noqa
    """
    inputs_path = os.path.join(path, 'inputs')
    wdl_path = os.path.join(path, 'workflow.wdl')
    dependencies = os.path.join(path, 'tasks')
    pathlist = [path, inputs_path, wdl_path, dependencies]
    for fpath in pathlist:
        if not os.path.exists(fpath):
            if ignore_error:
                return False
            else:
                raise InValidApp("%s is not a valid app.\n" %
                                 os.path.basename(path))
    return True


def parse_app_name(app_name):
    pattern = r'^([-\w]+)/([-\w]+)(:[-.\w]+)?$'
    match = re.search(pattern, app_name)
    if match:
        namespace, app_name, version = match.groups()
        if version:
            version = version.strip(':')
        else:
            version = 'latest'

        return {
            "namespace": namespace,
            "app_name": app_name,
            "version": version
        }
    else:
        return False


def dfs_get_zip_file(input_path, result):
    files = os.listdir(input_path)
    for file in files:
        filepath = os.path.join(input_path, file)
        if os.path.isdir(filepath):
            dfs_get_zip_file(filepath, result)
        else:
            result.append(filepath)


def zip_path(input_path, output_path):
    f = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)
    filelists = []
    dfs_get_zip_file(input_path, filelists)
    for file in filelists:
        f.write(file)
    f.close()
    return output_path


def zip_path_by_ext_program(input_path, output_path):
    cmd = ['zip', '-r', '-q', output_path, input_path]
    logger.debug('ZIP: Working Directory %s, CMD: %s' % (os.getcwd(), cmd))
    proc = Popen(cmd, stdin=PIPE)
    proc.communicate()


def check_cmd(command):
    for cmdpath in os.environ['PATH'].split(':'):
        if os.path.isdir(cmdpath) and command in os.listdir(cmdpath):
            return True

    return False


def generate_dependencies_zip(dependencies_path):
    # Fix Bug: When Changing Directory, you need a abs path.
    dependencies_path = os.path.abspath(dependencies_path)
    previous_workdir = os.getcwd()
    par_dir = str(uuid.uuid1())
    workdir = os.path.join('/', 'tmp', par_dir)
    os.mkdir(workdir)
    zip_output = os.path.join('/', 'tmp', par_dir, 'tasks.zip')

    os.chdir(workdir)
    # Fix bug:
    # Need two levels or one level?
    # dest_path = os.path.join('tasks', 'tasks')
    dest_path = 'tasks'
    shutil.copytree(dependencies_path, dest_path)

    # 外部命令
    if check_cmd('zip'):
        zip_path_by_ext_program('tasks', zip_output)
    else:
        # TODO: Fix the Bug
        # Python zipfile generate a zip that are version 2.0;
        # But Cromwell need a zip that are version 1.0;
        zip_path(dest_path, zip_output)

    os.chdir(previous_workdir)
    return zip_output


def get_version(app_dir):
    try:
        app_name = get_remote_url(app_dir)
    except Exception:
        logger.warn("Git's version is too low, please upgrade it.")
        app_name = ""

    return {
        "app_name": app_name,
        "commit_id": get_app_commit_id(app_dir),
        "version": get_app_tag(app_dir)
    }


def get_remote_url(app_dir):
    output = check_output(['git', 'remote', 'get-url', 'origin'], cwd=app_dir, universal_newlines=True).strip()
    return output


def get_app_commit_id(app_dir):
    output = check_output(['git', 'rev-parse', 'HEAD'], cwd=app_dir, universal_newlines=True).strip()
    return output


def get_app_tag(app_dir):
    output = check_output(['git', 'tag'], cwd=app_dir, universal_newlines=True).strip()
    return output


def install_app_by_git(base_url, namespace, app_name, dest_dir='./',
                       version='', username=None, password=None,
                       is_terminal=True):
    from urllib.parse import quote_plus
    repo_url = "%s/%s/%s.git" % (base_url.strip('http://'),
                                 namespace, app_name)
    # Fix bug: username with @
    # Need to URL encode the @ as %40: https://stackoverflow.com/a/38199336
    # Urlencode a string: https://stackoverflow.com/a/9345102
    auth_repo_url = "http://%s@%s" % (quote_plus(username), repo_url)
    version = version if version != 'latest' else 'master'
    # How to clone a specific tag with git: https://stackoverflow.com/a/31666461
    cmd = ['git', 'clone', '-b', version, '--single-branch', '-q',
           '--progress', '--depth', '1', auth_repo_url, dest_dir]
    logger.debug('Git Repo Cmd: %s' % ' '.join(cmd))
    proc = Popen(cmd, stdin=PIPE)
    proc.communicate(password)
    rc = proc.returncode
    if rc == 0:
        try:
            is_valid_app(dest_dir)
            logger.success("Install %s successfully." % app_name)
            msg = "Install %s successfully." % app_name
            failed = False
        except Exception as err:
            shutil.rmtree(dest_dir)
            logger.critical(str(err))
            msg = str(err)
            failed = True
    else:
        if os.path.exists(dest_dir):
            msg = 'The app already exists.'
            failed = True
        else:
            msg = 'Unkown error, Please retry later. Maybe not found or network error.'
            failed = True

    if failed:
        logger.critical("Install %s unsuccessfully." % app_name)
        if is_terminal:
            sys.exit(exit_code.APP_INSTALL_FAILED)
        else:
            raise AppInstallationFailed(msg)
    else:
        return msg


def get_app_root_dir():
    app_root_dir = global_config.get_path('general', 'app_root_dir')
    if not os.path.isdir(app_root_dir):
        os.makedirs(app_root_dir)
    return app_root_dir


def install_app(app_root_dir, choppy_app, is_terminal=True):
    parsed_dict = parse_app_name(choppy_app)
    if parsed_dict:
        base_url = global_config.get('repo', 'base_url')
        username = global_config.get('repo', 'username')
        # Best way to convert string to bytes in Python 3?
        # https://stackoverflow.com/a/17500651
        password = str.encode(global_config.get('repo', 'password'))
        namespace = parsed_dict.get('namespace')
        app_name = parsed_dict.get('app_name')
        version = parsed_dict.get('version')
        app_dir_version = os.path.join(app_root_dir, "%s/%s-%s" % (namespace, app_name, version))
        install_app_by_git(base_url, namespace, app_name, version=version,
                           dest_dir=app_dir_version, username=username,
                           password=password, is_terminal=is_terminal)
    else:
        app_name = os.path.splitext(os.path.basename(choppy_app))[0]
        dest_namelist = [os.path.join(app_name, 'inputs'),
                         os.path.join(app_name, 'workflow.wdl')]

        tasks_dirpath = os.path.join(app_name, 'tasks')
        choppy_app_handler = zipfile.ZipFile(choppy_app)
        namelist = choppy_app_handler.namelist()

        # Only wdl files.
        tasks_namelist = [name for name in namelist
                          if re.match('%s/.*.wdl$' % tasks_dirpath, name)]
        dest_namelist.extend(tasks_namelist)

        def check_app(dest_namelist, namelist):
            for file in dest_namelist:
                if file in namelist:
                    continue
                else:
                    return False
            return True

        if check_app(dest_namelist, namelist):
            choppy_app_handler.extractall(app_root_dir, dest_namelist)
            logger.success("Install %s successfully." % app_name)
        else:
            raise InValidApp("Not a valid app.")


def uninstall_app(app_dir, is_terminal=True):
    if not os.path.exists(app_dir):
        logger.debug("App root directory: %s" % os.path.dirname(app_dir))
        msg = 'No such app: %s' % os.path.basename(app_dir)
        logger.error(msg)
        raise AppUnInstallationFailed(msg)

    if is_terminal:
        answer = ''
        while answer.upper() not in ("YES", "NO", "Y", "N"):
            answer = input("Enter Yes/No: ")

            answer = answer.upper()
            if answer == "YES" or answer == "Y":
                shutil.rmtree(app_dir)
                logger.success("Uninstall %s successfully." % os.path.basename(app_dir))
            elif answer == "NO" or answer == "N":
                logger.warning("Cancel uninstall %s." % os.path.basename(app_dir))
            else:
                logger.info("Please enter Yes/No.")
    else:
        shutil.rmtree(app_dir)
        msg = "Uninstall %s successfully." % os.path.basename(app_dir)
        logger.success(msg)
        return msg


def parse_samples(file):
    dict_list = []

    try:
        content = json.load(open(file, 'rt'))
        if type(content) == dict:
            dict_list = [content, ]
        elif type(content) == list:
            dict_list = content
    except Exception as err:
        reader = csv.DictReader(open(file, 'rt'))
        dict_list = []

        for line in reader:
            header = line.keys()
            if None in header or "" in header:
                print("CSV file is not qualified.")
                sys.exit(2)
            dict_list.append(line)

    return dict_list


def render_app(app_path, template_file, data):
    env = Environment(loader=FileSystemLoader(app_path))
    template = env.get_template(template_file)
    return template.render(**data)


def read_file_as_string(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read()
    else:
        return ''


def write_string_as_file(filepath, string):
    with open(filepath, 'w') as f:
        f.write(string)


def render_readme(app_path, app_name, readme="README.md",
                  format="html", output=None):
    readme_path = os.path.join(app_path, app_name, readme)
    if os.path.exists(readme_path):
        if format.lower() == 'html':
            markdown_text = read_file_as_string(readme_path)
            markdowner = Markdown()
            html = markdowner.convert(markdown_text)
            if output:
                write_string_as_file(output, html)
                return 'Save manual to %s' % output
            else:
                return html
        else:
            markdown_text = read_file_as_string(readme_path)
            if output:
                write_string_as_file(output, markdown_text)
                return 'Save manual to %s' % output
            else:
                return markdown_text
    else:
        return 'No manual entry for %s' % app_name


def listapps():
    app_root_dir = get_app_root_dir()
    apps = []
    if os.path.isdir(app_root_dir):
        # backwards compatibility:
        # 1. No owner name as a namespace.
        # 2. User owner name as a namespace.
        for dir in os.listdir(app_root_dir):
            abs_dir = os.path.join(app_root_dir, dir)
            if is_valid_app(abs_dir, ignore_error=True):
                apps.append(dir)
            elif os.path.isdir(abs_dir):
                for subdir in os.listdir(abs_dir):
                    abs_dir_subdir = os.path.join(abs_dir, subdir)
                    if is_valid_app(abs_dir_subdir, ignore_error=True):
                        apps.append('%s/%s' % (dir, subdir))
    return apps


def get_header(file):
    reader = csv.DictReader(open(file, 'rb'))

    return reader.fieldnames


def write(path, filename, data):
    with open(os.path.join(path, filename), 'w') as f:
        f.write(data)


def submit_workflow(wdl, inputs, dependencies, label, username=None,
                    server='localhost', extra_options=None, labels_dict=None):
    labels_dict = kv_list_to_dict(
        label) if kv_list_to_dict(label) is not None else {}
    if username is None:
        username = global_config.getuser()
    labels_dict['username'] = username
    section_name = 'remote_%s' % server if server != 'localhost' else 'local'
    host, port, auth = global_config.get_conn_info(server, section_name)
    cromwell = Cromwell(host=host, port=port, auth=auth)
    result = cromwell.jstart_workflow(wdl_file=wdl, json_file=inputs,
                                      dependencies=dependencies,
                                      extra_options=kv_list_to_dict(
                                          extra_options),
                                      custom_labels=labels_dict)
    result['port'] = cromwell.port

    return result


def kv_list_to_dict(kv_list):
    """Converts a list of kv pairs delimited with colon into a dictionary.

    :param kv_list: kv list: ex ['a:b', 'c:d', 'e:f']
    :return: a dict, ex: {'a': 'b', 'c': 'd', 'e': 'f'}
    """
    new_dict = dict()
    if kv_list:
        for item in kv_list:
            (key, val) = item.split(':')
            new_dict[key] = val
        return new_dict
    else:
        return None


def parse_json(instance):
    if isinstance(instance, dict):
        for key, value in instance.items():
            # str is not supported by python2.7+
            # basestring is not supported by python3+
            if isinstance(value, basestring):
                try:
                    instance[key] = json.loads(value)
                except ValueError:
                    pass
            elif isinstance(value, dict):
                instance[key] = parse_json(instance[key])
    elif isinstance(instance, list):
        for idx, value in enumerate(instance):
            instance[idx] = parse_json(value)

    return instance


def get_all_variables(app_dir, no_default=False):
    inputs_variables = get_vars_from_app(app_dir, 'inputs', no_default=no_default)
    workflow_variables = get_vars_from_app(app_dir, 'workflow.wdl', no_default=no_default)
    variables = list(set(list(inputs_variables) + list(workflow_variables) + ['sample_id', ]))
    if 'project_name' in variables:
        variables.remove('project_name')

    return variables


def get_vars_from_app(app_path, template_file, no_default=False):
    env = Environment()
    template = os.path.join(app_path, template_file)
    with open(template) as f:
        templ_str = f.read()
        ast = env.parse(templ_str)
        variables = meta.find_undeclared_variables(ast)

        if no_default:
            app_default_var = AppDefaultVar(app_path)
            diff_variables = app_default_var.diff(variables)
            return diff_variables

    return variables


def check_variables(app_path, template_file, line_dict=None, header_list=None,
                    no_default=False):
    variables = get_vars_from_app(app_path, template_file)
    variables = list(variables) + ['sample_id', ]
    if no_default:
        app_default_var = AppDefaultVar(app_path)
        variables = app_default_var.diff(variables)

    for var in variables:
        if line_dict:
            if var not in line_dict.keys() and var != 'project_name':
                logger.warn('%s not in samples header.' % var)
                return False
        elif header_list:
            if var not in header_list and var != 'project_name':
                logger.warn('%s not in samples header.' % var)
                return False

    return True
