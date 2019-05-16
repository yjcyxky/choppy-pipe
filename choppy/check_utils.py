# -*- coding: utf-8 -*-
"""
    choppy.check_utils
    ~~~~~~~~~~~~~~~~~~

    A utility for checking dir/file/label and so on.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import re
import argparse
import os
import zipfile
import logging


logger = logging.getLogger(__name__)


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


def is_valid_tag(tag_name):
    pattern = r'^[-\w]+:[-.\w]+$'
    match = re.search(pattern, tag_name)
    if match:
        return tag_name
    else:
        raise argparse.ArgumentTypeError(
            "Invalid tag_name: %s did not match the regex "
            "'^[-\\w]+:[-.\\w]+$.'. Such as shiny:0.1.0" % tag_name)


def is_valid_deps(deps):
    pattern = r'^[\w]+(,[-\w]+)*$'
    match = re.search(pattern, deps)
    if match:
        return deps
    else:
        raise argparse.ArgumentTypeError(
            "Invalid tag_name: %s did not match the regex "
            "'^[\\w]+(,[-\\w]+)*$'. Such as shiny,devtools" % deps)


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


def is_valid_oss_links(oss_link_lst):
    if isinstance(oss_link_lst, list):
        for oss_link in oss_link_lst:
            is_valid_oss_link(oss_link)


def check_dir(path, skip=False, force=True):
    """Check whether path exists.

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
    """Integrates with ArgParse to validate a file path.

    :param path: Path to a file.
    :return: The path if it exists, otherwise raises an error.
    """
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            ("{} is not a valid file/directory path.\n".format(path)))
    else:
        return path


def is_valid_zip(path):
    """Integrates with argparse to validate a file path and verify that the file is a zip file.

    :param path: Path to a file.
    :return: The path if it exists and is a zip file, otherwise raises an error.
    """
    is_valid(path)
    if not zipfile.is_zipfile(path):
        e = "{} is not a valid zip file.\n".format(path)
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def is_valid_zip_or_dir(path):
    """Integrates with argparse to validate a file path and verify that the file is a zip file.

    :param path: Path to a file.
    :return: The path if it exists and is a zip file, otherwise raises an error.
    """
    if os.path.isdir(path):
        return path

    if not zipfile.is_zipfile(path):
        e = "{} is not a valid zip file.\n".format(path)
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def is_shiny_app(path):
    """Check if path is a valid shiny app.
    """
    if os.path.basename(path) == '.':
        raise argparse.ArgumentTypeError("Shiny app can't be current directory.(%s)" % path)
    elif not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Shiny app must be a directory "
                                         "that contains shiny app files.(%s)" % path)

    app_file = os.path.join(path, 'app.R')
    ui_file = os.path.join(path, 'ui.R')
    server_file = os.path.join(path, 'server.R')
    if not os.path.isfile(app_file) and not (os.path.isfile(ui_file) and os.path.isfile(server_file)):
        raise argparse.ArgumentTypeError("Shiny app must be a directory that "
                                         "contains app.R or (ui.R and server.R).")

    return path


def check_plugin():
    try:
        import mk_media_extension  # noqa
        return True
    except ImportError:
        msg = 'Use `pip install mk_media_extension` to support report plugin.\n'
        logger.warning('Report plugin is not yet supported by choppy.\n%s' % msg)
        return False


def check_customized_mkdocs():
    try:
        from mkdocs.commands.serve import dev_serve  # noqa
        return True
    except ImportError:
        msg = 'Please contact choppy team to get the customized version.\n'
        logger.warning('Official mkdocs is not yet supported by choppy.\n%s' % msg)
        return False
