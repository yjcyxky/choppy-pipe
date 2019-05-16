# -*- coding: utf-8 -*-
"""
    choppy_api.modules.workflow.parameters
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Input arguments (Parameters) for Workflow resources RESTful API.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import werkzeug
from flask_restplus import reqparse


# Batch
batch_submit_args = reqparse.RequestParser()
batch_submit_args.add_argument('samples', type=werkzeug.datastructures.FileStorage,
                               location='files', required=True,
                               help='a samples file what describe some attrs needed by app.')
