# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import os
import shutil
from datetime import datetime


def get_copyright(site_author='choppy'):
    year = datetime.now().year
    copyright = 'Copyright &copy; {} {}, ' \
                'Maintained by the <a href="http://choppy.3steps.cn">' \
                'Choppy Community</a>.'.format(year, site_author.title())
    return copyright


def copy_and_overwrite(from_path, to_path, is_file=False):
    if os.path.isfile(to_path):
        os.remove(to_path)

    if os.path.isdir(to_path):
        shutil.rmtree(to_path)

    if is_file and os.path.isfile(from_path):
        parent_dir = os.path.dirname(to_path)
        # Force to make directory when parent directory doesn't exist
        os.makedirs(parent_dir, exist_ok=True)
        shutil.copy2(from_path, to_path)
    elif os.path.isdir(from_path):
        shutil.copytree(from_path, to_path)


class ReportTheme:
    def __init__(self):
        pass

    @classmethod
    def get_theme_lst(cls):
        theme_lst = ('mkdocs', 'readthedocs', 'material', 'cinder')
        return theme_lst


def print_obj(string):
    try:  # For Python2.7
        print(unicode(string).encode('utf8'))
    except NameError:  # For Python3
        print(string)


def clean_tmp_dir(tmp_dir):
    # Clean temp directory
    shutil.rmtree(tmp_dir, ignore_errors=True)
