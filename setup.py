#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import re
from setuptools import setup
from collections import OrderedDict
from choppy.version import get_version
from setuptools.command.install import install

auto_complete_cmd = """
# Bash Auto Complete for Choppy
# eval "$(register-python-argcomplete choppy)"
"""


class PostInstallCommand(install):
    """Post-installation for installation mode."""

    def search_pattern(self, pattern):
        path = os.path.expanduser("~/.bashrc")
        with open(path, "r") as f:
            lines = f.read()
            data = re.findall(pattern, lines)
            return data

    def run(self):
        install.run(self)
        matched_str_lst = self.search_pattern(r"Bash Auto Complete for Choppy")
        if len(matched_str_lst) == 0:
            path = os.path.expanduser("~/.bashrc")
            # w+ 以读写模式打开; a 以追加模式打开 (从 EOF 开始, 必要时创建新文件)
            with open(path, "a") as f:
                f.write(auto_complete_cmd)


def get_packages(package):
    """Return root package and all sub-packages."""
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, "__init__.py"))]


setup(
    name="choppy-pipe",
    version=get_version(),
    description="An integrated analysis platform for efficiently achieving computational reproducibility",
    long_description=open("README.md").read(),
    long_description_content_type='text/markdown',
    author="Jingcheng Yang",
    author_email="yjcyxky@163.com",
    maintainer="Choppy Team",
    maintainer_email="choppyteam@gmail.com",
    url="http://choppy.3steps.cn",
    project_urls=OrderedDict(
        (
            ("Documentation", "https://choppy.readthedocs.io"),
            ("Code", "https://github.com/go-choppy/choppy"),
            ("Issue tracker", "https://github.com/go-choppy/choppy/issues"),
        )
    ),
    packages=get_packages("choppy"),
    keywords="choppy, data platform, command-line tool",
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    entry_points={
        "console_scripts": [
            "choppy = choppy.choppy_pipe:main",
            "choppy-pipe = choppy.choppy_pipe:main"
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
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    cmdclass={
        "install": PostInstallCommand,
    },
    install_requires=[
        "configparser>=3.5.0",
        "Jinja2>=2.10",
        "python-dateutil>=2.7.5",
        "ratelimit>=2.2.0",
        "requests>=2.21.0",
        "coloredlogs>=10.0",
        "argcomplete>=1.9.4",
        "markdown2>=2.3.7",
        "GitPython>=2.1.11",
        "SQLAlchemy >= 1.3.1",
        "docker",
        "verboselogs>=1.7",
        "psutil>=5.5.1",
        "jsonschema",
        "pytest>=4.4.1",
        "pytest-html"
    ]
)
