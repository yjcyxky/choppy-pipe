# -*- coding:utf-8 -*-
# Choppy JSON Schema
"""
Handle samples information from web frontend.

{
    # submit模式 / result模式
    # submit模式: sample信息
    # result模式: workflow信息
    "data": [

    ],
    "project": {
        "project_name": "",
        "label": {

        },
        "submitted": "",
        "failed": "",
        "status": ""
    },
    "runtime": {
        "server_name": "localhost",
        "force": True,
        "app_name": "",
        "version": "",
        "created_time": "",
        "updated_time": "",
    },
    "action": [{
        "action_name": "query",
        # 支持三种模式：值模式、引用模式、列表模式
        # 值模式：string, integer, float, boolean
        # 引用模式：project.project_name
        # 列表模式：(string, project.project_name, ...)
        "args": [
            "status",
            "metadata",
        ]
    }]
}
"""

from __future__ import unicode_literals
