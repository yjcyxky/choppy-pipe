#!/usr/bin/env python

from setuptools import setup, find_packages
from choppy.version import get_version

setup(
    name='choppy',
    version=get_version(),
    description='A command-line tool for executing WDL workflows on Cromwell servers.',
    long_description=open('README.md').read(),
    author='Jingcheng Yang',
    author_email='yjcyxky@163.com',
    url='http://www.nordata.cn',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    entry_points={
        'console_scripts': [
            'choppy = choppy.choppy:main',
        ],
    },
    install_requires=[
        'cachetools==3.0.0',
        'certifi==2018.11.29',
        'chardet==3.0.4',
        'configparser==3.5.0',
        'futures==3.2.0',
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
    ]
)
