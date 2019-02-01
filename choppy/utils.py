# -*- coding:utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime


def get_copyright(site_author='choppy'):
    year = datetime.now().year
    copyright = 'Copyright &copy; %s %s,' \
                'Maintained by the <a href="http://choppy.3steps.cn">Choppy Community</a>.'.format(year, site_author)
    return copyright


class BashColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    SUCCESS = '\033[92m'  # Green
    WARNING = '\033[93m'  # Yellow
    DANGER = '\033[91m'   # Red
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    INFO = '\033[30m'     # Black

    @classmethod
    def _get_color(cls, color_name):
        color_dict = {
            'SUCCESS': BashColors.SUCCESS,
            'INFO': BashColors.INFO,
            'WARNING': BashColors.WARNING,
            'DANGER': BashColors.DANGER,
            'UNDERLINE': BashColors.UNDERLINE,
            'BOLD': BashColors.BOLD,
            'BLUE': BashColors.OKBLUE
        }
        return color_dict.get(color_name.upper(), BashColors.INFO)

    @classmethod
    def get_color_msg(cls, color_name, msg):
        return cls._get_color(color_name) + msg + BashColors.ENDC

    @classmethod
    def print_color(cls, color_name, msg):
        print(color_name + msg + BashColors.ENDC)
