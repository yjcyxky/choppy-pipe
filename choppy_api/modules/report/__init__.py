# -*- coding: utf-8 -*-
"""
    choppy_api.modules.report
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Report Module.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from choppy_api.extensions.api import api_v1


def init_app(app, **kwargs):
    """Init report module.
    """

    # Touch underlying modules
    from . import resources

    api_v1.add_namespace(resources.api)
