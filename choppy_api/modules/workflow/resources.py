# -*- coding: utf-8 -*-
"""
    choppy_api.modules.workflow.resources
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    RESTful API Workflow resources.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import os
import uuid
import argparse
from choppy.config import get_global_config
from flask_restplus import Namespace, Resource
from choppy.check_utils import is_valid_project_name
from choppy.core.app_utils import get_app_root_dir
from choppy.core.workflow import run_batch
from .utils import get_data_dir
from .parameters import batch_submit_args

global_config = get_global_config()
api = Namespace('workflows', description='Choppy report related operations')


@api.route('/')
class Workflow(Resource):
    def get(self):
        """Get a set of workflows, filterd by something.
        """
        pass

    def post(self):
        """Submit a workflow.
        """
        pass

    def put(self):
        """Pause/Restart a set of workflows
        """
        pass

    def delete(self):
        """Stop a set of workflows.
        """
        pass


@api.route('/workflow/<workflow_id>')
class WorkflowInstance(Resource):
    def get(self):
        """Get all information.
        """
        pass

    def put(self):
        """Pause/Restart a workflow
        """
        pass

    def delete(self):
        """Stop a workflow
        """
        pass


@api.route('/batch/<app_name>')
class Batch(Resource):
    def get(self):
        """Get a batch task, metadata/samples/app/more.
        """
        pass

    @api.doc(responses={
        201: "Success.",
        400: "Bad request.",
    })
    @api.doc(params={'app_name': 'app name'})
    @api.expect(batch_submit_args, validate=True)
    def post(self, app_name):
        """Submit a batch task.
        """
        try:
            project_name = uuid.uuid1()
            is_valid_project_name(project_name)
            projects_loc = get_data_dir(
                subdir_name='projects/%s' % project_name)
            args = batch_submit_args.parse_args()
            file_name = uuid.uuid1()
            samples_file = args['samples']
            samples_file_name = '%s.samples' % file_name
            samples_file_path = os.path.join(projects_loc,
                                             samples_file_name)
            samples_file.save(samples_file_path)

            app_root_dir = get_app_root_dir()
            app_dir = os.path.join(app_root_dir, args.app_name)
            # TODO: support label
            results = run_batch(project_name, app_dir,
                                samples_file_path, None, global_config.cromwell_server)
            resp = {
                "message": "Success",
                "data": {
                    "successed": results.get("successed"),
                    "failed": results.get("failed"),
                    "project_name": project_name,
                    "samples": samples_file_name,
                    "app_name": app_name,
                    "server": global_config.cromwell_server
                }
            }
            return resp, 201
        except (argparse.ArgumentTypeError, Exception) as err:
            err_resp = {
                "message": str(err)
            }
            return err_resp, 400

    def put(self):
        """Restart a batch task.
        """
        pass

    def delete(self):
        """Stop a batch task.
        """
        pass
