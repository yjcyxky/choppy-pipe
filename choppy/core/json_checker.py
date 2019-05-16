# -*- coding: utf-8 -*-
"""
    choppy.core.json_checker
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Module to check json file.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import re
import sys
import logging
from choppy import exit_code

logger = logging.getLogger(__name__)

try:
    import json
except Exception:
    import simplejson as json

try:  # For Python2.7
    from cStringIO import StringIO
except Exception:  # For Python3
    from io import StringIO

try:  # For Python3
    from json.decoder import JSONDecodeError
except Exception:  # For Python2.7
    JSONDecodeError = ValueError


class DictStruct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def parse_error(err):
    """Parse error string (formats) raised by (simple)json:

    '%s: line %d column %d (char %d)'
    '%s: line %d column %d - line %d column %d (char %d - %d)'
    """
    return re.match(r"""^
      (?P<msg>.+):\s+
      line\ (?P<lineno>\d+)\s+
      column\ (?P<colno>\d+)\s+
      (?:-\s+
        line\ (?P<endlineno>\d+)\s+
        column\ (?P<endcolno>\d+)\s+
      )?
      \(char\ (?P<pos>\d+)(?:\ -\ (?P<end>\d+))?\)$""", err, re.VERBOSE)


def check_json(json_file=None, string=''):
    try:
        if json_file:
            with open(json_file) as f:
                json.load(f)
        else:
            json.loads(string)
    except JSONDecodeError as error:
        if json_file:
            logger.error("Invalid JSON: %s" % json_file)
        else:
            logger.error("Invalid JSON")

        if json_file:
            with open(json_file) as f:
                string = f.read()

        string = StringIO(string)

        try:  # For Python2.7
            err_msg = error.message
            err_dict = parse_error(err_msg).groupdict()
        # Python3 AttributeError: 'JSONDecodeError' object has no attribute 'message'
        except Exception:  # For Python3
            err_msg = str(error)
            err_dict = parse_error(err_msg).groupdict()

        # cast int captures to int
        for k, v in err_dict.items():
            if v and v.isdigit():
                err_dict[k] = int(v)

        err = DictStruct(**err_dict)
        for ii, line in enumerate(string.readlines()):
            if ii == err.lineno - 1:
                logger.error("%s\n\n%s\n%s^-- %s\n" % (err_msg, line.replace("\n", ""),
                                                       " " * (err.colno - 1),
                                                       err.msg))

        sys.exit(exit_code.JSON_NOT_VALID)
