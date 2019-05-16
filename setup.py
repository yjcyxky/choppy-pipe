#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import re
from setuptools import setup
from choppy.version import get_version
from setuptools.command.install import install

auto_complete_cmd = """
# Bash Auto Complete for Choppy
# eval "$(register-python-argcomplete choppy)"
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
    description='A command-line tool for executing WDL workflows on Cromwell servers.',
    long_description=open('README.md').read(),
    author='Jingcheng Yang',
    author_email='yjcyxky@163.com',
    url='http://choppy.3steps.cn',
    packages=get_packages("choppy"),
    keywords='choppy, data platform, command-line tool',
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    entry_points={
        'console_scripts': [
            'choppy-pipe = choppy.choppy_pipe:main',
            'choppy-api-server = choppy_api.api_server:main'
        ],
    },
    extras_require={
        "dotenv": ["python-dotenv"],
        "dev": [
            "pytest>=3",
            "tox",
            "sphinx",
            "pallets-sphinx-themes",
            "sphinxcontrib-log-cabinet",
        ],
        "docs": ["sphinx", "pallets-sphinx-themes", "sphinxcontrib-log-cabinet"],
    },
    classifiers=[
        'Development Status :: 1 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: AGPL 3.0 License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    cmdclass={
        'install': PostInstallCommand,
    },
    install_requires=[
        'configparser>=3.5.0',
        'Jinja2>=2.10',
        'python-dateutil>=2.7.5',
        'ratelimit>=2.2.0',
        'requests>=2.21.0',
        'SQLAlchemy>=1.2.15',
        'coloredlogs>=10.0',
        'argcomplete>=1.9.4',
        'markdown2>=2.3.7',
        'GitPython>=2.1.11',
        'bjoern>=2.2.3',
        'flask>=1.0.2',
        'gevent>=1.4.0',
        'flask-restplus>=0.12.1',
        'SQLAlchemy >= 1.3.1',
        'Flask-SQLAlchemy >= 2.4.0',
        'docker',
        'verboselogs>=1.7',
        'beautifulsoup4',
        'psutil>=5.5.1',
        'PyYAML',
        'pymdown-extensions',
        'jsonschema',
        'pytest>=4.4.1',
        'pytest-html',
        'Alembic==0.8.10',
        'werkzeug>=0.14.1,< 0.15',
        'marshmallow>=2.13.5',
        'flask-marshmallow==0.7.0',
        'marshmallow-sqlalchemy==0.12.0',
        'webargs>=1.4.0',
        'apispec>=0.20.0,< 0.39',
        'flask-caching>=1.7.1'
    ]
)
