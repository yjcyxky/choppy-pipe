# -*- coding: utf-8 -*-
"""
    choppy_api.extensions.api
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    API extension.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from copy import deepcopy
from flask_restplus import Api


api_v1 = Api(
    version='v1.0',
    title="Choppy for Reproducible Omics Pipeline.",
    description=(
        "This documentation describes the Choppy API."
    ),
)


def init_app(app, **kwargs):
    """API extension initialization point.
    """
    # Prevent config variable modification with runtime changes
    api_v1.authorizations = deepcopy(app.config['AUTHORIZATIONS'])
