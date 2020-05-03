# -*- coding: utf-8 -*-
"""
    choppy.core.workflow
    ~~~~~~~~~~~~~~~~~~~~

    Module to submit batch tasks.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import csv
import os
import json
import logging
from choppy.check_utils import check_dir, is_valid_label
from choppy.core.app_utils import (parse_samples, render_app, write,
                                   generate_dependencies_zip, submit_workflow,
                                   AppDefaultVar, is_valid_app, get_version)
from choppy.core.json_checker import check_json
from choppy.utils import copy_and_overwrite

logger = logging.getLogger(__name__)


def run_batch(project_name, app_dir, samples, label, server='localhost',
              username=None, dry_run=False, force=False):
    is_valid_app(app_dir)
    working_dir = os.getcwd()
    project_path = os.path.join(working_dir, project_name)
    check_dir(project_path, skip=force)

    samples_data = parse_samples(samples)
    successed_samples = []
    failed_samples = []

    for sample in samples_data:
        if 'sample_id' not in sample.keys():
            raise Exception("Your samples file must contain sample_id column.")
        else:
            # 用户可通过samples文件覆写default文件中已定义的变量
            # 只有samples文件中缺少的变量才从default文件中取值
            app_default_var = AppDefaultVar(app_dir)
            all_default_value = app_default_var.show_default_value()

            for key in all_default_value.keys():
                if key not in sample.keys():
                    sample[key] = all_default_value.get(key)

            # make project_name/sample_id directory
            sample_path = os.path.join(project_path, sample.get('sample_id'))
            check_dir(sample_path, skip=force)

            sample['project_name'] = project_name

            # inputs
            inputs = render_app(app_dir, 'inputs', sample)
            check_json(string=inputs)  # Json Syntax Checker
            write(sample_path, 'inputs', inputs)
            inputs_path = os.path.join(sample_path, 'inputs')

            # workflow.wdl
            wdl = render_app(app_dir, 'workflow.wdl', sample)
            write(sample_path, 'workflow.wdl', wdl)
            wdl_path = os.path.join(sample_path, 'workflow.wdl')

            # defaults
            src_defaults_file = os.path.join(app_dir, 'defaults')
            dest_defaults_file = os.path.join(sample_path, 'defaults')
            copy_and_overwrite(src_defaults_file, dest_defaults_file, is_file=True)

            src_dependencies = os.path.join(app_dir, 'tasks')
            dest_dependencies = os.path.join(sample_path, 'tasks')
            copy_and_overwrite(src_dependencies, dest_dependencies)

            if label is None:
                label = []

            is_valid_label(sample["sample_id"])
            label.append("sample-id:%s" % sample["sample_id"].lower())

            if not dry_run:
                try:
                    dep_path = os.path.join(app_dir, 'tasks')
                    dep_zip_file = generate_dependencies_zip(dep_path)
                    result = submit_workflow(wdl_path, inputs_path,
                                             dep_zip_file,
                                             label, username=username,
                                             server=server)

                    sample['workflow_id'] = result['id']
                    logger.info("Sample ID: %s, Workflow ID: %s" %
                                (sample.get('sample_id'), result['id']))
                except Exception as e:
                    logger.error("Sample ID: %s, %s" %
                                 (sample.get('sample_id'), str(e)))
                    failed_samples.append(sample)
                    continue

            successed_samples.append(sample)

    submitted_file_path = os.path.join(project_path, 'submitted.csv')
    failed_file_path = os.path.join(project_path, 'failed.csv')
    version_path = os.path.join(project_path, 'version')
    version_dict = get_version(app_dir)

    with open(version_path, 'wt') as fversion:
        json.dump(version_dict, fversion)

    if len(successed_samples) > 0:
        keys = successed_samples[0].keys()
        with open(submitted_file_path, 'wt') as fsuccess:
            dict_writer = csv.DictWriter(fsuccess, keys)
            dict_writer.writeheader()
            dict_writer.writerows(successed_samples)

    if len(failed_samples) > 0:
        keys = failed_samples[0].keys()
        with open(failed_file_path, 'wt') as ffail:
            dict_writer = csv.DictWriter(ffail, keys)
            dict_writer.writeheader()
            dict_writer.writerows(failed_samples)

    if len(successed_samples) > 0:
        if len(failed_samples) == 0:
            logger.info("Successed: %s, %s" %
                        (len(successed_samples), submitted_file_path))
        else:
            logger.info("Successed: %s, %s" %
                        (len(successed_samples), submitted_file_path))
            logger.error("Failed: %s, %s" %
                         (len(failed_samples), failed_file_path))
    else:
        logger.error("Failed: %s, %s" %
                     (len(failed_samples), failed_file_path))

    return {
        "successed": successed_samples,
        "failed": failed_samples
    }
