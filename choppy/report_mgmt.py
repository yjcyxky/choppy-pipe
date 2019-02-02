# coding: utf-8
from __future__ import unicode_literals

import logging
import re
import os
import sys
import json
import yaml
import csv
import uuid

from mkdocs import config
from jinja2 import Environment, FileSystemLoader
from mkdocs.commands.build import build as build_docs
from mkdocs.commands.serve import serve as serve_docs

import choppy.config as c
import choppy.exit_code as exit_code
from choppy.cromwell import Cromwell
from choppy.check_utils import check_dir
from choppy.utils import BashColors, copy_and_overwrite, get_copyright
from choppy.exceptions import InValidDefaults, InValidReport

logger = logging.getLogger(__name__)

TEMPLATE_FILES = [
    'about/app_store.md',
    'about/app.md',
    'about/choppy.md',
    'about/license.md',
    'project/sample.md',
    'index.md',
    'defaults'
]


class ReportDefaultVar:
    """
    Report Default File Management.
    """
    def __init__(self, defaults):
        self.defaults = defaults
        self.default_vars = self._parse()

    def _parse(self):
        """
        Parse defaults file and convert it to a dict.
        :return: a dict.
        """
        if os.path.isfile(self.defaults):
            try:
                with open(self.defaults, 'r') as f:
                    vars = json.load(f)
                    return vars
            except json.decoder.JSONDecodeError:
                raise InValidDefaults('The defaults file defined in app is not a valid json.')
        else:
            return dict()

    def get(self, key):
        """
        Get value from defaults file by using key.
        :param key: a string
        :return: value that is related with the key.
        """
        return self.default_vars.get(key)

    def has_key(self, key):
        """
        Whether the key is in defaults file.
        :param key: a string
        :return: boolean(True or False)
        """
        if self.default_vars.get(key):
            return True
        else:
            return False

    def diff(self, key_list):
        """
        Get difference set between default variables and key_list.
        :param key_list: a list that contains all you wanted variable key.
        :return: a set that contains all different keys.
        """
        keys = self.default_vars.keys()
        # key_list need to have more key.
        diff_sets = set(key_list) - set(keys)
        return diff_sets

    def set_default_value(self, key, value):
        """
        Update a default variable by using key:value mode.
        :param key: variable name.
        :param value: variable value.
        :return:
        """
        self.default_vars.update({key: value})

    def set_default_vars(self, vars_dict):
        """
        Update default vars by using dict update method.
        :param vars_dict: a dict that is waiting for update.
        :return:
        """
        self.default_vars.update(vars_dict)

    def get_default_vars(self, key_list):
        """
        Get all keys that are default variables and are in key_list.
        :param key_list: a list that contains all you wanted variable key.
        :return: a list that contains all intersection keys.
        """
        keys = self.default_vars.keys()
        inter_keys = list(set(key_list).intersection(set(keys)))
        return inter_keys

    def show_default_value(self, key_list=list()):
        """
        Show default variables and values that defined in defaults file.
        :param key_list: a list that contains all you wanted variable key.
        :return: a dict, just like defaults json file.
        """
        if len(key_list) > 0:
            inter_keys = self.get_default_vars(key_list)
        else:
            inter_keys = self.default_vars.keys()

        results = dict()
        for key in inter_keys:
            results.update({
                key: self.get(key)
            })

        return results

    def save(self):
        """
        Save all default vars into 'defaults' file. It should be called after you update variable's value.
        """
        with open(self.defaults, 'w') as f:
            json.dump(self.default_vars, f, indent=2, sort_keys=True)


class Context:
    def __init__(self, project_dir, server='localhost'):
        self.logger = logging.getLogger(__name__)
        self.project_dir = project_dir
        host, port, auth = c.get_conn_info(server)
        self.cromwell = Cromwell(host, port, auth)

        self._context = {
            # Mkdocs
            'docs_dir': 'report_markdown',
            'project_name': os.path.basename(self.project_dir),
            'site_name': 'Choppy Report',
            'repo_url': 'http://choppy.3steps.cn',
            'site_description': 'Choppy is a painless reproducibility manager.',
            'site_author': 'choppy',
            'copyright': get_copyright(),
            'extra_css_lst': ['http://kancloud.nordata.cn/2019-02-01-choppy-extra.css'],
            'extra_js_lst': [],
            'report_menu': [
                {
                    'key': 'Home',
                    'value': 'index.md'
                }, {
                    'key': 'Project',
                    'value': [
                        {
                            'key': 'sample_name',
                            'value': 'project/sample.md'
                        }
                    ]
                }, {
                    'key': 'About',
                    'value': [
                        {
                            'key': 'Current App',
                            'value': 'about/app.md'
                        }, {
                            'key': 'App Store',
                            'value': 'about/app_store.md'
                        }, {
                            'key': 'Choppy',
                            'value': 'about/choppy.md'
                        }, {
                            'key': 'App License',
                            'value': 'about/license.md'
                        }
                    ]
                }
            ],
            # Workflow
            'submitted_jobs': self.get_submitted_jobs(),
            'failed_jobs': self.get_failed_jobs(),
            'project_dir': self.project_dir,
            'workflow_metadata': [],
            'workflow_log': [],
            'workflow_status': [],
            'sample_id_lst': [],
            'workflow_id_lst': [],
            'defaults': {},
            'theme_name': 'mkdocs',
        }

        self.logger.debug('Report Context: %s' % str(self._context))

        # Must be after self.get_submitted_jobs() and self.get_failed_jobs().
        self.set_sample_id_lst()
        # Must be after self.get_submitted_jobs().
        self.set_workflow_id_lst()

        # Must be after self.set_sample_id_lst()
        self.set_project_menu(self._context['sample_id_lst'])

        # Must be after self.set_sample_id_lst() and self.set_workflow_id_lst().
        self.set_workflow_metadata()
        self.set_workflow_log()
        self.set_workflow_status()

    @property
    def context(self):
        return self._context

    def set_theme_name(self, theme_name):
        if isinstance(theme_name, str):
            self._context.update({
                'theme_name': theme_name
            })

    def set_defaults(self, defaults):
        if isinstance(defaults, dict):
            self._context.update(defaults)

    def set_workflow_id_lst(self):
        raw_workflow_id_lst = self._context['workflow_id_lst']
        if len(raw_workflow_id_lst) > 0:
            submitted_jobs = self._context['submitted_jobs']
            workflow_id_lst = [row.get('workflow_id') for row in submitted_jobs]
            self._context['workflow_id_lst'] = workflow_id_lst

    def set_sample_id_lst(self):
        raw_sample_id_lst = self._context['sample_id_lst']
        if len(raw_sample_id_lst) > 0:
            submitted_jobs = self._context['submitted_jobs']
            failed_jobs = self._context['failed_jobs']
            sample_id_lst = [row.get('sample_id') for row in submitted_jobs] + [row.get('sample_id') for row in failed_jobs]

            if len(sample_id_lst) > 0:
                self._context['sample_id_lst'] = sample_id_lst

    def set_repo_url(self, repo_url):
        if repo_url:
            self._context['repo_url'] = repo_url

    def set_site_name(self, site_name):
        if site_name:
            self._context['site_name'] = site_name

    def set_site_description(self, site_description):
        if site_description:
            self._context['site_description'] = site_description

    def set_site_author(self, site_author):
        if site_author:
            self._context['site_author'] = site_author

    def set_copyright(self, copyright):
        if copyright:
            self._context['copyright'] = copyright

    def set_extra_css_lst(self, extra_css_lst):
        if len(extra_css_lst) > 0:
            self._context['extra_css_lst'].extend(extra_css_lst)

    def set_extra_js_lst(self, extra_js_lst):
        if len(extra_js_lst) > 0:
            self._context['extra_js_lst'].extend(extra_js_lst)

    def set_project_menu(self, sample_list):
        project_menu = []
        for sample in sample_list:
            project_menu.append({
                'key': sample,
                'value': 'project/%s.md' % sample
            })

        if len(project_menu) > 0:
            # TODO: more security way to update the value of report_menu.
            self._context['report_menu'][1]['value'] = project_menu

    def get_submitted_jobs(self):
        submitted_file = os.path.join(self.project_dir, 'submitted.csv')

        if os.path.exists(submitted_file):
            reader = csv.DictReader(open(submitted_file, 'rt'))
            dict_list = []

            for line in reader:
                dict_list.append(line)

            return dict_list

    def get_failed_jobs(self):
        failed_file = os.path.join(self.project_dir, 'failed.csv')

        if os.path.exists(failed_file):
            reader = csv.DictReader(open(failed_file, 'rt'))
            dict_list = []

            for line in reader:
                dict_list.append(line)

            return dict_list

    def set_workflow_metadata(self):
        """
        Get workflow metadata.
        The order may be different with self._context['sample_id_lst']
        """
        # TODO: async加速
        workflow_metadata = []
        workflow_id_lst = self._context['workflow_id_lst']
        for workflow_id in workflow_id_lst:
            workflow_metadata.append(self.cromwell.query_metadata(workflow_id))

        self._context['workflow_metadata'] = workflow_metadata

    def set_workflow_status(self):
        """
        Get all workflow's status.
        """
        # TODO: async加速
        workflow_status = []
        workflow_id_lst = self._context['workflow_id_lst']
        for workflow_id in workflow_id_lst:
            workflow_status.append(self.cromwell.query_status(workflow_id))

        self._context['workflow_status'] = workflow_status

    def set_workflow_log(self):
        """
        Get all workflow's log.
        """
        # TODO: async加速
        workflow_log = []
        workflow_id_lst = self._context['workflow_id_lst']
        for workflow_id in workflow_id_lst:
            workflow_log.append(self.cromwell.query_logs(workflow_id))

        self._context['workflow_log'] = workflow_log

    def set_extra_context(self, repo_url='', site_description='', site_author='',
                          copyright='', extra_css_lst=[], extra_js_lst=[],
                          site_name='', theme_name='mkdocs'):
        self.set_repo_url(repo_url)
        self.set_site_name(site_name)
        self.set_site_description(site_description)
        self.set_site_author(site_author)
        self.set_copyright(copyright)
        self.set_theme_name(theme_name)
        self.set_extra_css_lst(extra_css_lst)
        self.set_extra_js_lst(extra_js_lst)
        self.logger.debug('Report Context(extra context medata): %s' % str(self._context))


class Renderer:
    def __init__(self, template_dir, project_dir, context, resource_dir=c.resource_dir):
        """
        :param context: a report context.
        """
        self.logger = logging.getLogger(__name__)
        self.template_dir = template_dir
        self.project_dir = project_dir
        self.context = context
        self.context_dict = self.context.context

        self.default_file = os.path.join(self.template_dir, 'defaults')
        self.default_vars = self.get_default_vars()
        self.context.set_defaults({
            'defaults': self.default_vars
        })

        self.project_report_dir = os.path.join(self.project_dir, 'report_markdown')
        check_dir(self.project_report_dir, skip=True, force=True)

        # For mkdocs.yml.template
        self.resource_dir = resource_dir
        self.template_list = self.get_template_files()

    def render(self, template, output_file, **kwargs):
        """
        Render template and write to output_file.
        :param template: a jinja2 template file and the path must be prefixed with `template_dir`
        :param output_file:
        :return:
        """
        self._validate(**kwargs)
        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template(template)
        with open(output_file, 'w') as f:
            f.write(template.render(context=self.context_dict, **kwargs))

    def batch_render(self, dest_dir, **kwargs):
        """
        Batch render template files.
        :param dest_dir: destination directory.
        """
        # All variables from mkdocs.yml must be same with context and kwargs.
        self._gen_docs_config(**kwargs)

        # TODO: async加速?
        markdown_templates = [template for template in TEMPLATE_FILES
                              if re.match(r'.*.md$', template)]
        output_file_lst = []
        for template in markdown_templates:
            templ_file = os.path.join(self.template_dir, template)
            output_file = os.path.join(dest_dir, template)
            templ_dir = os.path.dirname(output_file)
            if not os.path.exists(templ_dir):
                os.makedirs(templ_dir)
            self.logger.info('Render markdown template: %s, Save to %s' % (str(templ_file), output_file))
            # Fix bug: template file path must be prefixed with self.template_dir
            self.render(template, output_file, **kwargs)
            output_file_lst.append(output_file)

        self.logger.debug('All markdown templates: %s' % str(output_file_lst))
        return output_file_lst

    def _validate(self, **kwargs):
        """
        Validate render data by json schema file.
        """
        pass

    def get_default_vars(self):
        defaults = os.path.join(self.template_dir, 'defaults')
        default_var = ReportDefaultVar(defaults)
        return default_var.default_vars

    def get_template_files(self):
        template_files = []
        for root, dirnames, filenames in os.walk(self.template_dir):
            for filename in filenames:
                if re.match(r'.*.md$', filename):
                    template_files.append(os.path.join(root, filename))
        return template_files

    def _gen_docs_config(self, **kwargs):
        """
        Generate mkdocs.yml
        """
        mkdocs_templ = os.path.join(self.resource_dir, 'mkdocs.yml.template')
        output_file = os.path.join(self.project_dir, '.mkdocs.yml')
        self.logger.debug('Mkdocs config template: %s' % mkdocs_templ)
        self.logger.info('Generate mkdocs config: %s' % output_file)

        env = Environment(loader=FileSystemLoader(self.resource_dir))
        template = env.get_template('mkdocs.yml.template')
        with open(output_file, 'w') as f:
            f.write(template.render(context=self.context_dict, **kwargs))


class Parser:
    def __init__(self, app_dir):
        self.app_dir = app_dir
        self.app_report_dir = os.path.join(self.app_dir, 'report')
        # Check whether report templates is valid in an app.
        self._check_report()
        # Need to set extra_css_lst and extra_js_lst
        self._extra_css_lst = []
        self._extra_js_lst = []
        pass

    @property
    def extra_css_lst(self):
        return self._extra_css_lst

    @property
    def extra_js_lst(self):
        return self._extra_js_lst

    def _copy_app_templates(self, dest_dir):
        copy_and_overwrite(self.app_report_dir, dest_dir)

    def parse(self, dest_dir):
        # Fix bug: template files exist when all markdown files don't need to parse.
        #          so Parser need to parse markdown file from dest_dir
        self._copy_app_templates(dest_dir)

    def _check_report(self):
        current_dir = os.getcwd()
        app_name = os.path.basename(self.app_dir)
        if not os.path.exists(self.app_report_dir):
            raise InValidReport('Invalid App Report: Not Found %s in %s' % ('report', app_name))
        else:
            os.chdir(self.app_report_dir)

        for file in TEMPLATE_FILES:
            not_found_files = []
            if os.path.exists(file):
                continue
            else:
                not_found_files.append(file)

        os.chdir(current_dir)
        if len(not_found_files) > 0:
            raise InValidReport('Invalid App Report: Not Found %s in %s' % (str(not_found_files), app_name))


class Report:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.report_dir = os.path.join(self.project_dir, 'report_markdown')
        self.site_dir = os.path.join(self.project_dir, 'report_html')

        # ${project_dir}/.mkdocs.yml
        self.config_file = os.path.join(self.project_dir, '.mkdocs.yml')
        self.config = None

        self.logger = logging.getLogger(__name__)
        self._get_raw_config()

    def _check_config(self, msg, load_config=True):
        if os.path.isfile(self.config_file):
            if load_config:
                self.config = config.load_config(config_file=self.config_file,
                                                 site_dir=self.site_dir)
        else:
            raise Exception(msg)

    def _get_raw_config(self):
        with open(self.config_file) as f:
            self.raw_config = yaml.load(f)

    def update_config(self, key, value, append=False):
        """
        Update mkdocs config.
        """
        if append:
            # It will be failed when the value is None.
            # e.g. extra_css or extra_javascript
            if isinstance(self.raw_config.get(key), list):
                self.raw_config.get(key).append(value)
        else:
            self.raw_config.update({
                key: value
            })

    def save_config(self):
        with open(self.config_file, 'w') as f:
            f.write(self.raw_config)

    def build(self):
        self._check_config("Attempting to build docs but the mkdocs.yml doesn't exist."
                           " You need to call render/new firstly.")
        build_docs(self.config, live_server=False, dirty=False)

    def server(self, dev_addr=None, livereload='livereload'):
        self._check_config("Attempting to serve docs but the mkdocs.yml doesn't exist."
                           " You need to call render/new firstly.", load_config=False)
        serve_docs(config_file=self.config_file, dev_addr=dev_addr, livereload=livereload)


def build(app_dir, project_dir, resource_dir=c.resource_dir, repo_url='',
          site_description='', site_author='choppy', copyright=get_copyright(),
          site_name='Choppy Report', server='localhost', dev_addr='127.0.0.1:8000',
          theme_name='mkdocs', mode='build', force=False):
    report_dir = os.path.join(project_dir, 'report_markdown')
    if os.path.exists(report_dir) and not force:
        logger.info('Skip generate context and render markdown.')
    else:
        tmp_report_dir_uuid = str(uuid.uuid1())
        tmp_report_dir = os.path.join('/tmp', 'choppy', tmp_report_dir_uuid)
        check_dir(tmp_report_dir, skip=True, force=True)

        # Parser: translate markdown new tag to js code.
        logger.debug('Temporary report directory: %s' % tmp_report_dir)
        logger.info('1. Try parse new markdown syntax.')
        try:
            parser = Parser(app_dir)
            parser.parse(tmp_report_dir)
            logger.info(BashColors.get_color_msg('SUCCESS', 'Parse markdown successfully.'))
        except InValidReport as err:
            logger.debug('Warning: %s' % str(err))
            message = "The app %s doesn't support report.\n" \
                      "Please contact the app maintainer." % os.path.basename(app_dir)
            color_msg = BashColors.get_color_msg('WARNING', message)
            logger.info(color_msg)
            # TODO: How to deal with exit way when choppy run as web api mode.
            sys.exit(exit_code.INVALID_REPORT)

        # Context: generate context metadata.
        logger.info('\n2. Generate report context.')
        ctx_instance = Context(project_dir, server=server)
        ctx_instance.set_extra_context(repo_url=repo_url, site_description=site_description,
                                       site_author=site_author, copyright=copyright, site_name=site_name,
                                       theme_name=theme_name, extra_css_lst=parser.extra_css_lst,
                                       extra_js_lst=parser.extra_js_lst)
        logger.info('Context: %s' % ctx_instance.context)
        logger.info(BashColors.get_color_msg('SUCCESS', 'Context: generate report context successfully.'))

        # Renderer: render report markdown files.
        logger.info('\n3. Render report markdown files.')
        # Fix bug: Renderer need to get template file from temporary report directory.
        renderer = Renderer(tmp_report_dir, project_dir, context=ctx_instance, resource_dir=resource_dir)
        renderer.batch_render(report_dir)
        logger.info(BashColors.get_color_msg('SUCCESS', 'Render report markdown files successfully.'))

    # Report: build markdown files to html.
    report = Report(project_dir)
    if mode == 'build':
        logger.info('\n4. Build %s by mkdocs' % report_dir)
        report.build()
        site_dir = os.path.join(project_dir, 'report_html')
        color_msg = BashColors.get_color_msg('SUCCESS', 'Build markdown files successfully. '
                                                        '(Files in %s)' % site_dir)
        logger.info(color_msg)
    elif mode == 'livereload':
        logger.info('\n4. Serve %s in livereload mode by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='livereload')
    elif mode == 'server':
        logger.info('\n4. Serve %s by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='no-livereload')


def get_mode():
    return ['build', 'server', 'livereload']
