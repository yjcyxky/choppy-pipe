# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import os
import re
import uuid
import json
import requests
import logging
import pkg_resources
from bokeh.embed import json_item
from choppy.check_utils import check_dir
from choppy.utils import copy_and_overwrite
from choppy.oss import run_copy_files
from choppy.utils import BashColors


class BasePlugin:
    """
    Plugin class is initialized by plugin args from markdown.
    Plugin args: @plugin_name(arg1=value, arg2=value, arg3=value)
    """
    def __init__(self, context):
        self.logger = logging.getLogger(__name__)
        self.tmp_plugin_dir = str(uuid.uuid1())
        self.plugin_data_dir = os.path.join(self.tmp_plugin_dir, 'plugin')
        self.type2dir = {
            'css': os.path.join(self.plugin_data_dir, 'css'),
            'javascript': os.path.join(self.plugin_data_dir, 'js'),
            'js': os.path.join(self.plugin_data_dir, 'js'),
            'data': os.path.join(self.plugin_data_dir, 'data'),
            'context': os.path.join(self.plugin_data_dir, 'context')
        }

        for dir in self.type2dir.values():
            check_dir(dir, skip=True, force=True)

        # Parse args from markdown new syntax. e.g.
        # @scatter_plot(a=1, b=2, c=3)
        # kwargs = {'a': 1, 'b': 2, 'c': 3}
        self._context = {}.update(context)

        # The target_id will help to index html component position.
        self.target_id = str(uuid.uuid1())

        # The index db for saving key:real_path pairs.
        self._index_db = [{
            'type': 'directory',
            'key': key,
            'value': value
        } for key, value in self.type2dir.items()]

        # All plugin args need to check before next step.
        self._wrapper_check_args()

    def _wrapper_check_args(self):
        """
        Unpack context into keyword arguments of check_plugin_args method.
        """
        self.check_plugin_args(**self._context)

    def check_plugin_args(self, **kwargs):
        """
        All plugin args is holded by self._context.
        you need to check all plugin args when inherit Plugin class.
        """
        raise NotImplementedError('You need to reimplement check_plugin_args method.')

    def filter_ctx_files(self):
        """
        Filter context for getting all files.
        """
        files = []
        pattern = r'^(/)?([^/\0]+(/)?)+$'
        for key, value in self._context:
            if re.match(pattern, value):
                files.append(value)
        return files

    @property
    def context(self):
        return self._context

    @property
    def index_db(self):
        """
        Return index db's records.
        """
        return self._index_db

    def get_index(self, key):
        """
        Get record index from index db.
        """
        for idx, dic in enumerate(self._index_db):
            if dic['key'] == key:
                return idx
        return -1

    def get_value_by_idx(self, idx):
        """
        Get value by using record index from index db.
        """
        if idx >= 0:
            return self._index_db[idx].get('value')

    def set_value_by_idx(self, idx, value):
        if idx >= 0 and idx < len(self._index_db):
            self._index_db[idx].update({
                'value': value
            })

    def search(self, key):
        """
        Search index db by using key.
        """
        # Bug: next func just return one value,
        # so you need to make sure that the key in self._index_db is unique.
        return next((item for item in self._index_db if item["key"] == key), default=None)

    def set_index(self, path, type='css'):
        """
        Add a record into index db.
        """
        key = os.path.basename(path)

        if self.search(key):
            color_msg = BashColors.get_color_msg('The key (%s) is inside of index db. '
                                                 'The value will be updated by new value.' % key)
            self.logger.warning(color_msg)
            idx = next((index for (index, d) in enumerate(self._index_db) if d["key"] == key), None)
            self._index_db[idx] = {
                'type': type,
                'key': key,
                'value': path
            }
        else:
            pattern = r'^%s.*' % self.plugin_data_dir
            matched = re.match(pattern, path)
            # Save file when the file is not in plugin_data_dir.
            if not matched:
                self._save_file(path, type=type)
            else:
                self._index_db.append({
                    'type': type,
                    'key': key,
                    'value': path
                })

    def _get_dest_dir(self, type):
        """
        Get the plugin data directory.
        """
        dest_dir = self.type2dir.get(type.lower())
        return dest_dir

    def _save_file(self, path, type='css'):
        """
        Copy the file to plugin data directory.
        """
        dest_dir = self._get_dest_dir(type)
        if not dest_dir:
            raise NotImplementedError("Can't support the file type: %s" % type)

        if os.path.isfile(path):
            net_path = 'file://' + os.path.abspath(path)
        else:
            net_path = path

        matched = re.match(r'(https|http|file|ftp|oss)://.*', net_path)
        if matched:
            protocol = matched.groups()[0]
            filename = os.path.basename(path)
            dest_filepath = os.path.join(dest_dir, filename)
            # Set index database record.
            self.set_index(dest_filepath, type=type)
            if protocol == 'file':
                copy_and_overwrite(path, dest_filepath)
            elif protocol == 'oss':
                run_copy_files(path, dest_filepath, recursive=False, silent=True)
            else:
                r = requests.get(net_path)
                if r.status_code == 200:
                    with open(dest_filepath, "wb") as f:
                        f.write(r.content)
                else:
                    self.logger.warning('No such file: %s' % path)
        else:
            raise NotImplementedError("Can't support the file type: %s" % path)

    def external_data(self):
        """
        Adding external data files.
        :return: file list.
        """
        pass

    def external_css(self):
        """
        Adding external css files.
        :return: file list:
        """
        pass

    def external_javascript(self):
        """
        Adding external javascript files.
        :return: file list:
        """
        pass

    def prepare(self):
        """
        One of stages: copy all dependencies to plugin data directory.
        """
        css = self.external_css()
        javascript = self.external_javascript()
        data = self.external_data()
        context_files = self.filter_ctx_files()

        filetype = ['css'] * len(css) + ['js'] * len(javascript) + \
                   ['data'] * len(data) + ['context'] * len(context_files)
        filelist = css + javascript + data + context_files
        # TODO: async加速?
        for ftype, file in zip(filetype, filelist):
            self._save_file(file, type=ftype)

    def bokeh(self):
        pass

    def plotly(self):
        pass

    def transform(self):
        """
        The second stage: It's necessary for some plugins to transform data
        or render plugin template before generating javascript code.
        May be you want to reimplement transform method when you have
        a new plugin that is not a plotly or bokeh plugin. If the plugin is
        a plotly or bokeh plugin, you need to reimplement plotly method or
        bokeh method, not transform method.
        (transform, save and index transformed data file.)
        :return:
        """
        bokeh_plot = self.bokeh()
        plotly_plot = self.plotly()  # noqa
        # Only support bokeh in the current version.
        if bokeh_plot:
            dest_dir = self._get_dest_dir(type)
            plot_json = json.dumps(json_item(bokeh_plot, self.target_id))
            plot_json_path = os.path.join(dest_dir, 'plot.json')
            with open(plot_json_path) as f:
                f.write(plot_json)
                self.set_index(plot_json_path, type='json')
        else:
            pass

    def render(self, **kwargs):
        """
        The third stage: rendering javascript snippet. The js code will
        inject into markdown file, and then build as html file.
        :param kwargs: all plugin args.
        """
        raise NotImplementedError('You need to implement render method.')

    def _wrapper_render(self):
        """
        Unpack context into keyword arguments of render method.
        """
        self.render(**self._context)

    def run(self):
        """
        Run three stages step by step.
        """
        self.prepare()
        self.transform()
        self._wrapper_render()

    def get_net_path(self, filename, net_dir=''):
        """
        Get virtual network path for mkdocs server.
        """
        record_idx = self.get_index(filename)
        if record_idx >= 0:
            file_path = self.get_value_by_idx(record_idx)
            virtual_path = file_path.replace(self.tmp_plugin_dir, '')
            if net_dir:
                dest_path = os.path.join(net_dir, virtual_path)
                copy_and_overwrite(file_path, dest_path, is_file=True)
                self.set_value_by_idx(record_idx, dest_path)
            return virtual_path
        else:
            return ''

    def get_real_path(self, filename):
        """
        Get real path in local file system.
        """
        record = self.search(filename)
        if record:
            real_file_path = record.get('value')
            return real_file_path
        else:
            return ''


def get_plugins():
    """ Return a dict of all installed Plugins by name. """

    plugins = pkg_resources.iter_entry_points(group='choppy.plugins')

    return dict((plugin.name, plugin) for plugin in plugins)
