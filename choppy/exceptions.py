# -*- coding: utf-8 -*-
"""
    choppy.exceptions
    ~~~~~~~~~~~~~~~~~

    Exceptions.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals


class UnauthorizedException(Exception):
    pass


class UnFoundException(Exception):
    pass


class BadRequestException(Exception):
    pass


class InValidDefaults(Exception):
    pass


class InValidReport(Exception):
    pass


class NoSuchDirectory(Exception):
    pass


class NoSuchFile(Exception):
    pass


class InValidApp(Exception):
    pass


class NotFoundApp(Exception):
    pass


class WrongAppDir(Exception):
    pass


class AppInstallationFailed(Exception):
    pass


class AppUnInstallationFailed(Exception):
    pass


class PluginSyntaxError(Exception):
    pass


class ValidationError(Exception):
    pass


class NoConfigFile(Exception):
    pass


class NoSuchSection(Exception):
    pass


class NoSuchSchema(Exception):
    pass


class NoProperConfig(Exception):
    pass
