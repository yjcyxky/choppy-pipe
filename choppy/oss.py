# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import logging
import choppy.config as c
from subprocess import CalledProcessError, PIPE, Popen
from choppy.utils import print_obj

logger = logging.getLogger(__name__)


def run_copy_files(first_path, second_path, include=None, exclude=None, recursive=True, silent=False):  # noqa
    output_dir = os.path.join(c.log_dir, 'oss_outputs')
    checkpoint_dir = os.path.join(c.log_dir, 'oss_checkpoint')

    try:
        shell_cmd = [c.oss_bin, "cp", "-u", "-i", c.access_key, "-k", c.access_secret,  # noqa
                     "--output-dir=%s" % output_dir, "--checkpoint-dir=%s" % checkpoint_dir,  # noqa
                     "-e", c.endpoint]
        if include:
            shell_cmd.extend(["--include", include])

        if exclude:
            shell_cmd.extend(["--exclude", exclude])

        if recursive:
            shell_cmd.extend(["-r"])

        shell_cmd.extend([first_path, second_path])
        process = Popen(shell_cmd, stdout=PIPE)
        while process.poll() is None:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output and not silent:
                print_obj(output.strip())
                sys.stdout.flush()
            process.poll()
    except CalledProcessError as e:
        logger.critical(e)
        logger.critical("access_key/access_secret or oss_link is not valid.")
