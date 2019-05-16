# -*- coding: utf-8 -*-
"""
    choppy.server
    ~~~~~~~~~

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""
from __future__ import unicode_literals
import logging
import os
import bjoern
import werkzeug
import uuid
import argparse
import verboselogs
from gevent.pywsgi import WSGIServer
from flask import Flask, jsonify, Blueprint
from flask_restplus import Resource, Api, reqparse, apidoc
from choppy.config import get_global_config
from choppy.core.app_utils import (listapps, get_app_root_dir,
                                   install_app, uninstall_app)
from choppy.check_utils import check_dir, is_valid_project_name
from choppy.core.workflow import run_batch
from choppy.core.choppy_store import ChoppyStore
from choppy.exceptions import AppInstallationFailed, AppUnInstallationFailed

logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger(__name__)

choppy_store = global_config = None
cromwell_server = 'localhost'
api_version = 'v1'
api_prefix = '/api/%s' % api_version

flask_app = Flask(__name__)
api = Api(flask_app, version=api_version, title="Choppy API", doc=False, specs=False,
          description="Choppy for Reproducible Omics Pipeline", prefix=api_prefix)

blueprint = Blueprint('api', __name__)


@blueprint.route('/', endpoint='doc')
def swagger_ui():
    return apidoc.ui_for(api)


@flask_app.errorhandler(404)
def page_not_found(e):
    result = {
        'message': '404 Page Not Found.'
    }
    return jsonify(result), 404


def get_default_server():
    server = global_config.get_section('server')
    host = server.host
    port = int(server.port)
    if host and port:
        return (host, port)
    elif host:
        return (host, 8000)
    elif port:
        return ('localhost', port)
    else:
        return ('0.0.0.0', 8000)


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


@api.route('/installed-apps')
class App(Resource):
    @api.response(200, "Success.")
    def get(self):
        apps = listapps()
        resp = {
            "message": 'Success',
            "data": [get_app_info(app) for app in apps]
        }
        return resp, 200


repo_parser = reqparse.RequestParser()
repo_parser.add_argument('name', type=str, required=True)
repo_parser.add_argument('owner', type=str, required=True)
repo_parser.add_argument('version', type=str, required=False)


@api.route('/apps')
class Repo(Resource):
    @api.doc(responses={
        200: "Success.",
        400: "Bad request.",
        500: "Internal Server Error."
    })
    @api.doc(params={
        'q': 'keyword',
        'page': 'page number of results to return (1-based).',
        'limit': 'page size of results, maximum page size is 50.',
        'mode': 'type of repository to search for. Supported values are "fork", "source", "mirror" and "collaborative".',
        'sort': 'sort repos by attribute. Supported values are "alpha", "created", "updated", "size", and "id". Default is "alpha".',
        'order': 'sort order, either "asc" (ascending) or "desc" (descending). Default is "asc", ignored if "sort" is not specified.',
        'topic_only': 'q_str will be as topic name only when topic_only is true. Default is 1.'
    })
    def get(self):
        repo_parser = reqparse.RequestParser()
        repo_parser.add_argument('q', default='choppy-app')
        repo_parser.add_argument('page', type=int, help='Bad Type: {error_msg}',
                                 default=1)
        repo_parser.add_argument('limit', type=int, default=10)
        repo_parser.add_argument('mode', choices=("fork", "source", "mirror", "collaborative"),
                                 help='Bad choice: {error_msg}', default="source")
        repo_parser.add_argument('sort', choices=("alpha", "created", "updated", "size", "id"),
                                 help='Bad choice: {error_msg}', default="updated")
        repo_parser.add_argument('order', choices=('asc', 'desc'), default="asc",
                                 help='Bad choice: {error_msg}')
        repo_parser.add_argument('topic_only', type=int, default=1)
        args = repo_parser.parse_args()
        return choppy_store.search(args.get('q'), page=args.get('page'), limit=args.get('limit'),
                                   mode=args.get('mode'), sort=args.get('sort'), order=args.get('order'), topic_only=args.get('topic_only'))

    @api.doc(responses={
        204: "No content.",
        400: "Bad request.",
        500: "Internal Server Error."
    })
    @api.expect(repo_parser, validate=True)
    def post(self):
        args = repo_parser.parse_args()
        app_name = args.get('name')
        owner = args.get('owner')
        choppy_app = '%s/%s' % (owner, app_name)
        version = args.get('version', None)

        if version:
            choppy_app = '%s/%s:%s' % (owner, app_name, version)

        server = global_config.get_section('server')
        app_root_dir = os.path.expanduser(server.app_root_dir)
        try:
            install_app(app_root_dir, choppy_app, is_terminal=False)
            status_code = 204
            return None, status_code
        except AppInstallationFailed as err:
            msg = str(err)
            status_code = 400

            resp = {
                "message": msg
            }

            return resp, status_code

    @api.doc(responses={
        200: "Success.",
        400: "Bad request.",
        404: "Not found.",
        500: "Internal Server Error."
    })
    @api.expect(repo_parser, validate=True)
    def delete(self):
        args = repo_parser.parse_args()
        app_name = args.get('name')
        # TODO: Need to add a namespace
        owner = args.get('owner')
        choppy_app = '%s/%s-%s' % (owner, app_name, 'latest')
        version = args.get('version', None)

        if version:
            choppy_app = '%s/%s-%s' % (owner, app_name, version)

        server = global_config.get_section('server')
        app_dir = os.path.expanduser(os.path.join(server.app_root_dir, choppy_app))

        # TODO: Any Exception?
        try:
            msg = uninstall_app(app_dir, is_terminal=False)
            status_code = 200
        except AppUnInstallationFailed as err:
            msg = str(err)
            status_code = 404

        resp = {
            "message": msg
        }

        return resp, status_code


@api.route('/<owner>/<app_name>/releases')
class RepoRelease(Resource):
    @api.doc(params={'app_name': 'app name', 'owner': 'owner'})
    @api.doc(responses={
        200: "Success.",
        400: "Bad request.",
        500: "Internal Server Error."
    })
    def get(self, owner, app_name):
        return choppy_store.list_releases(owner, app_name)


@api.route('/workflow')
class Workflow(Resource):
    def get(self):
        # Get a set of workflows, filterd by something.
        pass

    def post(self):
        # Submit a workflow.
        pass

    def put(self):
        # Pause/Restart a set of workflows
        pass

    def delete(self):
        # Stop a set of workflows.
        pass


@api.route('/workflow/<workflow_id>')
class WorkflowInstance(Resource):
    def get(self):
        # Get all information.
        pass

    def put(self):
        # Pause/Restart a workflow
        pass

    def delete(self):
        # Stop a workflow
        pass


batch_parser = reqparse.RequestParser()
batch_parser.add_argument('samples', type=werkzeug.datastructures.FileStorage,
                          location='files', required=True)


@api.route('/batch/<app_name>')
class Batch(Resource):
    def get(self):
        # Get a batch task, metadata/samples/app/more.
        pass

    @api.doc(responses={
        201: "Success.",
        400: "Bad request.",
    })
    @api.doc(params={'app_name': 'app name'})
    @api.expect(batch_parser, validate=True)
    def post(self, app_name):
        try:
            project_name = uuid.uuid1()
            is_valid_project_name(project_name)
            projects_loc = get_data_dir(
                subdir_name='projects/%s' % project_name)
            args = batch_parser.parse_args()
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
                                samples_file_path, None, cromwell_server)
            resp = {
                "message": "Success",
                "data": {
                    "successed": results.get("successed"),
                    "failed": results.get("failed"),
                    "project_name": project_name,
                    "samples": samples_file_name,
                    "app_name": app_name,
                    "server": cromwell_server
                }
            }
            return resp, 201
        except (argparse.ArgumentTypeError, Exception) as err:
            err_resp = {
                "message": str(err)
            }
            return err_resp, 400

    def put(self):
        # Pause/Restart a batch task.
        pass

    def delete(self):
        # Stop a batch task.
        pass


@api.route('/report/workflow/<workflow_id>')
class WorkflowReport(Resource):
    pass


@api.route('/report/batch/<batch_id>')
class BatchReport(Resource):
    pass


@api.route('/sitemap')
class SiteMap(Resource):
    @api.response(200, 'Success.')
    def get(self):
        return ['%s' % rule for rule in flask_app.url_map.iter_rules()]


def run_server(args):
    global cromwell_server, choppy_store, global_config

    global_config = get_global_config()

    def init_choppy_store():
        store_config = global_config.get_section('repo')
        choppy_store = ChoppyStore(store_config.base_url,
                                   username=store_config.username,
                                   password=store_config.password)
        return choppy_store

    choppy_store = init_choppy_store()

    if args.swagger:
        flask_app.register_blueprint(blueprint)
        flask_app.register_blueprint(apidoc.apidoc)

    cromwell_server = args.server
    framework = args.framework

    #
    # TODO: this starts the built-in server, which isn't the most
    # efficient.  We should use something better.
    #
    if framework == "gevent":
        logger.success("Starting gevent based server")
        logger.success('Running Server: %s:%s' % get_default_server())
        svc = WSGIServer(get_default_server(), flask_app)
        svc.serve_forever()
    elif framework == "bjoern":
        logger.success("Starting bjoern based server")
        host, port = get_default_server()
        logger.success('Running Server: %s:%s' % (host, port))
        bjoern.run(flask_app, host, port, reuse_port=True)
    else:
        flask_app.run(debug=True)
