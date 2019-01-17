#!/usr/bin/env python

import logging
import sys
import imp
import os
import bjoern
import werkzeug
import uuid
import argparse
from gevent.pywsgi import WSGIServer
from flask import Flask, request, abort, g
from flask_restful import Resource, Api, reqparse
from . import config as c
from .app_utils import listapps
from .check_utils import check_dir, is_valid_project_name
from .workflow import run_batch
from .bash_colors import BashColors
from .choppy_store import ChoppyStore


cromwell_server = 'localhost'
choppy_store = ChoppyStore(c.base_url, username=c.username,
                           password=c.password)


def get_default_server(host=c.server_host, port=c.server_port):
    if host and port:
        return (host, port)
    elif host:
        return (host, '8000')
    elif port:
        return ('localhost', port)


def get_data_dir(data_dir=c.server_data_dir, subdir_name=None):
    if not data_dir:
        data_dir = os.path.expanduser('~/.choppy/data')

    check_dir(data_dir, skip=True, force=True)

    if subdir_name:
        subdir = os.path.join(data_dir, subdir_name)
        check_dir(subdir, skip=True, force=True)
        return subdir

    return data_dir


class App(Resource):
    def get(self):
        apps = listapps()
        resp = {
            "message": 'Success',
            "data": {
                "apps": apps
            }
        }
        return resp, 200


class Repo(Resource):
    def get(self):
        parse = reqparse.RequestParser()
        parse.add_argument('q', default='')
        parse.add_argument('page', type=int, help='Bad Type: {error_msg}',
                           default=1)
        parse.add_argument('limit', type=int, default=10)
        parse.add_argument('mode', choices=("fork", "source", "mirror", "collaborative"),
                           help='Bad choice: {error_msg}', default="source")
        parse.add_argument('sort', choices=("alpha", "created", "updated", "size", "id"),
                           help='Bad choice: {error_msg}', default="updated")
        parse.add_argument('order', choices=('asc', 'desc'), default="asc",
                           help='Bad choice: {error_msg}')
        args = parse.parse_args()
        return choppy_store.search(args.get('q'), page=args.get('page'), limit=args.get('limit'),
                                   mode=args.get('mode'), sort=args.get('sort'), order=args.get('order'))


class RepoRelease(Resource):
    def get(self, owner, app_name):
        return choppy_store.list_releases(owner, app_name)


class Workflow(Resource):
    pass


class Batch(Resource):
    def post(self, app_name):
        try:
            project_name = uuid.uuid1()
            is_valid_project_name(project_name)
            projects_loc = get_data_dir(
                subdir_name='projects/%s' % project_name)
            parse = reqparse.RequestParser()
            parse.add_argument('file', type=werkzeug.datastructures.FileStorage,
                               location=samples_loc)
            args = parse.parse_args()
            file_name = uuid.uuid1()
            samples_file = args['file']
            samples_file_name = '%s.samples' % file_name
            samples_file.save(samples_file_name)
            samples_file_path = os.path.join(projects_loc,
                                             samples_file_name)
            app_dir = os.path.join(c.app_dir, args.app_name)
            # TODO: support label
            results = run_batch(project_name, app_dir,
                                samples_file_path, None, cromwell_server)
            resp = {
                "message": "Success",
                "data": {
                    "successed": results.get(successed),
                    "failed": results.get(failed),
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


def set_resources(api):
    # Batch submit jobs to cromwell server
    api.add_resource(Batch, '/batch/<app_name>')
    # List all installed apps
    api.add_resource(App, '/installed-apps')
    # Show all apps from choppy app store
    api.add_resource(Repo, '/apps')
    # Show all releases of the app from choppy app store
    api.add_resource(RepoRelease, '/<owner>/<app_name>/releases')


def run_server(args):
    global cromwell_server
    cromwell_server = args.server
    daemon = args.daemon
    framework = args.framework

    app = Flask(__name__)
    api = Api(app)
    set_resources(api)

    if not daemon:
        if c.log_level == 'DEBUG':
            debug = True
        else:
            debug = False
        app.run(debug=debug)
    else:
        #
        # TODO: this starts the built-in server, which isn't the most
        # efficient.  We should use something better.
        #
        if framework == "GEVENT":
            c.print_color(BashColors.OKGREEN, "Starting gevent based server")
            c.print_color(BashColors.OKGREEN, '%s:%s' % get_default_server())
            svc = WSGIServer(get_default_server(), app)
            svc.serve_forever()
        else:
            c.print_color(BashColors.OKGREEN, "Starting bjoern based server")
            host, port = get_default_server()
            c.print_color(BashColors.OKGREEN, '%s:%s' % host, port)
            bjoern.run(app, host, port, reuse_port=True)
