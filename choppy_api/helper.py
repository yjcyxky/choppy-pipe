# -*- coding: utf-8 -*-
"""
    choppy_api.helper
    ~~~~~~~~~~~~~~~~~

    Helper module.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from functools import partial
from flask import jsonify
from flask_restplus import apidoc
from choppy_api.extensions.api import api_v1


def init_sitemap(app):
    sitemap = sorted(['%s' % rule for rule in app.url_map.iter_rules()])
    return jsonify({'sitemap': sitemap}), 200


def init_swagger_ui():
    return apidoc.ui_for(api_v1)


def register_helper(app, **kwargs):
    app.add_url_rule('/sitemap', endpoint='sitemap',
                     view_func=partial(init_sitemap, app), methods=['GET', ])
    app.add_url_rule('/', endpoint='doc', view_func=init_swagger_ui,
                     methods=['GET', ])

    @app.errorhandler(404)
    def page_not_found(err_msg):
        result = {
            'message': str(err_msg)
        }
        return jsonify(result), 404
