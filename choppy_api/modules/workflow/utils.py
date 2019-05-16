# -*- coding: utf-8 -*-
"""
    choppy_api.modules.workflow.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utils for Workflow resources.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import os
from choppy.check_utils import check_dir
from choppy.config import get_global_config


global_config = get_global_config()


def get_data_dir(data_dir=None, subdir_name=None):
    if not data_dir:
        data_dir = global_config.get('server', 'data_dir')
        data_dir = data_dir if data_dir else os.path.expanduser('~/.choppy/data')

    check_dir(data_dir, skip=True, force=True)

    if subdir_name:
        subdir = os.path.join(data_dir, subdir_name)
        check_dir(subdir, skip=True, force=True)
        return subdir

    return data_dir
