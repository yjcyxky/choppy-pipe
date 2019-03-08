# -*- coding:utf-8 -*-
from __future__ import unicode_literals


def listplugins():
    def get_plugin_name_lst(plugins):
        if isinstance(plugins, dict):
            return list(plugins.keys())
        else:
            return []

    try:
        from mk_media_extension.plugin import (get_plugins,
                                               get_internal_plugins) # noqa
        plugins = []
        external_plugins = get_plugin_name_lst(get_plugins())
        internal_plugins = get_plugin_name_lst(get_internal_plugins())
        plugins.extend(external_plugins)
        plugins.extend(internal_plugins)
        return plugins
    except Exception:
        return []


def getplugins():
    try:
        from mk_media_extension.plugin import (get_plugins,
                                               get_internal_plugins) # noqa
        external_plugins = get_plugins()
        internal_plugins = get_internal_plugins()
        external_plugins.update(internal_plugins)
        return external_plugins
    except Exception:
        return dict()
