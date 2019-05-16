# -*- coding: utf-8 -*-
"""
    choppy_api.modules.app.models
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    App database models.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import os
from choppy.core.app_utils import get_app_root_dir


def get_app_info(app_name):
    app_root_dir = get_app_root_dir()
    app_dir = os.path.join(app_root_dir, app_name)
    app_info = {
        'installed_time': os.path.getctime(app_dir),
        'owner': '',
        'app_name': '',
        'version': '',
        'full_name': app_name
    }
    return app_info
