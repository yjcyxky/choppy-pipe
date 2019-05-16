# -*- coding: utf-8 -*-
"""
    choppy_api.modules.app.parameters
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    RESTful API App resources.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from flask_restplus import reqparse

app_install_args = reqparse.RequestParser()
app_install_args.add_argument('name', type=str, required=True,
                              help='An app name.')
app_install_args.add_argument('owner', type=str, required=True,
                              help='The owner of an Choppy app.')
app_install_args.add_argument('version', type=str, required=False,
                              help='The version of an Choppy app.')

app_uninstall_args = reqparse.RequestParser()
app_uninstall_args.add_argument('name', type=str, required=True,
                                help='An app name.')
app_uninstall_args.add_argument('owner', type=str, required=True,
                                help='The owner of an Choppy app.')
app_uninstall_args.add_argument('version', type=str, required=False,
                                help='The version of an Choppy app.')


app_search_args = reqparse.RequestParser()
app_search_args.add_argument('q', type=str, required=True,
                             default='choppy-app', help='keyword')
app_search_args.add_argument('page', type=int, required=False,
                             default=1, help='page number of results to return (1-based).')
app_search_args.add_argument('limit', type=int, required=False,
                             default=10, help='page size of results, maximum page size is 50.')
app_search_args.add_argument('mode', type=str, required=False, default='source',
                             choices=('fork', 'source', 'mirror', 'collaborative'),
                             help='type of repository to search for.')
app_search_args.add_argument('sort', type=str, required=False, default='updated',
                             choices=('alpha', 'created', 'updated', 'size', 'id'),
                             help='sort repos by attribute.')
app_search_args.add_argument('order', type=str, required=False, default='asc',
                             choices=('asc', 'desc'),
                             help='sort order.')
app_search_args.add_argument('topic_only', type=int, required=False, default=1,
                             help='q_str will be as topic name only when topic_only is true.',
                             choices=(0, 1))

app_schema_args = reqparse.RequestParser()
app_schema_args.add_argument('name', type=str, required=True,
                             help='An app name. Maybe a full name, such as `owner/name-version`, '
                                  'When owner and version are not specified.')
app_uninstall_args.add_argument('owner', type=str, required=False, help='The owner of an Choppy app.')
app_uninstall_args.add_argument('version', type=str, required=False, help='The version of an Choppy app.')
