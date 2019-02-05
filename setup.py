#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import re
from setuptools import setup
from choppy.version import get_version
from setuptools.command.install import install

auto_complete_cmd = """
# Bash Auto Complete for Choppy
if command -v activate-global-python-argcomplete > /dev/null 2>&1; then
    activate-global-python-argcomplete --user > /dev/null
    eval "$(register-python-argcomplete choppy)"
else
    echo ''
fi
"""


class PostInstallCommand(install):
    """Post-installation for installation mode."""

    def search_pattern(self, pattern):
        path = os.path.expanduser('~/.bashrc')
        with open(path, 'r') as f:
            lines = f.read()
            data = re.findall(pattern, lines)
            return data

    def run(self):
        install.run(self)
        matched_str_lst = self.search_pattern(r'Bash Auto Complete for Choppy')
        if len(matched_str_lst) == 0:
            path = os.path.expanduser('~/.bashrc')
            # w+ 以读写模式打开; a 以追加模式打开 (从 EOF 开始, 必要时创建新文件)
            with open(path, 'a') as f:
                f.write(auto_complete_cmd)


def get_packages(package):
    """Return root package and all sub-packages."""
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


setup(
    name='choppy',
    version=get_version(),
    description='A command-line tool for executing WDL workflows on Cromwell servers.',  # noqa
    long_description=open('README.md').read(),
    author='Jingcheng Yang',
    author_email='yjcyxky@163.com',
    url='http://www.nordata.cn',
    packages=get_packages("choppy"),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    entry_points={
        'console_scripts': [
            'choppy = choppy.__main__:main',
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
    },
    install_requires=[
        'cachetools==3.0.0',
        'certifi==2018.11.29',
        'chardet==3.0.4',
        'configparser==3.5.0',
        'idna==2.8',
        'Jinja2==2.10',
        'MarkupSafe==1.1.0',
        'protobuf==3.6.1',
        'pyasn1==0.4.4',
        'pyasn1-modules==0.2.2',
        'python-dateutil==2.7.5',
        'pytz==2018.7',
        'ratelimit==2.2.0',
        'requests==2.21.0',
        'rsa==4.0',
        'six==1.12.0',
        'SQLAlchemy==1.2.15',
        'urllib3==1.24.1',
        'coloredlogs==10.0',
        'argcomplete==1.9.4',
        'markdown2==2.3.7',
        'GitPython==2.1.11',
        'bjoern == 2.2.3',
        'flask == 1.0.2',
        'gevent == 1.4.0',
        'flask-restplus==0.12.1',
        'docker==3.7.0',
        'mkdocs>=1.0.4',
        'mkdocs-material==3.3.0',
        'mkdocs-cinder==0.16.1',
    ]
)
