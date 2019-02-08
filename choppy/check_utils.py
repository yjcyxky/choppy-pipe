# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import re
import argparse
import os
import zipfile
import logging
from jinja2 import Environment, meta
from choppy.app_utils import AppDefaultVar


logger = logging.getLogger('choppy')


def is_valid_url(url):
    pattern = r'(https?)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]'
    if re.match(pattern, url):
        return True
    else:
        return False


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


def check_dir(path, skip=False, force=True):
    """
    Check whether path exists.
    :param path: directory path.
    :param skip: Boolean, Raise exception when skip is False and directory exists.
    :param force: Boolean, Force to make directory when directory doesn't exist?
    :return:
    """
    if not os.path.isdir(path):
        if force:
            os.makedirs(path)
        else:
            raise Exception("%s doesn't exist." % path)
    elif not skip:
        raise Exception("%s exists" % path)


def is_valid(path):
    """
    Integrates with ArgParse to validate a file path.
    :param path: Path to a file.
    :return: The path if it exists, otherwise raises an error.
    """
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            ("{} is not a valid file/directory path.\n".format(path)))
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
