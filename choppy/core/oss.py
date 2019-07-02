# -*- coding: utf-8 -*-
"""
    choppy.core.oss
    ~~~~~~~~~~~~~~~

    Module to interact with AliCloud ossutils.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import os
import sys
import logging
from choppy.config import get_global_config
from subprocess import CalledProcessError, PIPE, Popen

global_config = get_global_config()
logger = logging.getLogger(__name__)


def run_copy_files(first_path, second_path, include=None, exclude=None,
                   recursive=True, silent=False):
    if isinstance(first_path, list):
        for path in first_path:
            logger.info('\nDownloading %s' % path)
            oss_copy_func(path, second_path, include=include, exclude=exclude,
                          recursive=recursive, silent=silent)
    elif isinstance(first_path, str):
        oss_copy_func(first_path, second_path, include=include, exclude=exclude,
                      recursive=recursive, silent=silent)


def oss_copy_func(first_path, second_path, include=None, exclude=None,
                  recursive=True, silent=False):
    """Call ossutil and copy files from one place to anothers.

    :param: first_path: source path.
    :type: first_path: str
    :param: second_path: destination path.
    :type: second_path: str
    :param: include: include which files.
    :type: include: list
    :param: exclude: which files.
    :type: exclude: list
    :param: recursive: copy files recursively or not.
    :type: recursive: bool
    :param: silent: no any exception and warning, just let it go.
    :type: silent: bool
    :return:
    """
    log_dir = global_config.get_path('general', 'log_dir')
    output_dir = os.path.join(log_dir, 'oss_outputs')
    checkpoint_dir = os.path.join(log_dir, 'oss_checkpoint')

    try:
        oss_bin = global_config.get('oss', 'oss_bin')
        if not oss_bin:
            oss_bin_name = 'ossutil64' if os.uname().sysname == 'Linux' else 'ossutilmac64'
            oss_bin = os.path.join(global_config.resource_dir, 'lib', oss_bin_name)
        access_key = global_config.get('oss', 'access_key')
        access_secret = global_config.get('oss', 'access_secret')
        endpoint = global_config.get('oss', 'endpoint')
        shell_cmd = [oss_bin, "cp", "-u", "-i", access_key, "-k", access_secret,
                     "--output-dir=%s" % output_dir, "--checkpoint-dir=%s" % checkpoint_dir,
                     "-e", endpoint]
        if include:
            shell_cmd.extend(["--include", include])

        if exclude:
            shell_cmd.extend(["--exclude", exclude])

        if recursive:
            shell_cmd.extend(["-r"])

        shell_cmd.extend([first_path, second_path])

        logger.debug('Running Command: %s' % ' '.join(shell_cmd))
        process = Popen(shell_cmd, stdout=PIPE)
        while process.poll() is None:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output and not silent:
                print(output.strip().decode())
                sys.stdout.flush()
            process.poll()
    except CalledProcessError as e:
        logger.critical(e)
        logger.critical("access_key/access_secret or oss_link is not valid.")
