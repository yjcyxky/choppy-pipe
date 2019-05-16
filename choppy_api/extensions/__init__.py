# -*- coding: utf-8 -*-
"""
    choppy_api.extensions
    ~~~~~~~~~~~~~~~~~~~~~

    Extensions provide access to common resources of the application.
    Please, put new extension instantiations and initializations here.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from . import api

db = SQLAlchemy()
cache = Cache()


def init_app(app):
    """
    Application extensions initialization.
    """
    for extension in (
        db,
        cache,
        api,
    ):
        extension.init_app(app)
