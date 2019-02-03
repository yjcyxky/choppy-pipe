# -*- coding:utf-8 -*-
from __future__ import unicode_literals

import re
import logging
from markdown.preprocessors import Preprocessor
from markdown.extensions import Extension
from choppy.plugin import get_plugins
from choppy.convertor import get_convertors
from choppy.utils import BashColors
from choppy.exceptions import PluginSyntaxError, ValidationError
from choppy.plugin import BasePlugin
from choppy.convertor import BaseConvertor


class Code:
    def __init__(self, code):
        self.logger = logging.getLogger(__name__)
        self._code = code
        self.installed_plugins = get_plugins()
        self.installed_convertors = get_convertors()

    def load_convertor(self, name):
        if name not in self.installed_convertors:
            raise ValidationError('The "{0}" convertor is not installed'.format(name))

        Convertor = self.installed_convertors[name].load()

        if not issubclass(Convertor, BaseConvertor):
            raise ValidationError('{0}.{1} must be a subclass of {2}.{3}'.format(
                                  Convertor.__module__, Convertor.__name__, BaseConvertor.__module__,
                                  BaseConvertor.__name__))

        convertor = Convertor()
        return convertor

    def load_plugin(self, name, context):
        if name not in self.installed_plugins:
            raise ValidationError('The "{0}" plugin is not installed'.format(name))

        Plugin = self.installed_plugins[name].load()

        if not issubclass(Plugin, BasePlugin):
            raise ValidationError('{0}.{1} must be a subclass of {2}.{3}'.format(
                                  Plugin.__module__, Plugin.__name__, BasePlugin.__module__,
                                  BasePlugin.__name__))

        plugin = Plugin(context)
        return plugin

    def _parse(self):
        """
        Parse plugin call for identify plugin name and keyword arguments.
        """
        from choppy.syntax_parser import plugin_kwarg
        from pyparsing import ParseException

        # Split func with args
        pattern = r'^@(?P<plugin_name>[\w]+)(?P<args_str>.*)$'
        matched = re.match(pattern, self._code)
        if matched:
            plugin_name = matched.group('plugin_name')
            args_str = matched.group('args_str')
            color_msg = BashColors.get_color_msg('SUCCESS',
                                                 'Parsed choppy plugin command: %s%s' % (plugin_name, args_str))
            self.logger.info(color_msg)

            try:
                # Bug: maybe error when the argument value is a string as file name.
                # filter_ctx_files function's pattern '^(/)?([^/\0]+(/)?)+$' may treat a string as a file but it's not true.
                items = plugin_kwarg.parseString(args_str).asList()
                plugin_kwargs = {i[0]: i[1] for i in items if len(i) == 2}
            except ParseException:
                color_msg = 'Choppy plugin command(%s): syntax error' % self._code
                self.logger.error(color_msg)
                raise PluginSyntaxError('Can not parse choppy plugin command.')
            print('Plugin name: %s, Plugin kwargs: %s' % (plugin_name, str(plugin_kwargs)))
            self.logger.info('Plugin name: %s, Plugin kwargs: %s' % (plugin_name, str(plugin_kwargs)))
            return plugin_name, plugin_kwargs
        else:
            color_msg = BashColors.get_color_msg('WARNING', 'Can not parse choppy plugin command.')
            self.logger.error(color_msg)
            raise PluginSyntaxError('Can not parse choppy plugin command.')

    def _recursive_call(self, filepath, convertor_key_lst):
        """
        Call convertor in the chain.
        """
        if len(convertor_key_lst) == 1:
            convertor = self.load_convertor(convertor_key_lst[0])
            return convertor.run(filepath)
        else:
            convertor = self.load_convertor(convertor_key_lst[0])
            return self._recursive_call(convertor.run(filepath), convertor_key_lst[1:])

    def _convert_context(self, plugin_kwargs):
        """
        Parse convertor from choppy plugin kwargs, and then call convertor in the chain. (Get real path of all files.)
        """
        context = {}
        for key, value in plugin_kwargs.items():
            if isinstance(value, str):
                convertor_str_lst = [i.strip() for i in value.split('|')]
                if len(convertor_str_lst) == 1:
                    filepath = convertor_str_lst[0]
                else:
                    filepath = convertor_str_lst[0]
                    convertor_key_lst = convertor_str_lst[1:]
                    filepath = self._recursive_call(filepath, convertor_key_lst)
                context.update({
                    key: filepath
                })
            else:
                context.update({
                    key: value
                })
        self.logger.debug('Context: %s' % context)
        return context

    def _extract_context(self, plugin_kwargs):
        context = {}
        for key, value in plugin_kwargs.items():
            convertor_str_lst = [i.strip() for i in value.split('|')]
            # For "filepath | convertor"
            context.update({
                key: convertor_str_lst[0]
            })
        return context

    def generate(self):
        # Get all plugin kwargs and plugin name.
        plugin_name, plugin_kwargs = self._parse()
        # Run convertor and get new plugin kwargs as context.
        context = self._convert_context(plugin_kwargs)
        plugin = self.load_plugin(plugin_name, context)
        # e.g. ["<script id='plot' src=''>", "</script>"]
        return plugin.run()


class ChoppyPluginPreprocessor(Preprocessor):
    """
    Dynamic Plot / Multimedia Preprocessor for Python-Markdown.
    """
    def run(self, lines):
        new_lines = []
        block = []
        flag = False
        start_pattern = r'^@[-\w]+\(.*'
        end_pattern = r'.*\)$'
        for line in lines:
            striped_line = line.strip()
            start_matched = re.match(start_pattern, striped_line)
            end_matched = re.match(end_pattern, striped_line)
            if start_matched:
                flag = True
                block.append(striped_line)
            elif flag:
                if end_matched:
                    block.append(striped_line)
                    code_str = re.sub(r'\s', '', ''.join(block))

                    # Parse plugin call code, and then call plugin.
                    code_instance = Code(code_str)
                    js_code_lines = code_instance.generate()
                    new_lines.extend(js_code_lines)
                else:
                    block.append(line)
            else:
                new_lines.append(line)

        if not new_lines and block:
            new_lines = block
        return new_lines


class ChoppyPluginExtension(Extension):
    def __init__(self, configs={}):
        self.config = configs

    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)

        plugin_preprocessor = ChoppyPluginPreprocessor()
        md.preprocessors.add('plugin_preprocessor', plugin_preprocessor, '<normalize_whitespace')


# http://pythonhosted.org/Markdown/extensions/api.html#makeextension
def makeExtension(*args, **kwargs):
    return ChoppyPluginExtension(*args, **kwargs)


def test():
    import markdown
    text = '''
    # title

    # Just support string, boolean(True/False), integer, float
    @test(
        arg1=1,
        arg2="2",
        arg3=true,
    )
    '''
    plugin = ChoppyPluginExtension(configs={})
    print(markdown.markdown(text, extensions=[plugin]))
