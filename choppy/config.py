# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import re
import logging
import getpass
import configparser
from choppy import exit_code
from os.path import expanduser

logger = logging.getLogger(__name__)
DIRNAME = os.path.split(os.path.abspath(__file__))[0]

conf_file_example = os.path.join(os.path.dirname(DIRNAME), 'choppy',
                                 'conf', 'choppy.conf.example')
CONFIG_FILES = ['~/.choppy/choppy.conf', '/etc/choppy.conf']


def getconf(config_files):
    for f in config_files:
        try:
            loc = expanduser(f)
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


def check_oss_config():
    if access_key and access_secret and endpoint:
        return True
    else:
        logger.critical("You need to config oss section in choppy.conf")
        sys.exit(exit_code.OSS_NOT_CONFIG)


def check_server_config(host, port, username=None, password=None):
    if host and port:
        return True
    else:
        logger.critical("You need to config local/remote_* section in choppy.conf")
        sys.exit(exit_code.SERVER_NOT_CONFIG)


def get_workflow_db(workflow_db):
    if not workflow_db:
        return expanduser('~/.choppy/workflow.db')
    else:
        return workflow_db


def get_log_dir(log_dir):
    if not log_dir:
        return expanduser('~/.choppy')
    else:
        return log_dir


def get_app_dir(app_dir):
    if not app_dir:
        return expanduser('~/.choppy')
    else:
        return app_dir


def get_remote_info(section_name):
    try:
        remote_host = config.get(section_name, 'server')
        remote_port = config.get(section_name, 'port')
        username = config.get(section_name, 'username')
        password = config.get(section_name, 'password')
        return (remote_host, remote_port, username, password)
    except KeyError:
        logger.warn('No such key in %s' % section_name)
        sys.exit(exit_code.NO_SUCH_KEY_IN_SECTION)


def get_server_name(section_name):
    if re.match(r'remote_[\w]+', section_name):
        return section_name.split('_')[1]


def get_rlib_paths(dir):
    rlib_paths = []
    pattern = r'.*packrat/lib/[a-zA-Z0-9.\-_]+/[0-9]+.[0-9]+.[0-9]+$'
    for root, dirnames, filenames in os.walk(dir):
        if re.match(pattern, root):
            rlib_paths.append(root)
    return rlib_paths


config = configparser.ConfigParser()

config_files = CONFIG_FILES + [conf_file_example, ]
conf_path = getconf(config_files)

if conf_path:
    config.read(conf_path, encoding="utf-8")

# Global Config
run_states = ['Running', 'Submitted', 'QueuedInCromwell']
terminal_states = ['Failed', 'Aborted', 'Succeeded']
status_list = run_states + terminal_states
resource_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'resources'))
component_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'components'))

try:
    workflow_db = expanduser(config.get('general', 'workflow_db'))
    workflow_db = get_workflow_db(workflow_db)

    # Get default value if app_dir is None
    app_dir = os.path.join(expanduser(config.get('general', 'app_dir')), 'apps')
    app_dir = get_app_dir(app_dir)
    check_dir(app_dir)

    # tmp_dir
    general_section = config['general']
    tmp_dir = general_section.get('tmp_dir', '/tmp/choppy')

    # Email Config
    email_smtp_server = config.get('email', 'email_smtp_server')
    email_domain = config.get('email', 'email_domain')
    email_account = config.get('email', 'email_notification_account')
    sender_user = config.get('email', 'sender_user')
    sender_password = config.get('email', 'sender_password')

    # Server Config
    remote_sections = [section_name for section_name in config.sections()
                       if re.match(r'remote_[\w]+', section_name)]
    servers = ['localhost', ] + \
        [get_server_name(section_name) for section_name in remote_sections]

    def get_conn_info(server):
        if server == 'localhost':
            local_port = config.get('local', 'port')
            username = config.get('local', 'username')
            password = config.get('local', 'password')
            check_server_config('localhost', local_port)
            return 'localhost', local_port, (username, password)
        else:
            host, port, username, password = get_remote_info(
                'remote_%s' % server)
            check_server_config(host, port)
            return host, port, (username, password)

    # oss access_key and access_secret
    access_key = config.get('oss', 'access_key')
    access_secret = config.get('oss', 'access_secret')
    endpoint = config.get('oss', 'endpoint')
    check_oss_config()

    # repo
    base_url = config.get('repo', 'base_url')
    username = config.get('repo', 'username')
    password = config.get('repo', 'password')

    # Server
    server_data_dir = config.get('server', 'data_dir')
    server_host = config.get('server', 'host')
    server_port = config.get('server', 'port')

    # Log
    if sys.platform == 'darwin':
        log_dir = os.path.join(expanduser(config.get('general', 'log_dir')), 'logs')
        oss_bin = os.path.join(os.path.dirname(
            __file__), "lib", 'ossutilmac64')
    else:
        oss_bin = os.path.join(os.path.dirname(__file__), "lib", 'ossutil64')
        log_dir = os.path.join(expanduser(config.get('general', 'log_dir')), 'logs')

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

    # Plugin
    if config.has_section('plugin'):
        plugin_section = config['plugin']
        temp = '/tmp/choppy-media-extension'
        plugin_cache_dir = expanduser(plugin_section.get('cache_dir', temp))
        default_plugin_db = os.path.join(temp, 'plugin.db')
        plugin_db = expanduser(plugin_section.get('plugin_db', default_plugin_db))
        clean_cache = plugin_section.getboolean('clean_cache', True)
        enable_iframe = plugin_section.getboolean('enable_iframe', True)
        R_libs = plugin_section.get('r_lib_path', '~/.choppy/R_libs')
        # Set R_LIB_SITE
        R_libs = expanduser(R_libs)
        check_dir(R_libs)
        rlib_paths = get_rlib_paths(R_libs)
        os.environ['R_LIBS_SITE'] = ":".join(rlib_paths)

except (configparser.NoSectionError, configparser.NoOptionError, KeyError) as err:
    logger.critical('Parsing config file (%s) error.\n%s' %
                    (conf_path, str(err)))
    sys.exit(exit_code.CONFIG_FILE_FAILED)


def getuser():
    user = getpass.getuser().lower()
    matchObj = re.match(r'^[a-zA-Z0-9_]+$', user, re.M | re.I)
    if matchObj:
        return user
    else:
        logger.critical("Your account name is not valid. "
                        "Did not match the regex ^[a-zA-Z0-9_]+$")
        sys.exit(exit_code.USERNAME_NOT_VALID)
