# -*- coding: utf-8 -*-
"""
    choppy.utils
    ~~~~~~~~~~~~

    A general utility.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals

import os
import logging
import shutil
import psutil
import signal
import time
import coloredlogs
import verboselogs
from datetime import datetime
from random import Random as _Random
from choppy.check_utils import check_dir
import _thread

_allocate_lock = _thread.allocate_lock
_once_lock = _allocate_lock()
_name_sequence = None

logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger('choppy.utils')


def set_logger(log_name, loglevel, handler='stream', subdir="project_logs", log_dir='/tmp'):
    if subdir:
        project_logs = os.path.join(log_dir, "project_logs")
        check_dir(project_logs, skip=True)
        logfile = os.path.join(project_logs, '{}_choppy.log'.format(log_name))
    else:
        logfile = os.path.join(log_dir, '{}_{}_choppy.log'.format(str(time.strftime("%Y-%m-%d")), log_name))

    if handler != 'stream':
        fhandler = logging.FileHandler(logfile)
    else:
        fhandler = None

    if loglevel == logging.SPAM:
        fmt = '%(asctime)s - %(name)s(%(lineno)d) - %(levelname)s - %(message)s'
        coloredlogs.install(level=logging.DEBUG, fmt=fmt, stream=fhandler)
    elif loglevel == logging.DEBUG:
        fmt = '%(name)s - %(levelname)s - %(message)s'
        coloredlogs.install(level=loglevel, fmt=fmt, stream=fhandler)
    else:
        fmt = '%(message)s'
        coloredlogs.install(level=loglevel, fmt=fmt, stream=fhandler)


class CromwellConfig:
    config_schema = {
        "type": "object",
        "properties": {
            "bcs_root": {
                "type": "string"
            },
            "bcs_region": {
                "type": "string"
            },
            "bcs_access_id": {
                "type": "string"
            },
            "bcs_access_key": {
                "type": "string"
            },
            "bcs_endpoint": {
                "type": "string"
            },
            "auto_scale": {
                "type": "boolean"
            },
            "cluster": {
                "type": "string"
            },
            "vpc": {
                "type": "string"
            },
            "auto_release_job": {
                "type": "boolean"
            },
            "db_host": {
                "type": "string"
            },
            "db_name": {
                "type": "string"
            },
            "db_user": {
                "type": "string"
            },
            "db_passwd": {
                "type": "string"
            },
            "workflow_log_dir": {
                "type": "string"
            },
            "webservice_port": {
                "type": "number",
                "minimum": 1000,
                "maximum": 65535
            },
            "webservice_ipaddr": {
                "type": "string",
                "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$"
            }
        }
    }

    def __init__(self, cromwell_config):
        self.config = cromwell_config
        self.logger = logging.getLogger("choppy.utils.CromwellConfig")

    def validate(self):
        from jsonschema import validate, ValidationError, SchemaError
        try:
            valid_result = validate(self.config, self.config_schema, None)
            if valid_result is None:
                self.logger.success("Cromwell config is valid.")
        except Exception as e:
            if isinstance(e, ValidationError):
                self.logger.error("Cromwell config is invalid: {}".format(e.message))
            elif isinstance(e, SchemaError):
                self.logger.error("Cromwell config schema is invalid: {}".format(e.message))


def get_copyright(site_author='choppy'):
    year = datetime.now().year
    copyright = 'Copyright &copy; {} {}, ' \
                'Powered by <a href="http://choppy.3steps.cn">' \
                'Choppy</a>.'.format(year, site_author.title())
    return copyright


def copy_and_overwrite(from_path, to_path, is_file=False, ignore_errors=True, ask=False):
    if ask:
        answer = ''
        while answer.upper() not in ("YES", "NO", "Y", "N"):
            answer = input("Remove %s, Enter Yes/No: " % to_path)

            answer = answer.upper()
            if answer == "YES" or answer == "Y":
                ignore_errors = True
            elif answer == "NO" or answer == "N":
                ignore_errors = False
            else:
                print("Please enter Yes/No.")

    if ignore_errors:
        # TODO: rmtree is too dangerous
        if os.path.isfile(to_path):
            os.remove(to_path)

        if os.path.isdir(to_path):
            shutil.rmtree(to_path)

    try:
        if is_file and os.path.isfile(from_path):
            parent_dir = os.path.dirname(to_path)
            # Force to make directory when parent directory doesn't exist
            os.makedirs(parent_dir, exist_ok=True)
            shutil.copy2(from_path, to_path)
        elif os.path.isdir(from_path):
            shutil.copytree(from_path, to_path)
    except Exception as err:
        logger.warning('Copy %s to %s error: %s' % (from_path, to_path, str(err)))


def clean_files(folder, skip=True):
    if os.path.isdir(folder):
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                if not skip:
                    print(e)
    else:
        logger.debug("No such directory: %s" % folder)


def clean_temp(temp, dir=True):
    # Clean temp directory
    if dir:
        shutil.rmtree(temp, ignore_errors=True)
    else:
        try:
            os.remove(temp)
        except Exception:
            pass


class _RandomNameSequence:
    """An instance of _RandomNameSequence generates an endless
    sequence of unpredictable strings which can safely be incorporated
    into file names.  Each string is six characters long.  Multiple
    threads can safely use the same instance at the same time.
    _RandomNameSequence is an iterator."""

    characters = ("abcdefghijklmnopqrstuvwxyz" +  # noqa
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +  # noqa
                  "0123456789_")

    def __init__(self):
        self.mutex = _allocate_lock()
        self.normcase = os.path.normcase

    @property
    def rng(self):
        cur_pid = os.getpid()
        if cur_pid != getattr(self, '_rng_pid', None):
            self._rng = _Random()
            self._rng_pid = cur_pid
        return self._rng

    def __iter__(self):
        return self

    def next(self):
        m = self.mutex
        c = self.characters
        choose = self.rng.choice

        m.acquire()
        try:
            letters = [choose(c) for dummy in "123456"]
        finally:
            m.release()

        return self.normcase(''.join(letters))


def get_candidate_name():
    """Common setup sequence for all user-callable interfaces."""

    global _name_sequence
    if _name_sequence is None:
        _once_lock.acquire()
        try:
            if _name_sequence is None:
                _name_sequence = _RandomNameSequence()
        finally:
            _once_lock.release()
    return _name_sequence.next()


class Process:
    def __init__(self):
        self.logger = logging.getLogger('choppy.utils.Process')

    def get_process(self, process_id):
        try:
            p = psutil.Process(process_id)
            return p
        except psutil.NoSuchProcess:
            self.logger.warning('No such process: %s' % process_id)
            return None

    def clean_processs(self):
        process_id = os.getpid()
        process = self.get_process(process_id)
        if process:
            self.kill_proc_tree(process_id)

    def kill_proc_tree(self, pid, sig=signal.SIGTERM, include_parent=False,
                       timeout=3, on_terminate=None):
        """Kill a process tree (including grandchildren) with signal
        "sig" and return a (gone, still_alive) tuple.
        "on_terminate", if specified, is a callabck function which is
        called as soon as a child terminates.
        """
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        if include_parent:
            children.append(parent)
        children_pids = [child.pid for child in children]
        self.logger.debug('Kill process: %s and all children %s' % (pid, children_pids))
        try:
            for p in children:
                p.send_signal(sig)
            gone, alive = psutil.wait_procs(children, timeout=timeout,
                                            callback=on_terminate)
            return (gone, alive)
        except Exception as err:
            self.logger.debug('Kill all processes: %s' % str(err))
            return (None, None)


def clean_temp_files():
    choppy_temp = '/tmp/choppy'
    shutil.rmtree(choppy_temp, ignore_errors=True)
