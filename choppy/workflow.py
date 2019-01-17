# -*- coding:utf-8 -*-
import csv
import os
import logging
from .check_utils import check_dir, is_valid_label
from .app_utils import (parse_samples, render_app, write, copy_and_overwrite,
                        generate_dependencies_zip, submit_workflow,)
from .json_checker import check_json

logger = logging.getLogger('choppy')


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
            # make project_name/sample_id directory
            sample_path = os.path.join(project_path, sample.get('sample_id'))
            check_dir(sample_path, skip=force)

            sample['project_name'] = project_name

            inputs = render_app(app_dir, 'inputs', sample)
            check_json(str=inputs)  # Json Syntax Checker
            write(sample_path, 'inputs', inputs)
            inputs_path = os.path.join(sample_path, 'inputs')

            wdl = render_app(app_dir, 'workflow.wdl', sample)
            write(sample_path, 'workflow.wdl', wdl)
            wdl_path = os.path.join(sample_path, 'workflow.wdl')

            src_dependencies = os.path.join(app_dir, 'tasks')
            dest_dependencies = os.path.join(sample_path, 'tasks')
            copy_and_overwrite(src_dependencies, dest_dependencies)

            if label is None:
                label = []

            is_valid_label(sample["sample_id"])
            label.append("sample-id:%s" % sample["sample_id"].lower())

            if not dry_run:
                try:
                    dependencies_path = os.path.join(app_dir, 'tasks')
                    dependencies_zip_file = generate_dependencies_zip(
                        dependencies_path)
                    result = submit_workflow(wdl_path, inputs_path, dependencies_zip_file, label,
                                             username=username, server=server)

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
        successed: successed_samples,
        failed: failed_samples
    }
