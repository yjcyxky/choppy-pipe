import os
import sys
import logging
import configparser
from itertools import chain, imap

DIRNAME = os.path.split(os.path.abspath(__file__))[0]

CONFIG_FILES = ['~/.choppy.conf', 
                os.path.join(os.path.dirname(DIRNAME), 'choppy', 'conf', 'choppy.conf'), 
                '/etc/choppy.conf']

def getconf():
    for f in CONFIG_FILES:
        try:
            loc = os.path.expanduser(f)
        except KeyError:
            # os.path.expanduser can fail when $HOME is undefined and
            # getpwuid fails. See http://bugs.python.org/issue20164 &
            # https://github.com/kennethreitz/requests/issues/1846
            return

        if os.path.exists(loc):
            return loc

config = configparser.ConfigParser()

def check_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)

conf_path = getconf()
if conf_path:
    config.read(conf_path, encoding="utf-8")
else:
    raise Exception("Not Found choppy.conf in %s" % CONFIG_FILES)

servers = ['localhost', ]

resource_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'resources')
run_states = ['Running', 'Submitted', 'QueuedInCromwell']
terminal_states = ['Failed', 'Aborted', 'Succeeded']

workflow_db = os.path.expanduser(config.get('general', 'workflow_db'))
app_dir = os.path.join(os.path.expanduser(config.get('general', 'app_dir')), 'apps')

# check and make app_dir
check_dir(app_dir)

# localhost port
local_port = config.get('local', 'local_port')

# directory for generated temporary files (ex: for making fofns)
temp_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'generated')

if sys.platform == 'win32':
    log_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'logs')
else:
    log_dir = os.path.expanduser(config.get('general', 'log_dir'))

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

