# -*- coding:utf-8 -*-
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
from markdown2 import Markdown
from subprocess import Popen, PIPE
from jinja2 import Environment, FileSystemLoader
import choppy.config as c
from choppy.utils import BashColors
from choppy.cromwell import Cromwell
from choppy import exit_code
from choppy.exceptions import InValidApp

logger = logging.getLogger('choppy')

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


def is_valid_app(path):
    """
    Validate a directory path and verify the directory is an valid app directory. # noqa
    :param path: Path to a directory.
    :return: The path if it exists and is an app directory, otherwise raises an error. # noqa
    """
    inputs_path = os.path.join(path, 'inputs')
    wdl_path = os.path.join(path, 'workflow.wdl')
    dependencies = os.path.join(path, 'tasks')
    pathlist = [path, inputs_path, wdl_path, dependencies]
    for fpath in pathlist:
        if not os.path.exists(fpath):
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


def install_app_by_git(base_url, namespace, app_name, dest_dir='./',
                       version='', username=None, password=None):
    repo_url = "%s/%s/%s.git" % (base_url.strip('http://'),
                                 namespace, app_name)
    auth_repo_url = "http://%s@%s" % (username, repo_url)
    version = version if version is not 'latest' else 'master'
    cmd = ['git', 'clone', '-b', version, '--single-branch', '-q',
           '--progress', '--depth', '1', auth_repo_url, dest_dir]
    logger.debug('Git Repo Cmd: %s' % ''.join(cmd))
    proc = Popen(cmd, stdin=PIPE)
    proc.communicate(password)
    rc = proc.returncode
    if rc == 0:
        try:
            is_valid_app(dest_dir)
            BashColors.print_color('SUCCESS', "Install %s successfully." % app_name)
        except Exception as err:
            shutil.rmtree(dest_dir)
            BashColors.print_color('DANGER', "Install %s unsuccessfully." % app_name)
            BashColors.print_color('DANGER', str(err))
    else:
        BashColors.print_color('DANGER', "Install %s unsuccessfully." % app_name)
        sys.exit(exit_code.APP_INSTALL_FAILED)


def install_app(app_dir, choppy_app):
    parsed_dict = parse_app_name(choppy_app)
    if parsed_dict:
        base_url = c.base_url
        namespace = parsed_dict.get('namespace')
        app_name = parsed_dict.get('app_name')
        version = parsed_dict.get('version')
        app_dir_version = os.path.join(app_dir, "%s-%s" % (app_name, version))
        install_app_by_git(base_url, namespace, app_name, version=version,
                           dest_dir=app_dir_version, username=c.username,
                           password=c.password)
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
            choppy_app_handler.extractall(app_dir, dest_namelist)
            print("Install %s successfully." % app_name)
        else:
            raise InValidApp("Not a valid app.")


def uninstall_app(app_dir):
    answer = ''
    while answer.upper() not in ("YES", "NO", "Y", "N"):
        try:
            answer = raw_input("Enter Yes/No: ")  # noqa: python2
        except Exception:
            answer = input("Enter Yes/No: ")  # noqa: python3

        answer = answer.upper()
        if answer == "YES" or answer == "Y":
            shutil.rmtree(app_dir)
            print("Uninstall %s successfully." % os.path.basename(app_dir))
        elif answer == "NO" or answer == "N":
            print("Cancel uninstall %s." % os.path.basename(app_dir))
        else:
            print("Please enter Yes/No.")


def parse_samples(file):
    reader = csv.DictReader(open(file, 'rt'))
    dict_list = []

    for line in reader:
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
    if os.path.isdir(c.app_dir):
        files = os.listdir(c.app_dir)
        return files
    else:
        return []


def get_header(file):
    reader = csv.DictReader(open(file, 'rb'))

    return reader.fieldnames


def write(path, filename, data):
    with open(os.path.join(path, filename), 'w') as f:
        f.write(data)


def submit_workflow(wdl, inputs, dependencies, label, username=c.getuser(),
                    server='localhost', extra_options=None, labels_dict=None):
    labels_dict = kv_list_to_dict(
        label) if kv_list_to_dict(label) is not None else {}
    labels_dict['username'] = username
    host, port, auth = c.get_conn_info(server)
    cromwell = Cromwell(host=host, port=port, auth=auth)
    result = cromwell.jstart_workflow(wdl_file=wdl, json_file=inputs,
                                      dependencies=dependencies,
                                      extra_options=kv_list_to_dict(
                                          extra_options),
                                      custom_labels=labels_dict)
    result['port'] = cromwell.port

    return result


def kv_list_to_dict(kv_list):
    """
    Converts a list of kv pairs delimited with colon into a dictionary.
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
