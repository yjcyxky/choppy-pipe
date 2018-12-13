import os
import sys
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

# Hosts that have a broadinstitute.org domain
bi_hosts = ['ale', 'ale1', 'btl-cromwell', 'gscid-cromwell']
# Hosts that don't
other_hosts = ['cloud', 'localhost', 'gscid-cloud']
# cloud only hosts
cloud_hosts = ['cloud', 'gscid-cloud']
servers = bi_hosts + other_hosts

resource_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'resources')
run_states = ['Running', 'Submitted', 'QueuedInCromwell']
terminal_states = ['Failed', 'Aborted', 'Succeeded']

workflow_db = os.path.expanduser(config.get('general', 'workflow_db'))
app_dir = os.path.join(os.path.expanduser(config.get('general', 'app_dir')), 'apps')

# check and make app_dir
check_dir(app_dir)

# localhost port
local_port = config.get('local', 'local_port')

# cloud servers IP address(es)
cloud_server = config.get('cloud', 'cloud_server')
gscid_cloud_server = config.get('cloud', 'gscid_cloud_server')
cloud_port = config.get('cloud', 'cloud_port')

# bucket names
gscid_bucket = config.get('cloud', 'gscid_bucket')
dev_bucket = config.get('cloud', 'dev_bucket')
default_bucket = gscid_bucket
inputs_root = config.get('cloud', 'inputs_root')

# directory for generated temporary files (ex: for making fofns)

temp_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'generated')


if sys.platform == 'win32':
    log_dir = os.path.abspath(os.path.dirname(__file__)).replace('choppy', 'logs')
else:
    log_dir = os.path.expanduser(config.get('general', 'log_dir'))

# Exclude these json keys from being converted to GS URLs.
exclude_gspath_array = ["onprem_download_path"]


def gspathable(k):
    """
    Evaluate if a key is allowed to be converted to a GS path.
    :param k: The key to evaluate.
    :return: True if allowed, false if not.
    """
    for field in exclude_gspath_array:
        if field in k:
            return False

    return True

def flatmap(f, items):
    return chain.from_iterable(imap(f, items))

temp_test_dir = "/broad/hptmp"
