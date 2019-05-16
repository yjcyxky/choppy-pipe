# -*- coding: utf-8 -*-
"""
    choppy.core.scaffold
    ~~~~~~~~~~~~~~~~~~~~

    Module to generate a scaffold for choppy app.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import os
import logging
import verboselogs
from jinja2 import Environment, FileSystemLoader
from choppy.config import get_global_config
from choppy.utils import copy_and_overwrite
from choppy.exceptions import NoSuchDirectory, NoSuchFile

global_config = get_global_config()
logging.setLoggerClass(verboselogs.VerboseLogger)


class Scaffold:
    def __init__(self, output_dir='.'):
        self.logger = logging.getLogger('choppy.scaffold.Scaffold')
        file_list = ['README.md', 'workflow.wdl', 'inputs', 'defaults']
        dir_list = ['tasks', 'test', 'docker', 'report']
        self.scaffold_dir = os.path.join(global_config.resource_dir, 'scaffold_template')
        self.file_list = [os.path.join(self.scaffold_dir, file) for file in file_list]
        self.dir_list = [os.path.join(self.scaffold_dir, dir) for dir in dir_list]

        # scaffold_template directory must have these files and dirs.
        self._check_file(self.file_list)
        self._check_dir(self.dir_list)

        # Template Env
        self.env = Environment(loader=FileSystemLoader(self.scaffold_dir))
        self.output_dir = output_dir

    def _check_file(self, file_list):
        for file in file_list:
            if not os.path.isfile(file):
                raise NoSuchFile('No such file(%s) in scaffold.' % file)
            else:
                continue

    def _check_dir(self, dir_list):
        for dir in dir_list:
            if not os.path.isdir(dir):
                raise NoSuchDirectory('No such directory(%s) in scaffold.' % dir)
            else:
                continue

    def _gen_readme(self, output_file='README.md', **kwargs):
        """Generate README.md from README.md template.
        """
        template = self.env.get_template('README.md')
        rendered_tmpl = template.render(**kwargs)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def _gen_defaults(self, output_file='defaults', **kwargs):
        """Generate defaults from defaults template.
        """
        template = self.env.get_template('defaults')
        rendered_tmpl = template.render(**kwargs)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def _gen_inputs(self, output_file='inputs', **kwargs):
        """Generate inputs from inputs template.
        """
        template = self.env.get_template('inputs')
        rendered_tmpl = template.render(**kwargs)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def _gen_workflow(self, output_file='workflow.wdl', **kwargs):
        """Generate workflow.wdl from workflow.wdl template.
        """
        template = self.env.get_template('workflow.wdl')
        rendered_tmpl = template.render(**kwargs)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def _copy_tasks(self):
        """Generate tasks directory from scaffold template.
        """
        tasks_dir = os.path.join(self.scaffold_dir, 'tasks')
        dest_dir = os.path.join(self.output_dir, 'tasks')
        copy_and_overwrite(tasks_dir, dest_dir)

    def _copy_docker(self):
        """Generate docker directory from scaffold template.
        """
        docker_dir = os.path.join(self.scaffold_dir, 'docker')
        dest_dir = os.path.join(self.output_dir, 'docker')
        copy_and_overwrite(docker_dir, dest_dir)

    def _copy_test(self):
        """Generate test directory from scaffold template.
        """
        test_dir = os.path.join(self.scaffold_dir, 'test')
        dest_dir = os.path.join(self.output_dir, 'test')
        copy_and_overwrite(test_dir, dest_dir)

    def _copy_report(self):
        """Generate report directory from scaffold template.
        """
        report_dir = os.path.join(self.scaffold_dir, 'report')
        dest_dir = os.path.join(self.output_dir, 'report')
        copy_and_overwrite(report_dir, dest_dir)

    def generate(self, template):
        if template != 'report':
            self._copy_docker()
            self._copy_tasks()
            self._copy_test()
            self._copy_report()

            readme = os.path.join(self.output_dir, 'README.md')
            self._gen_readme(output_file=readme)

            defaults = os.path.join(self.output_dir, 'defaults')
            self._gen_defaults(output_file=defaults)

            inputs = os.path.join(self.output_dir, 'inputs')
            self._gen_inputs(output_file=inputs)

            workflow = os.path.join(self.output_dir, 'workflow.wdl')
            self._gen_workflow(workflow)
        else:
            self._copy_report()
            self.output_dir = os.path.join(self.output_dir, 'report')

        self.logger.success('Generate scaffold directory successfully. '
                            '(All files in %s)' % self.output_dir)
