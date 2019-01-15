#!/usr/bin/env python
# -*- coding:utf-8 -*-
# pylint: disable=no-name-in-module
"""
Example usage:
$ f=`cat test.json`; echo -e "$f"; python validate_json.py "$f"
{
  "foo": true,
  "bar": false,
  baz: -23
}
Invalid JSON
  Expecting property name: line 4 column 3 (char 35)
    baz: -23
    ^-- Expecting property name
"""

import re
import sys
from . import exit_code

try:
    import json
except:
    import simplejson as json

try:  # For Python2.7
    from cStringIO import StringIO
except:  # For Python3
    from io import StringIO

try:  # For Python3
    from json.decoder import JSONDecodeError
except:  # For Python2.7
    JSONDecodeError = ValueError


def parse_error(err):
    """
    "Parse" error string (formats) raised by (simple)json:
    '%s: line %d column %d (char %d)'
    '%s: line %d column %d - line %d column %d (char %d - %d)'
    """
    return re.match(r"""^
      (?P<msg>[^:]+):\s+
      line\ (?P<lineno>\d+)\s+
      column\ (?P<colno>\d+)\s+
      (?:-\s+
        line\ (?P<endlineno>\d+)\s+
        column\ (?P<endcolno>\d+)\s+
      )?
      \(char\ (?P<pos>\d+)(?:\ -\ (?P<end>\d+))?\)
  $""", err, re.VERBOSE)


def check_json(json_file=None, str=''):
    try:
        if json_file:
            with open(json_file) as f:
                json.load(f)
        else:
            json.loads(str)
    except JSONDecodeError as err:
        if json_file:
            print("Invalid JSON: %s\n" % json_file)
        else:
            print("Invalid JSON\n")

        if json_file:
            with open(json_file) as f:
                str = f.read()

        str = StringIO(str)

        try:  # For Python2.7
            msg = err.message
            err = parse_error(msg).groupdict()
            # cast int captures to int
            for k, v in err.items():
                if v and v.isdigit():
                    err[k] = int(v)

            for ii, line in enumerate(str.readlines()):
                if ii == err["lineno"] - 1:
                    break
            print("%s\n%s\n%s^-- %s\n" % (msg, line.replace("\n", ""),
                                          " " * (err["colno"] - 1),
                                          err["msg"]))
        except:  # For Python3
            for ii, line in enumerate(str.readlines()):
                if ii == err.lineno - 1:
                    break

            print("%s\n%s\n%s^-- %s\n" % (err.msg, line.replace("\n", ""),
                                          " " * (err.colno - 1),
                                          err.msg))

        sys.exit(exit_code.JSON_NOT_VALID)
