# -*- coding: utf-8 -*-
"""
    tests.config.test_config
    ~~~~~~~~~

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""
import os
import pytest
from os.path import expanduser
from choppy import config
from choppy import exceptions


class TestNoConfigFile(object):
    def test_init_config(self):
        try:
            config.ChoppyConfig()
        except exceptions.NoConfigFile:
            with pytest.raises(exceptions.NoConfigFile):
                config.ChoppyConfig()


class TestConfigFile(object):
    @classmethod
    def get_config_file(cls):
        default_conf_files = ['~/.choppy/choppy.conf', '/etc/choppy.conf']
        for f in default_conf_files:
            try:
                loc = expanduser(f)
            except KeyError:
                # os.path.expanduser can fail when $HOME is undefined and
                # getpwuid fails. See http://bugs.python.org/issue20164 &
                # https://github.com/kennethreitz/requests/issues/1846
                return

            if os.path.exists(loc):
                return loc

    @pytest.fixture(scope="session", autouse=True)
    def config_obj(self):
        conf_file = self.get_config_file()
        if conf_file is None:
            examples_dir = os.path.abspath(__file__)
            example_conf = os.path.join(examples_dir, 'examples', 'choppy.conf')
        else:
            example_conf = None
        return config.ChoppyConfig(config_file=example_conf)

    def test_raw_config(self, config_obj):
        from configparser import ConfigParser
        assert isinstance(config_obj.raw_config, ConfigParser)

    def test_get_section(self, config_obj):
        with pytest.raises(exceptions.NoSuchSection):
            config_obj.get_section('no_such_section')

        assert isinstance(config_obj.get_section('general'), config.Section)
        assert isinstance(config_obj.get_section('local'), config.Section)
        assert isinstance(config_obj.get_section('email'), config.Section)
        assert isinstance(config_obj.get_section('oss'), config.Section)
        assert isinstance(config_obj.get_section('repo'), config.Section)
        assert isinstance(config_obj.get_section('remote_remote'), config.Section)

    def test_get_conf_lst(self, config_obj):
        conf_lst = config_obj.get_conf_lst(filter='.*.example$')
        assert isinstance(conf_lst, list)
        assert '~/.choppy/choppy.conf' in conf_lst
        assert '/etc/choppy.conf' in conf_lst
        assert config_obj.get_conf_example(return_path=True) not in conf_lst

    def test_get_conf_file_by_key(self, config_obj):
        conf_file = config_obj.get_conf_file_by_key('userconf')
        assert isinstance(conf_file, str)
        assert conf_file == '~/.choppy/choppy.conf'

        conf_file = config_obj.get_conf_file_by_key('no_such_key')
        assert isinstance(conf_file, str)
        assert conf_file == ''

    def test_get_config_file(self, config_obj):
        conf_file = config_obj.get_config_file()
        assert conf_file in [
            expanduser('~/.choppy/choppy.conf'),
            '/etc/choppy.conf',
            os.path.join(config_obj.conf_dir, 'choppy.conf.example')
        ]

        conf_file = config_obj.get_config_file('sysconf')
        if os.path.exists('/etc/choppy.conf'):
            assert conf_file == '/etc/choppy.conf'
        else:
            assert conf_file is None

    def test_conf_example(self, config_obj):
        example = config_obj.get_conf_example()
        example_path = config_obj.get_conf_example(return_path=True)
        assert isinstance(example, str)
        assert 'choppy.conf.example' in example_path
