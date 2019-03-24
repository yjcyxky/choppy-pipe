# coding: utf-8
"""
Report management module:
1. Building report contains four stages: context stage, preprocessor stage, renderer stage, and report stage.
2. Context will get all environment variables in context stage, these variables will be used for remaining stages.
3. Preprocessor will check the app's report whether is valid or not and copy all template files from app directory to temporary report directory in preprocessor stage.
4. Renderer will render all template files in temporary report directory and write to report markdown directory of a project, and then copy all dependency files of markdown files to the same directory.
5. Report will call mkdocs to build markdown files as html files. mkdocs will run a series of plugins, such as plot plugins, format conversion plugins, and evaluation plugins, to parse new markdown syntax. and then build markdown files.

Plot plugin for generate dynamic interactive plot or static image.
Format conversion plugin for converting one format to another.
Evaluation plugin for get value from the expression.
"""
from __future__ import unicode_literals

import logging
import re
import os
import sys
import json
import yaml
import csv
import uuid
import verboselogs

from mkdocs import config as mkdocs_config
from os.path import join as join_path
from jinja2 import Environment, FileSystemLoader, BaseLoader
from jinja2.exceptions import TemplateSyntaxError

import choppy.config as c
import choppy.exit_code as exit_code
from choppy.cromwell import Cromwell
from choppy.check_utils import check_dir
from choppy.utils import (copy_and_overwrite, get_copyright, clean_files)
from choppy.exceptions import InValidReport

logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger(__name__)

# Any app report MUST have these template files.
BASED_TEMPLATE_FILES = [
    'about/app_store.md',
    'about/app.md',
    'about/choppy.md',
    'about/license.md',
    'project/sample.md',
    'index.md',
    'defaults'
]


def find_extra_templ_files(template_dir):
    template_files = []
    for root, dirnames, filenames in os.walk(template_dir):
        for filename in filenames:
            if re.match(r'.*.md$', filename):
                file_path = join_path(root, filename)
                # Muse be no prefix in template file path
                template = file_path.replace(template_dir, '').strip('/')
                template_files.append(template)
    diff_sets = list(set(template_files) - set(BASED_TEMPLATE_FILES))
    return diff_sets


class ReportDefaultVar:
    """
    Report defaults file management interface. App developer can set default variable in the defaults file and ReportDefaultVar will maintain all variables in the memory from defaults file. Moreover user can modify the default value in the defaults file by using ReportDefaultVar's methods.
    """
    def __init__(self, defaults):
        from choppy.json_checker import check_json
        check_json(defaults)

        self.defaults = defaults
        self.default_vars = self._parse()

    def _parse(self):
        """
        Parse defaults file and convert it to a dict.

        :return: a dict.
        """
        if os.path.isfile(self.defaults):
            with open(self.defaults, 'r') as f:
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
        with open(self.defaults, 'w') as f:
            json.dump(self.default_vars, f, indent=2, sort_keys=True)


class Context:
    """
    The context class maintain a context database that store metadata related with project and provide a set of manipulation functions.
    """
    def __init__(self, project_dir, server='localhost', editable=True,
                 sample_id_pattern='', cached_metadata=True, by_workflow=True,
                 enable_media_extension=True, templ_dir=None, app_name=None):
        self.logger = logging.getLogger('choppy.report_mgmt.Context')
        if not (app_name or templ_dir):
            raise Exception("Either app_name or templ_dir must exits.")

        self.project_dir = project_dir

        self._context = {
            # For Mkdocs
            'enable_media_extension': enable_media_extension,
            'app_name': app_name,
            'app_installation_dir': c.app_dir,
            'current_app_dir': None,
            'editable': editable,
            'project_dir': self.project_dir,
            'docs_dir': 'report_markdown',
            'html_dir': 'report_html',
            'plugin_dir': join_path(self.project_dir, 'report_html'),
            'project_name': os.path.basename(self.project_dir),
            'site_name': 'Choppy Report',
            'repo_url': 'http://choppy.3steps.cn',
            'site_description': 'Choppy is a painless reproducibility manager.',
            'site_author': 'choppy',
            'copyright': get_copyright(),
            'iframe_mode': c.enable_iframe,
            'extra_header_js_lst': [
                # For non iframe mode.
                "http://kancloud.nordata.cn/2019-03-22-load-script-0.1.3.js",
                "http://kancloud.nordata.cn/2019-03-22-web-inject.min.js"
            ],
            'extra_css_lst': [
                "http://kancloud.nordata.cn/2019-03-21-jquery-confirm.min.css",
                "http://kancloud.nordata.cn/2019-03-21-loading.css",
                "http://kancloud.nordata.cn/2019-03-24-choppy-custom.css"
            ],
            'extra_js_lst': [
                # For main page.
                "http://kancloud.nordata.cn/2019-03-21-jquery-2.1.1.min.js",
                "http://kancloud.nordata.cn/2019-03-21-jquery-confirm.min.js",
                "http://kancloud.nordata.cn/2019-03-21-loading.js",
                "http://kancloud.nordata.cn/2019-03-21-notify.js",
                "http://kancloud.nordata.cn/2019-03-21-stackedit-lib.js",
                "http://kancloud.nordata.cn/2019-03-21-stackedit.js",
                "http://kancloud.nordata.cn/2019-02-27-iframeResizer.min.js",
                "http://kancloud.nordata.cn/2019-03-21-choppy-custom.js"
            ],
            'theme_name': 'mkdocs',

            # For App
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
            'cached_metadata': cached_metadata,
            'submitted_jobs': None,
            'failed_jobs': None,
            'workflow_metadata': [],
            'workflow_log': [],
            'workflow_status': [],
            'sample_id_lst': [],
            'workflow_id_lst': [],
            'ids': {},  # All sample_id: workflow_id key value pairs.
            'defaults': {},  # from report defaults file.
            'cached_files': {}
        }

        if app_name:
            default_file = join_path(join_path(c.app_dir, app_name), 'report', 'defaults')
            report_dir = join_path(c.app_dir, app_name, 'report')
        elif templ_dir:
            default_file = join_path(templ_dir, 'defaults')
            report_dir = templ_dir

        default_vars = self.get_default_vars(default_file)
        self.set_defaults({
            'defaults': default_vars
        })
        self.logger.debug('Report Context: %s' % str(self._context))

        if app_name:
            self._context['current_app_dir'] = join_path(c.app_dir, app_name)

            host, port, auth = c.get_conn_info(server)
            self.cromwell = Cromwell(host, port, auth)

            self._context['submitted_jobs'] = self.get_submitted_jobs()
            self._context['failed_jobs'] = self.get_failed_jobs()

            # Must be after self.get_submitted_jobs() and self.get_failed_jobs().
            self.set_sample_id_lst()
            # Must be after self.get_submitted_jobs().
            self.set_workflow_id_lst()
            # Set id dict.
            self.set_id_dict()

            # Allow user specify a sample id pattern to get a subset of samples
            pattern = r'%s' % sample_id_pattern
            sample_id_set = [sample_id for sample_id in self._context['sample_id_lst']
                             if re.match(pattern, sample_id)]

            # Must be after self.set_sample_id_lst()
            sample_id_lst = sample_id_set if sample_id_pattern else self.get_successed_sample_ids()
            self.set_project_menu(sample_id_lst)

            # Must be after self.set_sample_id_lst() and self.set_workflow_id_lst().
            self.set_workflow_log(sample_id_lst)
            self.set_workflow_status(sample_id_lst)

            # Cached files that user want to save, sample_id as key and workflow's outputs as value
            # _set_cached_files function will:
            # 1. cache workflow metadata simultaneously when by_workflow is True.
            # 2. set file links what were related with sample ids. sample ids can be specified by users, otherwise all sample ids.
            # 3. files that defined in workflow output block or report defaults file (cached_file_list field).
            self._set_cached_files(sample_id_lst=sample_id_set, workflow=by_workflow)
        else:
            self.set_project_menu(self.sample_id_lst)

        self.set_menu(report_dir)

    @property
    def context(self):
        """
        Return the context's value.
        """
        return self._context

    @property
    def sample_id_lst(self):
        if self._context['app_name']:
            return self._context['sample_id_lst']
        else:
            return self._context['defaults'].get('sample_id_lst', [])

    def _parse_task_outputs(self, metadata):
        """
        Parse task outputs from cromwell metadata.
        """
        # TODO: four level for loop is too bad, how to improve it?
        outputs = {}
        # TODO: whether is it necessary to hold all workflow metadata?
        calls = metadata.get('calls')
        # serveral tasks in calls
        for task_name in calls.keys():
            task_lst = calls.get(task_name)
            # may be several tasks have same task name.
            for task in task_lst:
                task_outputs = task.get('outputs')
                # one task have sevaral outputs.
                for output_key in task_outputs.keys():
                    key = '%s.%s' % (task_name, output_key)
                    output = outputs[key] = task_outputs.get(output_key)
                    # handle output directory
                    if isinstance(output, list):
                        pattern = r'^([-\w/:.]+%s).*$' % output_key
                        # MUST BE matched. Need assert or more friendly way?
                        matched = re.match(pattern, output[0])
                        output_dir = matched.groups()[0]
                        outputs[key] = output_dir

                stderr = '%s.stderr' % task_name
                stdout = '%s.stdout' % task_name
                outputs[stderr] = task.get('stderr')
                outputs[stdout] = task.get('stdout')
        return outputs

    def _parse_workflow_outputs(self, metadata):
        """
        Parse workflow outputs from cromwell metadata.
        """
        outputs = {}
        workflow_outputs = metadata.get('outputs')
        for output_key in workflow_outputs.keys():
            output = outputs[output_key] = workflow_outputs.get(output_key)
            # handle output directory
            if isinstance(output, list):
                pattern = r'^([-\w/:.]+%s).*$' % output_key
                # MUST BE matched. Need assert or more friendly way?
                matched = re.match(pattern, output[0])
                output_dir = matched.groups()[0]
                outputs[output_key] = output_dir

        return outputs

    def _get_file_links(self, workflow_id, workflow=True):
        metadata = self._get_workflow_metadata(workflow_id=workflow_id)
        if self._context['cached_metadata']:
            self._context['workflow_metadata'].append(metadata)

        if workflow:
            # syntax: [workflow].[output]
            # e.g.: test_rna_seq.read_2p
            workflow_outputs_dict = self._parse_workflow_outputs(metadata)
            return workflow_outputs_dict
        else:
            task_outputs = self._parse_task_outputs(metadata)
            file_links_dict = {}
            defaults = self._context.get('defaults')
            cached_file_list = defaults.get('cached_file_list', [])
            for cached_file_key in cached_file_list:
                # syntax: [workflow].[task].[output]
                # e.g.: test_rna_seq.trimmomatic.read_2p
                cached_file = task_outputs.get(cached_file_key)
                if cached_file:
                    file_links_dict.update({
                        cached_file_key: cached_file
                    })
                else:
                    self.logger.warning('No such key in project outputs: %s.' % cached_file_key)
            return file_links_dict

    def _get_sample_id(self, workflow_id):
        """
        Get sample id by workflow id.

        :return: sample_id
        """
        return self._context['ids'].get(workflow_id)

    def _get_workflow_id(self, sample_id):
        """
        Get workflow id by sample_id

        :param: sample_id: sample id in a project samples file that is setting by user.
        """
        # key -- workflow_id, value -- sample_id
        for key, value in self._context['ids'].items():
            if value == sample_id:
                return key

    def _set_cached_files(self, workflow_id_lst=None, sample_id_lst=None,
                          workflow=True):
        """
        Get real link of files that list in cached_file_list.

        Example
        "sample_id": {
            "test_rna_seq.bam": "oss://pgx-cromwell-rna-seq/test_rna_seq/ec30ad38-bc22-4c46-9693-7e9321d3e8ae/call-samtools/FUSCCTNBC007_1P.sorted.bam"
        }
        """
        if workflow_id_lst:
            self._context['cached_files'] = {
                self._get_sample_id(workflow_id): self._get_file_links(workflow_id, workflow=workflow)
                for workflow_id in workflow_id_lst
            }
        elif sample_id_lst:
            self._context['cached_files'] = {
                sample_id: self._get_file_links(self._get_workflow_id(sample_id), workflow=workflow)
                for sample_id in sample_id_lst
            }

    def get_default_vars(self, default_file):
        default_var = ReportDefaultVar(default_file)
        return default_var.default_vars

    def set_theme_name(self, theme_name):
        if isinstance(theme_name, str):
            self._context.update({
                'theme_name': theme_name
            })

    def set_defaults(self, defaults):
        if isinstance(defaults, dict):
            self._context.update(defaults)

    def set_id_dict(self):
        """
        Generate workflow_id: sample_id dict.

        :return:
        """
        raw_workflow_id_lst = self._context['workflow_id_lst']
        if len(raw_workflow_id_lst) > 0:
            submitted_jobs = self._context['submitted_jobs']
            workflow_id_lst = [row.get('workflow_id') for row in submitted_jobs]
            sample_id_lst = [row.get('sample_id') for row in submitted_jobs]
            self._context['ids'] = dict(zip(workflow_id_lst, sample_id_lst))

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

            self._context['sample_id_lst'] = sample_id_lst

    def get_successed_sample_ids(self):
        submitted_jobs = self._context['submitted_jobs']
        sample_id_lst = [row.get('sample_id') for row in submitted_jobs]
        return sample_id_lst

    def get_failed_sample_ids(self):
        failed_jobs = self._context['failed_jobs']
        sample_id_lst = [row.get('sample_id') for row in failed_jobs]
        return sample_id_lst

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

    def set_menu(self, templ_dir, strip_pattern=''):
        """
        Add extra menu item.
        """
        # Allowed user to add more markdown files except that defined in BASED_TEMPLATE_FILES
        extra_files = find_extra_templ_files(templ_dir)

        for item in extra_files:
            key = item.strip('/').split('/')[0].title()
            basename = os.path.basename(item).split('.md')[0].title()
            file_path = item.replace(strip_pattern, '').strip('/')
            index = next((index for (index, d) in enumerate(self._context['report_menu'])
                         if d["key"] == key), None)
            if index:
                project_menu = {
                    'key': basename,
                    'value': file_path
                }
                self._context['report_menu'][index]['value'].append(project_menu)
            else:
                menu = {
                    'key': key,
                    'value': [
                        {
                            'key': basename,
                            'value': file_path
                        }
                    ]
                }
                self._context['report_menu'].append(menu)

    def set_project_menu(self, sample_list):
        project_menu = []
        for sample in sample_list:
            project_menu.append({
                'key': sample,
                'value': 'project/%s.md' % sample
            })

        if len(project_menu) > 0:
            # TODO: more security way to update the value of report_menu.
            # index 1 is "Project"
            self._context['report_menu'][1]['value'] = project_menu

    def get_submitted_jobs(self):
        # Fix bug: can not get project_dir by self._context.get('project_dir')
        # self._context doesn't exist when get_submmitted_jobs is called.
        submitted_file = join_path(self.project_dir, 'submitted.csv')

        dict_list = []
        if os.path.exists(submitted_file):
            reader = csv.DictReader(open(submitted_file, 'rt'))

            for line in reader:
                dict_list.append(line)

        return dict_list

    def get_failed_jobs(self):
        # Fix bug: can not get project_dir by self._context.get('project_dir')
        # self._context doesn't exist when get_failed_jobs is called.
        failed_file = join_path(self.project_dir, 'failed.csv')

        # Fix bug: failed_jobs must be iterable nor None
        # so we need return empty list when failed.csv doesn't exist.
        dict_list = []
        if os.path.exists(failed_file):
            reader = csv.DictReader(open(failed_file, 'rt'))

            for line in reader:
                dict_list.append(line)

        return dict_list

    def _get_workflow_metadata(self, workflow_id=None):
        """
        Get workflow metadata.
        """
        if workflow_id:
            return self.cromwell.query_metadata(workflow_id)
        else:
            # TODO: async加速?
            # The order may be different with self._context['sample_id_lst']
            workflow_id_lst = self._context['workflow_id_lst']
            for workflow_id in workflow_id_lst:
                # TODO: handle network error.
                yield self.cromwell.query_metadata(workflow_id)

    def set_workflow_status(self, sample_id_lst=None):
        """
        Get all workflow's status.
        """
        workflow_status = []
        if sample_id_lst:
            workflow_id_lst = [self._get_workflow_id(sample_id) for sample_id in sample_id_lst]
        else:
            # TODO: async加速
            workflow_id_lst = self._context['workflow_id_lst']

        for workflow_id in workflow_id_lst:
            workflow_status.append(self.cromwell.query_status(workflow_id))

        self._context['workflow_status'] = workflow_status

    def set_workflow_log(self, sample_id_lst=None):
        """
        Get all workflow's log.
        """
        # TODO: async加速
        workflow_log = []

        if sample_id_lst:
            workflow_id_lst = [self._get_workflow_id(sample_id) for sample_id in sample_id_lst]
        else:
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
    """
    Report renderer class that render all templates related with a specified app and copy
     all dependent files to destination directory.
    """
    def __init__(self, template_dir, dest_dir, context, resource_dir=c.resource_dir):
        """
        :param template_dir: a directory that contains app template files.
        :param context: a report context.
        """
        self.logger = logging.getLogger('choppy.report_mgmt.Renderer')
        self.template_dir = template_dir
        self.context = context
        self.context_dict = self.context.context

        self.dest_dir = dest_dir
        self.project_report_dir = join_path(dest_dir, 'report_markdown')

        # For mkdocs.yml.template?
        self.resource_dir = resource_dir
        # To validate template files?
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
        try:
            template = env.get_template(template)
            with open(output_file, 'w') as f:
                f.write(template.render(context=self.context_dict, **kwargs))
        except TemplateSyntaxError as err:
            self.logger.warning(str(err))
            pass

    def _render_sample_report(self, templ_file, sample_id, output_file, **kwargs):
        self._validate(**kwargs)

        with open(templ_file, 'r') as f:
            string = f.read()
            updated_string = '{% set sample_id = "' + sample_id + '" %}' + string
            rtemplate = Environment(loader=BaseLoader).from_string(updated_string)
            try:
                with open(output_file, 'w') as f:
                    f.write(rtemplate.render(context=self.context_dict, **kwargs))
            except TemplateSyntaxError as err:
                self.logger.warning(str(err))

    def batch_render(self, **kwargs):
        """
        Batch render template files.
        """
        # All variables from mkdocs.yml must be same with context and kwargs.
        self._gen_docs_config(**kwargs)

        # TODO: async加速?
        TEMPLATE_FILES = BASED_TEMPLATE_FILES + find_extra_templ_files(self.template_dir)
        markdown_templates = [template for template in TEMPLATE_FILES
                              if re.match(r'.*.md$', template)]
        output_file_lst = []
        for template in markdown_templates:
            templ_file = join_path(self.template_dir, template)
            output_file = join_path(self.project_report_dir, template)
            templ_dir = os.path.dirname(output_file)
            if not os.path.exists(templ_dir):
                os.makedirs(templ_dir)

            if template == 'project/sample.md':
                for sample_id in self.context.sample_id_lst:
                    output_file = join_path(self.project_report_dir,
                                            os.path.dirname(template),
                                            '%s.md' % sample_id)
                    self.logger.info('Render markdown template: %s, Save to %s'
                                     % (str(templ_file), output_file))
                    self._render_sample_report(templ_file, sample_id,
                                               output_file, **kwargs)
            else:
                self.logger.info('Render markdown template: %s, Save to %s'
                                 % (str(templ_file), output_file))
                # Fix bug: template file path must be prefixed with self.template_dir
                # render function have set the FileSystemLoader so we need to pass template instead of templ_file.
                self.render(template, output_file, **kwargs)
                output_file_lst.append(output_file)

        self.logger.debug('All markdown templates: %s' % str(output_file_lst))
        return output_file_lst

    def _validate(self, **kwargs):
        """
        Validate render data by json schema file.
        """
        pass

    def get_dependent_files(self):
        """
        Get all dependent files from temporary report directory except markdown template files. e.g. images, data etc. Maybe these files are generated by Preprocessor class.
        """
        dependent_files = []
        for root, dirnames, filenames in os.walk(self.template_dir):
            for filename in filenames:
                if not re.match(r'.*.md$', filename):
                    dependent_files.append(join_path(root, filename))
        self.logger.info('Markdown dependent files: %s' % str(dependent_files))
        return dependent_files

    def copy_dependent_files(self):
        dependent_files = self.get_dependent_files()
        for file in dependent_files:
            # copy process may be wrong when filename start with '/'
            filename = file.replace(self.template_dir, '').strip('/')
            copy_and_overwrite(file, join_path(self.project_report_dir, filename), is_file=True)

    def get_template_files(self):
        template_files = []
        for root, dirnames, filenames in os.walk(self.template_dir):
            for filename in filenames:
                if re.match(r'.*.md$', filename):
                    template_files.append(join_path(root, filename))
        return template_files

    def _gen_docs_config(self, **kwargs):
        """
        Generate mkdocs.yml
        """
        mkdocs_templ = join_path(self.resource_dir, 'mkdocs.yml.template')
        output_file = join_path(self.dest_dir, '.mkdocs.yml')
        self.logger.debug('Mkdocs config template: %s' % mkdocs_templ)
        self.logger.info('Generate mkdocs config: %s' % output_file)

        env = Environment(loader=FileSystemLoader(self.resource_dir))
        template = env.get_template('mkdocs.yml.template')
        with open(output_file, 'w') as f:
            f.write(template.render(context=self.context_dict, **kwargs))


class Preprocessor:
    """
    Report preprocessor for prepare rendering and report building environment.
    """
    def __init__(self, report_dir, context):
        self.app_report_dir = report_dir
        # Check whether report templates is valid in an app.
        self._check_report()
        self._context = context

    def _copy_app_templates(self, dest_dir):
        """
        Copy app templates from app directory to temporary report directory.
        """
        copy_and_overwrite(self.app_report_dir, dest_dir)

    def process(self, dest_dir):
        # TODO: Need to parse report and prepare all dependencies.
        self._copy_app_templates(dest_dir)

    def _check_report(self):
        current_dir = os.getcwd()
        if not os.path.exists(self.app_report_dir):
            raise InValidReport("Current app doesn't support report. "
                                "Please contact the app maintainer.")
        else:
            os.chdir(self.app_report_dir)

        for file in BASED_TEMPLATE_FILES:
            not_found_files = []
            if os.path.exists(file):
                continue
            else:
                not_found_files.append(file)

        os.chdir(current_dir)
        if len(not_found_files) > 0:
            raise InValidReport('Invalid app report templates: Not Found %s in %s'
                                % (str(not_found_files), os.path.basename(self.app_report_dir)))


class Report:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.report_dir = join_path(self.project_dir, 'report_markdown')
        self.site_dir = join_path(self.project_dir, 'report_html')

        # ${project_dir}/.mkdocs.yml
        self.config_file = join_path(self.project_dir, '.mkdocs.yml')
        self.config = None

        self.logger = logging.getLogger('choppy.report_mgmt.Report')
        self._get_raw_config()

    def _check_config(self, msg, load_config=True):
        if os.path.isfile(self.config_file):
            if load_config:
                self.config = mkdocs_config.load_config(config_file=self.config_file,
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

    def build(self, templ_type='html'):
        from mkdocs.commands.build import build as build_docs
        self._check_config("Attempting to build docs but the mkdocs.yml doesn't exist."
                           " You need to call render/new firstly.")
        build_docs(self.config, live_server=False, dirty=False,
                   templ_type=templ_type)

    def server(self, dev_addr=None, livereload='livereload', templ_type='html'):
        from mkdocs.commands.serve import dev_serve as serve_docs
        self._check_config("Attempting to serve docs but the mkdocs.yml doesn't exist."
                           " You need to call render/new firstly.", load_config=False)
        serve_docs(config_file=self.config_file, dev_addr=dev_addr,
                   livereload=livereload, site_dir=self.site_dir,
                   templ_type=templ_type)


def build(project_dir, resource_dir=c.resource_dir, repo_url='',
          site_description='', site_author='choppy', copyright=get_copyright(),
          site_name='Choppy Report', server='localhost', dev_addr='127.0.0.1:8000',
          theme_name='mkdocs', mode='build', force=False, editable=True,
          sample_id_pattern='', cached_metadata=True, by_workflow=True,
          enable_media_extension=True, templ_dir=None, app_name=None):
    """
    Build an app report.

    :param: app_name: an app name, like rna-seq-v1.0.0
    :param: project_dir: a project output directory.
    :param: resource_dir: a directory that host template files.
    :param: repo_url: a repo url and its prefix is 'http://choppy.3steps.cn/'.
    :param: site_decription:
    :param: site_author:
    :param: copyright:
    :param: site_name: it will show as website logo.
    :param: server: a cromwell server name
    :param: dev_addr:
    :param: theme_name:
    :param: mode: mkdocs be ran as which mode, build, livereload or server.
    :param: force: force to renew the mkdocs outputs.
    :param: editable: whether the report can be edited by users.
    :param: sample_id_pattern: which samples were selected by user.
    :param: cached_metadata: whether cache related workflow metadata.
    :param: by_workflow: whether treat workflow output block as the source of cached file list.
    :return:
    """
    from choppy.check_utils import check_plugin
    from choppy.check_utils import check_customized_mkdocs

    if enable_media_extension:
        if not (check_plugin() and check_customized_mkdocs()):
            sys.exit(exit_code.INVALID_DEPS)

    # When all are False
    if not (app_name or templ_dir):
        raise Exception("Either app_name or templ_dir must exits.")

    report_dir = join_path(project_dir, 'report_markdown')
    if os.path.exists(report_dir) and not force:
        logger.info('Skip 1, 2, 3 generate context and render markdown.')
    else:
        # Force to clean
        logger.info('0. Force to clean all files in %s.' % report_dir)
        clean_files(report_dir)
        logger.success('Clean successfully.')

        # Context: generate context metadata.
        logger.info('\n1. Generate report context.')
        ctx_instance = Context(project_dir, server=server, editable=editable,
                               sample_id_pattern='', cached_metadata=cached_metadata,
                               by_workflow=by_workflow, enable_media_extension=enable_media_extension,
                               app_name=app_name, templ_dir=templ_dir)
        ctx_instance.set_extra_context(repo_url=repo_url, site_description=site_description,
                                       site_author=site_author, copyright=copyright, site_name=site_name,
                                       theme_name=theme_name)
        logger.info('Context: %s' % ctx_instance.context)
        logger.success('Context: generate report context successfully.')

        # Preprocessor: check app whether support report and cache files that be required by report rendering.
        if app_name:
            report_dir = join_path(c.app_dir, app_name, 'report')
        elif templ_dir:
            report_dir = templ_dir

        tmp_report_dir_uuid = str(uuid.uuid1())
        tmp_report_dir = join_path('/tmp', 'choppy', tmp_report_dir_uuid)
        check_dir(tmp_report_dir, skip=True, force=True)

        logger.debug('Temporary report directory: %s' % tmp_report_dir)
        logger.info('\n2. Try to preprocess an app report.')
        try:
            preprocessor = Preprocessor(report_dir, ctx_instance)
            preprocessor.process(tmp_report_dir)
            logger.success('Preprocess app report successfully.')
        except InValidReport as err:
            logger.warn(str(err))
            # TODO: How to deal with exit way when choppy run as web api mode.
            sys.exit(exit_code.INVALID_REPORT)

        # Renderer: render report markdown files.
        logger.info('\n3. Render report markdown files.')
        # Fix bug: Renderer need to get template file from temporary report directory.
        renderer = Renderer(tmp_report_dir, project_dir, context=ctx_instance, resource_dir=resource_dir)
        renderer.batch_render()
        renderer.copy_dependent_files()
        logger.success('Render report markdown files successfully.')

    # Report: build markdown files to html.
    from choppy.utils import ReportTheme
    if theme_name in ReportTheme.get_ppt_theme_lst():
        templ_type = 'ppt'
    elif theme_name in ReportTheme.get_html_theme_lst():
        templ_type = 'html'

    report = Report(project_dir)
    if mode == 'build':
        logger.info('\n4. Build %s by mkdocs' % report_dir)
        report.build(templ_type=templ_type)
        site_dir = join_path(project_dir, 'report_html')
        logger.success('Build markdown files successfully. '
                       '(Files in %s)' % site_dir)
    elif mode == 'livereload':
        logger.info('\n4. Serve %s in livereload mode by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='livereload',
                      templ_type=templ_type)
    elif mode == 'server':
        logger.info('\n4. Serve %s by mkdocs' % report_dir)
        report.server(dev_addr=dev_addr, livereload='no-livereload',
                      templ_type=templ_type)


def get_mode():
    return ['build', 'server', 'livereload']
