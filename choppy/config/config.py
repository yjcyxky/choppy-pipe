# -*- coding: utf-8 -*-
"""
    choppy.config.config
    ~~~~~~~~~
    Load and parse config file.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""
from __future__ import unicode_literals
import os
import sys
import re
import logging
import getpass
from choppy import exit_code
from choppy import exceptions
from os.path import expanduser
from threading import local

g = local()


# Convert nested Python dict to object?
# For more details: https://stackoverflow.com/a/1305663
class Section:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class ChoppyConfig:
    """Load and parse config file.
    """
    prefixes = ['remote']

    conf_dir = os.path.dirname(os.path.abspath(__file__))

    conf_file_dict = {
        "userconf": "~/.choppy/choppy.conf",
        "sysconf": "/etc/choppy.conf",
        "exampleconf": os.path.join(conf_dir, 'choppy.conf.example')
    }

    run_states = ['Running', 'Submitted', 'QueuedInCromwell']
    terminal_states = ['Failed', 'Aborted', 'Succeeded']
    status_list = run_states + terminal_states

    def __init__(self, extra_config_file=None, chosen_conf_key=None, format='ini'):
        self.conf_format = format
        self.logger = logging.getLogger(__name__)
        schema_dir = os.path.join(self.conf_dir, 'schemas')
        self.schemas = self._load_schemas(schema_dir)
        self.logger.debug("Load schema files: %s" % str(self.schemas))
        if extra_config_file is not None:
            self._add_conf_file('tempconf', extra_config_file)

        self._init_config(chosen_conf_key)

    def _init_config(self, chosen_conf_key):
        conf_path = self.get_config_file(chosen_conf_key)
        self.logger.debug("Use config file: %s" % conf_path)
        if conf_path is None:
            raise exceptions.NoConfigFile('Not found choppy.conf in %s' % self.get_conf_lst())

        if self.conf_format == 'ini':
            import configparser
            self.config = configparser.ConfigParser()
            self.config.read(conf_path, encoding="utf-8")
        elif self.conf_format == 'json':
            import json
            with open(conf_path, 'r') as f:
                self.config = json.load(f)

    def register_prefix(self, prefix):
        if prefix not in self.prefixes:
            self.prefixes.append(prefix)
        return self.prefixes

    @property
    def raw_config(self):
        return self.config

    def get_section(self, section_name, is_dict=False):
        section_dict = self._convert2dict(section_name)
        try:
            self._check_schema(section_dict, name=section_name)
        except exceptions.NoSuchSchema:
            # May be the section is a user custom section, such as remote_
            valid_name = self._get_prefix_name(section_name)
            self._check_schema(section_dict, name=valid_name)

        if is_dict:
            return section_dict
        else:
            return Section(**section_dict)

    def _load_schemas(self, schema_dir, abspath=True):
        """Get all schema files from the schema_dir.
        """
        # Using listdir realpath abspath with symbolic links.
        # For more details: https://stackoverflow.com/a/27156824
        if abspath:
            return [os.path.join(schema_dir, fname)
                    for fname in os.listdir(schema_dir)]
        else:
            return os.listdir(schema_dir)

    def _get_prefix_name(self, section_name):
        """Get section prefix from user custom section.
        """
        for prefix in self.prefixes:
            if prefix in section_name:
                return prefix

    def _check_schema(self, data, name=None, schema_file=None):
        """Check the data whether satisfy the specified schema file.

        :param: data: a dict.
        :type: dict
        :param: name: schema index.
        :type: str
        :param: schema_file: file handler from user custom schema file.
        :type: filehandler
        """
        import json
        from jsonschema import validate
        from choppy.config.schema import ChoppyValidator
        if name:
            valid_name = 'config_%s.json' % name
            fname_lst = [x for x in self.schemas if x == valid_name or valid_name in x]
            self.logger.debug('Matched %s-th schema file: %s' % (len(fname_lst), fname_lst))
            # May be it will cause error when matched file are greater than two.
            filename = fname_lst[0] if len(fname_lst) > 0 else None
            if filename:
                with open(filename, 'r') as f:
                    schema = json.load(f)
                    validate(data, schema, cls=ChoppyValidator)
            else:
                raise exceptions.NoSuchSchema("No such schema file: %s" % valid_name)
        elif schema_file and os.path.exists(schema_file):
            schema = json.load(filename)
            validate(data, schema, cls=ChoppyValidator)
        else:
            schema = name if name else schema_file
            raise exceptions.NoSuchSchema("No such schema file: %s" % schema)

    def get_server_name(self, section_name):
        if re.match(r'remote_[\w]+', section_name):
            return section_name.split('_')[1]

    @property
    def servers(self):
        remote_sections = [section_name for section_name in self.sections
                           if re.match(r'remote_[\w]+', section_name)]
        servers = [self.get_server_name(section_name) for section_name in remote_sections]
        return ['localhost', ] + servers

    def get(self, section_name, attr_name):
        section = self.get_section(section_name, is_dict=True)
        return section.get(attr_name, None)

    def get_path(self, section_name, attr_name):
        section = self.get_section(section_name, is_dict=True)
        return os.path.expanduser(section.get(attr_name, ''))

    def get_int(self, section_name, attr_name):
        section = self.get_section(section_name, is_dict=True)
        try:
            return int(section.get(attr_name))
        except ValueError:
            msg = '%s in %s section of config file must be integer.' % (section_name, attr_name)
            raise exceptions.ConfigValueError(msg)

    def get_float(self, section_name, attr_name):
        section = self.get_section(section_name, is_dict=True)
        try:
            return float(section.get(attr_name))
        except ValueError:
            msg = '%s in %s section of config file must be float.' % (section_name, attr_name)
            raise exceptions.ConfigValueError(msg)

    def get_boolean(self, section_name, attr_name):
        section = self.get_section(section_name, is_dict=True)
        try:
            value = str(section.get(attr_name))
            if value.upper() in ('T', 'TRUE'):
                return True
            else:
                return False
        except ValueError:
            msg = '%s in %s section of config file must be float.' % (section_name, attr_name)
            raise exceptions.ConfigValueError(msg)

    def get_conn_info(self, server, section_name):
        section = self.get_section(section_name)
        if server == 'localhost':
            return 'localhost', section.port, (section.username, section.password)
        else:
            return section.host, section.port, (section.username, section.password)

    @property
    def sections(self):
        if self.conf_format == 'ini':
            return self.config.sections()
        elif self.conf_format == 'json':
            return self.config.keys()

    def _convert2dict(self, section_name):
        if self.conf_format == 'ini':
            if self.config.has_section(section_name):
                return dict(self.config[section_name])
            else:
                msg = 'No such section in config file: %s' % section_name
                raise exceptions.NoSuchSection(msg)
        elif self.conf_format == 'json':
            section = self.config.get(section_name, None)
            if section:
                return section
            else:
                msg = 'No such property in json config file: %s' % section_name
                raise exceptions.NoSuchSection(msg)

    @property
    def resource_dir(self):
        from os.path import dirname, abspath, join
        resource_dir = join(dirname(dirname(abspath(__file__))), 'resources')
        return resource_dir

    def _add_conf_file(self, key, filepath):
        if not os.path.isfile(expanduser(filepath)):
            self.logger.warning("No such file: %s" % filepath)
        else:
            self.conf_file_dict.update({
                key: filepath
            })

    def get_conf_lst(self, filter=''):
        if filter:
            try:
                import re
                return list([string for string in self.conf_file_dict.values()
                             if not re.match(filter, string)])
            except Exception as err:
                self.logger.error('regular expression(%s) is wrong' % filter)
                self.logger.debug(str(err))
        else:
            return list(self.conf_file_dict.values())

    def get_conf_file_by_key(self, key):
        return self.conf_file_dict.get(key, '')

    def get_config_file(self, chosen_conf_key=None):
        if chosen_conf_key:
            conf_file = expanduser(self.get_conf_file_by_key(chosen_conf_key))
            if conf_file and os.path.exists(conf_file):
                return conf_file
            else:
                return
        else:
            for f in self.get_conf_lst():
                try:
                    loc = expanduser(f)
                except KeyError:
                    # os.path.expanduser can fail when $HOME is undefined and
                    # getpwuid fails. See http://bugs.python.org/issue20164 &
                    # https://github.com/kennethreitz/requests/issues/1846
                    return

                if os.path.exists(loc):
                    return loc

    def get_conf_example(self, return_path=False):
        example_file_path = os.path.join(self.conf_dir, 'choppy.conf.example')
        if return_path:
            return example_file_path
        else:
            with open(example_file_path, 'r') as f:
                return f.read()

    def _check_dir(self, path):
        if not os.path.isdir(path):
            os.makedirs(path)

    def getuser(self):
        user = getpass.getuser().lower()
        matchObj = re.match(r'^[a-zA-Z0-9_]+$', user, re.M | re.I)
        if matchObj:
            return user
        else:
            self.logger.critical("Your account name is not valid. "
                                 "Did not match the regex ^[a-zA-Z0-9_]+$")
            sys.exit(exit_code.USERNAME_NOT_VALID)


def init_config(extra_config_file=None, chosen_conf_key=None, format='ini'):
    '''Initialize config object.
    order:
    1. ~/.choppy/choppy.conf
    2. /etc/choppy.conf
    3. choppy.conf.example
    '''
    try:
        global g
        g.config = ChoppyConfig(extra_config_file, chosen_conf_key, format)
    except exceptions.NoConfigFile:
        # Need to run config/version subcommand when ~/.choppy/choppy.conf doesn't exist.
        pass


def get_global_config():
    global g
    return g.config
