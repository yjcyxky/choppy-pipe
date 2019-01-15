# -*- coding:utf-8 -*-
import os
import sys
import re
import logging
import getpass
import configparser
import subprocess
from . import exit_code
from .bash_colors import BashColors

DIRNAME = os.path.split(os.path.abspath(__file__))[0]


conf_file_example = os.path.join(os.path.dirname(DIRNAME), 'choppy',
                                 'conf', 'choppy.conf.example')
CONFIG_FILES = ['~/.choppy/choppy.conf', '/etc/choppy.conf']


def getconf(config_files):
    for f in config_files:
        try:
            loc = os.path.expanduser(f)
        except KeyError:
            # os.path.expanduser can fail when $HOME is undefined and
            # getpwuid fails. See http://bugs.python.org/issue20164 &
            # https://github.com/kennethreitz/requests/issues/1846
            return

        if os.path.exists(loc):
            return loc


def check_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def print_color(color, msg):
    print(color + msg + BashColors.ENDC)


def check_oss_config():
    if access_key and access_secret and endpoint:
        return True
    else:
        print_color(BashColors.FAIL,
                    "You need to config oss section in choppy.conf")
        sys.exit(exit_code.OSS_NOT_CONFIG)


def check_server_config():
    if local_port or (remote_host and remote_port):
        return True
    else:
        print_color(BashColors.FAIL,
                    "You need to config local/remote section in choppy.conf")
        sys.exit(exit_code.SERVER_NOT_CONFIG)


def get_workflow_db(workflow_db):
    if not workflow_db:
        return os.path.expanduser('~/.choppy/workflow.db')
    else:
        return workflow_db


def get_log_dir(log_dir):
    if not log_dir:
        return os.path.expanduser('~/.choppy')
    else:
        return log_dir


def get_app_dir(app_dir):
    if not app_dir:
        return os.path.expanduser('~/.choppy')
    else:
        return app_dir


config = configparser.ConfigParser()

config_files = CONFIG_FILES + [conf_file_example, ]
conf_path = getconf(config_files)

if conf_path:
    config.read(conf_path, encoding="utf-8")

# Global Config
servers = ['localhost', 'remote']
run_states = ['Running', 'Submitted', 'QueuedInCromwell']
terminal_states = ['Failed', 'Aborted', 'Succeeded']
status_list = run_states + terminal_states
resource_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'resources'))

workflow_db = os.path.expanduser(config.get('general', 'workflow_db'))
workflow_db = get_workflow_db(workflow_db)

# Get default value if app_dir is None
app_dir = os.path.join(os.path.expanduser(
    config.get('general', 'app_dir')), 'apps')
app_dir = get_app_dir(app_dir)
check_dir(app_dir)

# Email Config
email_smtp_server = config.get('email', 'email_smtp_server')
email_domain = config.get('email', 'email_domain')
email_account = config.get('email', 'email_notification_account')
sender_user = config.get('email', 'sender_user')
sender_password = config.get('email', 'sender_password')

# Server Config
local_port = config.get('local', 'port')
remote_host = config.get('remote', 'server')
remote_port = config.get('remote', 'port')
username = config.get('auth', 'username')
password = config.get('auth', 'password')

if username and password:
    auth = (username, password)
else:
    auth = None

check_server_config()


def get_conn_info(server):
    if server == 'localhost':
        return 'localhost', local_port, auth
    elif server == 'remote':
        return remote_host, remote_port, auth


# oss access_key and access_secret
access_key = config.get('oss', 'access_key')
access_secret = config.get('oss', 'access_secret')
endpoint = config.get('oss', 'endpoint')
check_oss_config()


# repo
base_url = config.get('repo', 'base_url')
username = config.get('repo', 'username')
password = config.get('repo', 'password')

# Log
if sys.platform == 'darwin':
    log_dir = os.path.join(os.path.expanduser(
        config.get('general', 'log_dir')), 'logs')
    oss_bin = os.path.join(os.path.dirname(__file__), "lib", 'ossutilmac64')
else:
    oss_bin = os.path.join(os.path.dirname(__file__), "lib", 'ossutil64')
    log_dir = os.path.join(os.path.expanduser(
        config.get('general', 'log_dir')), 'logs')

log_dir = get_log_dir(log_dir)
check_dir(log_dir)

log_level = config.get('general', 'log_level').upper()

if log_level == 'DEBUG':
    log_level = logging.DEBUG
elif log_level == 'INFO':
    log_level = logging.INFO
elif log_level == 'WARNING':
    log_level = logging.WARNING
elif log_level == 'CRITICAL':
    log_level == logging.CRITICAL
elif log_level == 'FATAL':
    log_level == logging.FATAL
else:
    log_level = logging.DEBUG


def getuser():
    user = getpass.getuser().lower()
    matchObj = re.match(r'^[a-zA-Z0-9_]+$', user, re.M | re.I)
    if matchObj:
        return user
    else:
        print_color(BashColors.FAIL,
                    "Your account name is not valid. Did not match the regex ^[a-zA-Z0-9_]+$")
        sys.exit(exit_code.USERNAME_NOT_VALID)
