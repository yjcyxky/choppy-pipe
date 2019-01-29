#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import logging
import os
import bjoern
import werkzeug
import uuid
import argparse
from gevent.pywsgi import WSGIServer
from flask import Flask, jsonify
from flask_restplus import Resource, Api, reqparse
import choppy.config as c
from choppy.app_utils import listapps
from choppy.check_utils import check_dir, is_valid_project_name
from choppy.workflow import run_batch
from choppy.bash_colors import BashColors
from choppy.choppy_store import ChoppyStore


cromwell_server = 'localhost'
api_version = 'v1'
api_prefix = '/api/%s' % api_version
choppy_store = ChoppyStore(c.base_url, username=c.username,
                           password=c.password)
flask_app = Flask(__name__)
api = Api(flask_app, version=api_version, title="Choppy API",
          description="Choppy for Reproducible Omics Pipeline", prefix=api_prefix)  # noqa


@flask_app.errorhandler(404)
def page_not_found(e):
    result = {
        'message': '404 Page Not Found.'
    }
    return jsonify(result), 404


def get_default_server(host=c.server_host, port=c.server_port):
    if host and port:
        return (host, port)
    elif host:
        return (host, 8000)
    elif port:
        return ('localhost', port)
    else:
        return ('0.0.0.0', 8000)


def get_data_dir(data_dir=c.server_data_dir, subdir_name=None):
    if not data_dir:
        data_dir = os.path.expanduser('~/.choppy/data')

    check_dir(data_dir, skip=True, force=True)

    if subdir_name:
        subdir = os.path.join(data_dir, subdir_name)
        check_dir(subdir, skip=True, force=True)
        return subdir

    return data_dir


@api.route('/installed-apps')
class App(Resource):
    @api.response(200, "Success.")
    def get(self):
        apps = listapps()
        resp = {
            "message": 'Success',
            "data": {
                "apps": apps
            }
        }
        return resp, 200


repo_parser = reqparse.RequestParser()


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
        'mode': 'type of repository to search for. Supported values are "fork", "source", "mirror" and "collaborative".',  # noqa
        'sort': 'sort repos by attribute. Supported values are "alpha", "created", "updated", "size", and "id". Default is "alpha".',  # noqa
        'order': 'sort order, either "asc" (ascending) or "desc" (descending). Default is "asc", ignored if "sort" is not specified.'  # noqa
    })
    def get(self):
        repo_parser.add_argument('q', default='')
        repo_parser.add_argument('page', type=int, help='Bad Type: {error_msg}',  # noqa
                                 default=1)
        repo_parser.add_argument('limit', type=int, default=10)
        repo_parser.add_argument('mode', choices=("fork", "source", "mirror", "collaborative"),  # noqa
                                 help='Bad choice: {error_msg}', default="source")  # noqa
        repo_parser.add_argument('sort', choices=("alpha", "created", "updated", "size", "id"),  # noqa
                                 help='Bad choice: {error_msg}', default="updated")  # noqa
        repo_parser.add_argument('order', choices=('asc', 'desc'), default="asc",  # noqa
                                 help='Bad choice: {error_msg}')
        args = repo_parser.parse_args()
        return choppy_store.search(args.get('q'), page=args.get('page'), limit=args.get('limit'),  # noqa
                                   mode=args.get('mode'), sort=args.get('sort'), order=args.get('order'))  # noqa


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
    pass


batch_parser = reqparse.RequestParser()
batch_parser.add_argument('samples', type=werkzeug.datastructures.FileStorage,
                          location='files', required=True)


@api.route('/batch/<app_name>')
class Batch(Resource):
    @api.doc(responses={
        201: "Success.",
        400: "Bad request.",
    })
    @api.doc(params={'app_name': 'app name'})
    @api.expect(batch_parser)
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
            app_dir = os.path.join(c.app_dir, args.app_name)
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


@api.route('/sitemap')
class SiteMap(Resource):
    @api.response(200, 'Success.')
    def get(self):
        return ['%s' % rule for rule in flask_app.url_map.iter_rules()]


def run_server(args):
    global cromwell_server
    cromwell_server = args.server
    daemon = args.daemon
    framework = args.framework
    if not daemon:
        if c.log_level == logging.DEBUG:
            debug = True
        else:
            debug = False
        flask_app.run(debug=debug)
    else:
        #
        # TODO: this starts the built-in server, which isn't the most
        # efficient.  We should use something better.
        #
        if framework == "GEVENT":
            c.print_color(BashColors.OKGREEN, "Starting gevent based server")
            c.print_color(BashColors.OKGREEN,
                          'Running Server: %s:%s' % get_default_server())
            svc = WSGIServer(get_default_server(), flask_app)
            svc.serve_forever()
        else:
            c.print_color(BashColors.OKGREEN, "Starting bjoern based server")
            host, port = get_default_server()
            c.print_color(BashColors.OKGREEN,
                          'Running Server: %s:%s' % (host, port))
            bjoern.run(flask_app, host, port, reuse_port=True)
