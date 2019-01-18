# -*- coding:utf-8 -*-
import re
import argparse
import os
import zipfile
import logging
from jinja2 import Environment, meta


logger = logging.getLogger('choppy')


def is_valid_app_name(app_name):
    """
    Example(app_name):
        'choppy/choppy:v0.1.2', 'choppy/choppyv0.1.2', 'choppy/choppy'
    """
    try:
        is_valid_zip(app_name)
        return app_name
    except argparse.ArgumentTypeError:
        pattern = r'^([-\w]+)/([-\w]+)(:[-.\w]+)?$'
        match = re.search(pattern, app_name)
        if match:
            return app_name
        else:
            raise argparse.ArgumentTypeError(
                "Invalid app_name: %s did not match the regex "
                "'^([-\\w]+)/([-\\w]+)(:[-.\\w]+)?$'" % app_name)


def get_vars_from_app(app_path, template_file):
    env = Environment()
    template = os.path.join(app_path, template_file)
    with open(template) as f:
        templ_str = f.read()
        ast = env.parse(templ_str)
        variables = meta.find_undeclared_variables(ast)

    return variables


def check_variables(app_path, template_file, line_dict=None, header_list=None):
    variables = get_vars_from_app(app_path, template_file)
    variables = list(variables) + ['sample_id', ]
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


def check_identifier(identifier):
    matchObj = re.match(r'([a-z0-9]*[-a-z0-9]*[a-z0-9])?.',
                        identifier, re.M | re.I)
    if matchObj:
        return True
    else:
        return False


def is_valid_label(label):
    matchObj = re.match(r'([a-z0-9]*[-a-z0-9]*[a-z0-9])?.', label, re.M | re.I)
    if matchObj:
        return label
    else:
        raise argparse.ArgumentTypeError(
            "Invalid label: %s did not match the regex "
            "([a-z0-9]*[-a-z0-9]*[a-z0-9])?." % label)


def is_valid_project_name(project_name):
    matchObj = re.match(r'([a-z0-9]*[_a-z0-9]*[a-z0-9])?.',
                        project_name, re.M | re.I)
    if matchObj:
        return project_name
    else:
        raise argparse.ArgumentTypeError(
            "Invalid Project Name: %s did not match the regex "
            "([a-z0-9]*[_a-z0-9]*[a-z0-9])?." % project_name)


def is_valid_oss_link(path):
    matchObj = re.match(r'^oss://[a-zA-Z0-9\-_\./]+$', path, re.M | re.I)
    if matchObj:
        return path
    else:
        raise argparse.ArgumentTypeError(
            "%s is not a valid oss link.\n" % path)


def check_dir(path, skip=None, force=True):
    if not os.path.isdir(path):
        if force:
            os.makedirs(path)
        else:
            raise Exception("%s doesn't exist." % path)
    elif not skip:
        raise Exception("%s exists" % path)


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
            raise Exception("%s is not a valid app.\n" %
                            os.path.basename(path))
    return True


def is_valid(path):
    """
    Integrates with ArgParse to validate a file path.
    :param path: Path to a file.
    :return: The path if it exists, otherwise raises an error.
    """
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            ("{} is not a valid file path.\n".format(path)))
    else:
        return path


def is_valid_zip(path):
    """
    Integrates with argparse to validate a file path and verify that the file is a zip file. # noqa
    :param path: Path to a file.
    :return: The path if it exists and is a zip file, otherwise raises an error. # noqa
    """
    is_valid(path)
    if not zipfile.is_zipfile(path):
        e = "{} is not a valid zip file.\n".format(path)
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def is_valid_zip_or_dir(path):
    """
    Integrates with argparse to validate a file path and verify that the file is a zip file. # noqa
    :param path: Path to a file.
    :return: The path if it exists and is a zip file, otherwise raises an error. # noqa
    """
    if os.path.isdir(path):
        return path

    if not zipfile.is_zipfile(path):
        e = "{} is not a valid zip file.\n".format(path)
        raise argparse.ArgumentTypeError(e)
    else:
        return path
