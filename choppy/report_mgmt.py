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
from choppy.utils import BashColors

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


class InValidReport(Exception):
    pass


class ReportDefaultVar:
    """
    Report Default File Management.
    """
    def __init__(self, app_report_dir):
        self.app_report_dir = app_report_dir
        self.default = os.path.join(self.app_report_dir, 'defaults')
        self.default_vars = self._parse()

    def _parse(self):
        """
        Parse defaults file and convert it to a dict.
        :return: a dict.
        """
        if os.path.isfile(self.default):
            with open(self.default, 'r') as f:
                vars = json.load(f)
                return vars
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
        with open(self.default, 'w') as f:
            json.dump(self.default_vars, f, indent=2, sort_keys=True)


class Context:
    def __init__(self, project_dir, server='localhost'):
        self.logger = logging.getLogger(__name__)
        self.project_dir = project_dir
        host, port, auth = c.get_conn_info(server)
        self.cromwell = Cromwell(host, port, auth)

        self._context = {
            # Mkdocs
            'project_name': os.path.basename(self.project_dir),
            'site_name': '',
            'repo_url': '',
            'site_description': '',
            'site_author': '',
            'copyright': '',
            'extra_css_lst': [],
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
                            'value': 'project/sample_name.md'
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
            'workflow_metadata': self.get_workflow_metadata(),
            'workflow_log': self.get_workflow_log(),
            'workflow_status': self.get_workflow_status(),
            'sample_id_lst': self.get_sample_id_lst(),  # must be after self.get_submitted_jobs() and self.get_failed_jobs().
            'workflow_id_lst': self.get_workflow_id_lst(),  # must be after self.get_submitted_jobs().
        }

        self.set_project_menu(self.get_sample_id_lst())
        self.logger.debug('Report Context: %s' % str(self._context))

    @property
    def context(self):
        return self._context

    def get_workflow_id_lst(self):
        raw_workflow_id_lst = self._context['workflow_id_lst']
        if raw_workflow_id_lst:
            return raw_workflow_id_lst
        else:
            submitted_jobs = self._context['submitted_jobs']
            workflow_id_lst = [row.get('workflow_id') for row in submitted_jobs]
            return workflow_id_lst

    def get_sample_id_lst(self):
        raw_sample_id_lst = self._context['sample_id_lst']
        if raw_sample_id_lst:
            return raw_sample_id_lst
        else:
            submitted_jobs = self._context['submitted_jobs']
            failed_jobs = self._context['failed_jobs']
            sample_id_lst = [row.get('sample_id') for row in submitted_jobs] + [row.get('sample_id') for row in failed_jobs]
            return sample_id_lst

    def set_repo_url(self, repo_url):
        self._context['repo_url'] = repo_url

    def set_site_name(self, site_name):
        self._context['site_name'] = site_name

    def set_site_description(self, site_description):
        self._context['site_description'] = site_description

    def set_site_author(self, site_author):
        self._context['site_author'] = site_author

    def set_copyright(self, copyright):
        self._context['copyright'] = copyright

    def set_extra_css_lst(self, extra_css_lst):
        self._context['extra_css_lst'] = extra_css_lst

    def set_extra_js_lst(self, extra_js_lst):
        self._context['extra_js_lst'] = extra_js_lst

    def set_project_menu(self, sample_list):
        project_menu = []
        for sample in sample_list:
            project_menu.append({
                'key': sample,
                'value': 'project/%s.md' % sample
            })

        self._context['report_menu'][1]['value'] = project_menu

    def get_submitted_jobs(self):
        submitted_file = os.path.join(self.project_dir, 'submitted.csv')

        reader = csv.DictReader(open(submitted_file, 'rt'))
        dict_list = []

        for line in reader:
            dict_list.append(line)

        return dict_list

    def get_failed_jobs(self):
        failed_file = os.path.join(self.project_dir, 'failed.csv')

        reader = csv.DictReader(open(failed_file, 'rt'))
        dict_list = []

        for line in reader:
            dict_list.append(line)

        return dict_list

    def get_workflow_metadata(self):
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

    def get_workflow_status(self):
        """
        Get all workflow's status.
        """
        # TODO: async加速
        workflow_status = []
        workflow_id_lst = self._context['workflow_id_lst']
        for workflow_id in workflow_id_lst:
            workflow_status.append(self.cromwell.query_status(workflow_id))

        self._context['workflow_status'] = workflow_status

    def get_workflow_log(self):
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
                          site_name=''):
        self.set_repo_url(repo_url)
        self.set_site_name(site_name)
        self.set_site_description(site_description)
        self.set_site_author(site_author)
        self.set_copyright(copyright)
        self.set_extra_css_lst(extra_css_lst)
        self.set_extra_js_lst(extra_js_lst)
        self.logger.debug('Report Context(extra context medata): %s' % str(self._context))


class Renderer:
    def __init__(self, template_dir, project_dir, resource_dir=c.resource_dir):
        self.logger = logging.getLogger(__name__)
        self.template_dir = template_dir
        self.project_dir = project_dir
        self.default_file = os.path.join(self.template_dir, 'defaults')
        self.project_report_dir = os.path.join(self.project_dir, 'report_markdown')

        # For mkdocs.yml.template
        self.resource_dir = resource_dir
        self.template_list = self.get_template_files(self.template_dir)

    def render(self, template, output_file, context=None, **kwargs):
        self._validate(**kwargs)
        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template(template)
        with open(output_file, 'w') as f:
            f.write(template.render(context=context, **kwargs))

    def batch_render(self, dest_dir, context=None, **kwargs):
        """
        """
        # All variables from mkdocs.yml must be same with context and kwargs.
        self._gen_docs_config(context=context, **kwargs)

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
            self.logger.info('Render markdown template: %s \n Save to %s' % (str(templ_file), output_file))
            self.render(templ_file, output_file, context=context, **kwargs)
            output_file_lst.append(output_file)

        self.logger.debug('All markdown templates: %s' % str(output_file_lst))
        return output_file_lst

    def _validate(self, **kwargs):
        """
        Validate render data by json schema file.
        """
        pass

    def get_default_vars(self):
        defaults = ReportDefaultVar(self.template_dir)
        return defaults.default_vars

    def get_template_files(self):
        template_files = []
        for root, dirnames, filenames in os.walk(self.template_dir):
            for filename in filenames:
                if re.match(r'.*.md$', filename):
                    template_files.append(os.path.join(root, filename))
        return template_files

    def _gen_docs_config(self, context, **kwargs):
        """
        Generate mkdocs.yml
        """
        mkdocs_templ = os.path.join(self.resource_dir, 'mkdocs.yml.template')
        output_file = os.path.join(self.project_report_dir, '.mkdoc.yml')
        self.logger.debug('Mkdocs config template: %s' % mkdocs_templ)
        self.logger.info('Generate mkdocs config: %s' % output_file)

        env = Environment(loader=FileSystemLoader(self.resource_dir))
        template = env.get_template(mkdocs_templ)
        with open(output_file, 'w') as f:
            f.write(template.render(context=context, **kwargs))


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

    def parse(self, dest_dir):
        pass

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

        # ${project_dir}/report/mkdocs.yml
        self.config_file = os.path.join(self.report_dir, '.mkdocs.yml')
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
          site_description='', site_author='', copyright='', site_name='',
          server='localhost', dev_addr='127.0.0.1:8000', mode='build', force=False):
    report_dir = os.path.join(project_dir, 'report_markdown')
    if os.path.exists(report_dir) and not force:
        logger.info('Skip generate context and render markdown.')
    else:
        tmp_report_dir_uuid = str(uuid.uuid1())
        tmp_report_dir = os.path.join('/tmp', 'choppy', tmp_report_dir_uuid)
        check_dir(tmp_report_dir, skip=True, force=True)

        # Parser: translate markdown new tag to js code.
        logger.debug('Temporary report directory: %s' % tmp_report_dir)
        logger.debug('Parse new markdown syntax.')
        try:
            parser = Parser(app_dir)
            parser.parse(tmp_report_dir)
        except InValidReport as err:
            logger.debug('Warning: %s' % str(err))
            message = "The app %s doesn't support report.\n" \
                      "Please contact the app maintainer." % os.path.basename(app_dir)
            color_msg = BashColors.get_color_msg('WARNING', message)
            logger.info(color_msg)
            # TODO: How to deal with exit way when choppy run as web api mode.
            sys.exit(exit_code.INVALID_REPORT)

        # Context: generate context metadata.
        logger.debug('Generate report context.')
        context = Context(project_dir, server=server)
        context.set_extra_context(repo_url=repo_url, site_description=site_description,
                                  site_author=site_author, copyright=copyright, site_name=site_name,
                                  extra_css_lst=parser.extra_css_lst, extra_js_lst=parser.extra_js_lst)

        # Renderer: render report markdown files.
        logger.debug('Render report markdown files.')
        renderer = Renderer(app_dir, project_dir, resource_dir=resource_dir)
        renderer.batch_render(report_dir, context=context)

    # Report: m
    report = Report(project_dir)
    if mode == 'build':
        logger.debug('Build %s by mkdocs' % report_dir)
        report.build()
    elif mode == 'livereload':
        logger.debug('Serve %s in livereload mode by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='livereload')
    elif mode == 'server':
        logger.debug('Serve %s by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='no-livereload')


def get_mode():
    return ['build', 'server', 'livereload']
