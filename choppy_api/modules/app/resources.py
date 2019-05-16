# -*- coding: utf-8 -*-
"""
    choppy_api.modules.app.resources
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    RESTful API App resources.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import os
from flask import jsonify
from flask_restplus import Namespace, Resource
from choppy.config import get_global_config
from choppy.core.app_utils import (listapps, install_app, uninstall_app)
from choppy.exceptions import AppInstallationFailed, AppUnInstallationFailed
from .parameters import (app_search_args, app_install_args,
                         app_uninstall_args, app_schema_args)
from .models import get_app_info

global_config = get_global_config()
choppy_store = global_config.choppy_store
api = Namespace('apps', description='Choppy app related operations')


@api.route('/installed-apps')
class App(Resource):
    def get(self):
        """List all installed apps.
        """
        apps = listapps()
        resp = {
            "message": 'Success',
            "data": [get_app_info(app) for app in apps]
        }
        return resp, 200


@api.route('/schema')
class RepoSchema(Resource):
    @api.doc(responses={
        200: 'Success.',
        400: "Bad request.",
        500: "Internal Server Error."
    })
    @api.expect(app_schema_args, validate=True)
    def get(self):
        args = app_schema_args.parse_args()
        return jsonify(args), 200


@api.route('/')
class Repo(Resource):
    @api.doc(responses={
        200: "Success.",
        400: "Bad request.",
        500: "Internal Server Error."
    })
    @api.expect(app_search_args, validate=True)
    def get(self):
        """Search apps.
        """
        args = app_search_args.parse_args()
        return choppy_store.search(args.get('q'), page=args.get('page'), limit=args.get('limit'),
                                   mode=args.get('mode'), sort=args.get('sort'), order=args.get('order'), topic_only=args.get('topic_only'))

    @api.doc(responses={
        204: "No content.",
        400: "Bad request.",
        500: "Internal Server Error."
    })
    @api.expect(app_install_args, validate=True)
    def post(self):
        """Install an app.
        """
        args = app_install_args.parse_args()
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
    @api.expect(app_uninstall_args, validate=True)
    def delete(self):
        """Uninstall an app.
        """
        args = app_uninstall_args.parse_args()
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
        """Get all releases of an app.
        """
        return choppy_store.list_releases(owner, app_name)
