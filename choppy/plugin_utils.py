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


def get_plugin(name):
    from mk_media_extension.plugin import (get_plugins, BasePlugin,
                                           get_internal_plugins) # noqa
    internal_plugins = get_internal_plugins()
    internal_plugin = internal_plugins.get(name)
    if internal_plugin:
        return internal_plugin
    else:
        external_plugins = get_plugins()
        if name not in external_plugins:
            raise Exception('The "{0}" plugin is not installed'.format(name))

        Plugin = external_plugins[name].load()

        if not issubclass(Plugin, BasePlugin):
            raise Exception('{0}.{1} must be a subclass of {2}.{3}'.format(
                            Plugin.__module__, Plugin.__name__, BasePlugin.__module__,
                            BasePlugin.__name__))
        return Plugin
