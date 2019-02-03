# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import pkg_resources


class BaseConvertor:
    def __init__(self):
        pass

    def run(self, filepath):
        pass


def get_convertors():
    """ Return a dict of all installed Plugins by name. """

    convertors = pkg_resources.iter_entry_points(group='choppy.convertors')

    return dict((convertor.name, convertor) for convertor in convertors)
