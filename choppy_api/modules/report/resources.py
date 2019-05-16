# -*- coding: utf-8 -*-
"""
    choppy_api.modules.report.resources
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    RESTful API Report resources.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from flask_restplus import Namespace, Resource

api = Namespace('reports', description='Choppy report related operations')


@api.route('/')
class Report(Resource):
    def get(self):
        """List all reports.
        """
        pass

    def post(self):
        """Create a report.
        """

    def put(self):
        """Modify a report
        """

    def delete(self):
        """Delete a report
        """


@api.route('/workflow/<workflow_id>')
class WorkflowReport(Resource):
    def get(self):
        """Get a specific workflow report.
        """
        pass

    def post(self):
        """Start a workflow report server.
        """
        pass

    def put(self):
        """Restart the specific workflow report server
        """
        pass

    def delete(self):
        """Stop the specific workflow report server.
        """
        pass


@api.route('/batch/<batch_id>')
class BatchReport(Resource):
    def get(self):
        """Get a specific batch report.
        """
        pass

    def post(self):
        """Start a batch report server.
        """
        pass

    def put(self):
        """Restart the specific batch report server
        """
        pass

    def delete(self):
        """Stop the specific batch report server.
        """
        pass
