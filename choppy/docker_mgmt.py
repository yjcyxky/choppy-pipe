# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import os
import uuid
import logging
import hashlib
import requests
import docker
import json
from choppy.app_utils import parse_json
from jinja2 import Environment, FileSystemLoader
import choppy.config as c
from choppy.bash_colors import BashColors
from choppy.check_utils import check_dir


def get_parser():
    return ('r', 'python', 'bash')


def overwrite_dockerfile(dockerfile):
    answer = ''
    while answer.upper() not in ("YES", "NO", "Y", "N"):
        try:
            answer = raw_input("Overwrite Dockerfile, Enter Yes/No: ")  # noqa: python2
        except Exception:
            answer = input("Overwrite Dockerfile, Enter Yes/No: ")  # noqa: python3

        answer = answer.upper()
        if answer == "YES" or answer == "Y":
            os.remove(dockerfile)
        elif answer == "NO" or answer == "N":
            raise Exception('Dockerfile Exists.')
        else:
            print("Please enter Yes/No.")


class Docker:
    """ Module to interact with Docker. Example usage:
        docker = Docker()
        docker.build()
        docker.login()
        docker.push()
    """

    def __init__(self, username=None, password=None, base_url='unix://var/run/docker.sock'):
        self.logger = logging.getLogger('choppy.docker_mgmt')
        self.username = username
        self.password = password
        self.base_url = base_url
        self.client = docker.DockerClient(base_url=base_url)

    def _exist_docker(self):
        """
        Test whether docker daemon is running.
        """
        try:
            self.client.ping()
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to the Docker daemon."
                            " Is the docker daemon running?")

    def _md5(self, string):
        """
        Generate md5 value for a string.
        """
        md5 = hashlib.md5()
        md5.update(string.encode(encoding='utf-8'))
        return md5.hexdigest()

    def _gen_dockerfile(self, software_name, software_version, summary='', home='',
                        software_doc='', tags='', output_file=None, **kwargs):
        """
        Generate dockerfile.
        """
        dockerfile_version = self._md5('%s-%s' % (software_name, software_version))
        env = Environment(loader=FileSystemLoader(c.resource_dir))
        template = env.get_template('dockerfile.template')
        rendered_tmpl = template.render(version=dockerfile_version, software_name=software_name,
                                        software_version=software_version, summary=summary,
                                        home=home, software_doc=software_doc, tags=tags,
                                        **kwargs)
        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def _gen_wrapper(self, main_program_list, parser='', output_file=None):
        env = Environment(loader=FileSystemLoader(c.resource_dir))
        if len(main_program_list) == 1:
            template = env.get_template('wrapper.template')
            rendered_tmpl = template.render(main_program=main_program_list[0], parser=parser)
        elif len(main_program_list) > 1:
            template = env.get_template('multi_wrapper.template')
            program_list = [program.split('.')[0] for program in main_program_list]
            program_list_str = ','.join(program_list)
            rendered_tmpl = template.render(program_list_str=program_list_str, parser=parser)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(rendered_tmpl)
                return output_file
        else:
            return rendered_tmpl

    def version(self):
        try:
            self._exist_docker()
            version_json = self.client.version()
            if version_json:
                print(json.dumps(parse_json(version_json), indent=2, sort_keys=True))
        except Exception as err:
            c.print_color(BashColors.FAIL, str(err))

    def clean_containers(self, filters):
        try:
            containers = self.client.containers.list(filters=filters)
            for container in containers:
                container.remove(force=True)
        except (docker.errors.APIError, Exception) as err:
            c.print_color(BashColors.FAIL, "Clean Containers: %s" % str(err))

    def clean_images(self, filters):
        try:
            images = self.client.images.list(filters=filters)
            for image in images:
                self.client.images.remove(image=image.id, force=True)
        except (docker.errors.APIError, Exception) as err:
            c.print_color(BashColors.FAIL, "Clean Images: %s" % str(err))

    def clean_all(self):
        container_filters = {
            'status': 'exited',
            'label': 'choppy_tag'
        }
        image_filters = {
            'label': 'choppy_tag'
        }
        self.clean_containers(container_filters)
        self.clean_images(image_filters)

    def build(self, software_name, software_version, tag_name, summary='',
              home='', software_doc='', tags='', channels=list(), base_image=None,
              parser='', main_program_lst=None, deps=None, dry_run=False, current_dir=True):
        """
        Build docker image.
        """
        try:
            current_dir = os.getcwd()
            if main_program_lst:
                wrapper_program = os.path.join(current_dir, software_name)
                self._gen_wrapper(main_program_lst, parser=parser, output_file=wrapper_program)

            self._exist_docker()
            if current_dir:
                tmp_dir = os.getcwd()
            else:
                tmp_dir = os.path.join('/tmp', 'choppy', str(uuid.uuid1()))
                check_dir(tmp_dir)

            tmp_dockerfile = os.path.join(tmp_dir, 'Dockerfile')

            if os.path.isfile(tmp_dockerfile):
                overwrite_dockerfile(tmp_dockerfile)

            choppy_tag = '%s-%s' % (software_name, software_version)

            self._gen_dockerfile(software_name, software_version, summary=summary, home=home,
                                 software_doc=software_doc, tags=tags, output_file=tmp_dockerfile,
                                 choppy_tag=choppy_tag, channels=channels, base_image=base_image,
                                 deps=deps, parser=parser)
            if not dry_run:
                cli = docker.APIClient(base_url=self.base_url)
                logs = cli.build(path=tmp_dir, tag=tag_name, decode=True,
                                 nocache=True, rm=True, pull=False)

                for line in logs:
                    streamline = line.get('stream')
                    if streamline:
                        print(streamline.strip())
            return tmp_dir
        except (docker.errors.APIError, Exception) as err:
            err_msg = "Build docker(%s-%s): %s" % (software_name, software_version, str(err))
            c.print_color(BashColors.FAIL, err_msg)
            return False


if __name__ == "__main__":
    software_name = 'cufflinks'
    software_version = '2.2.1'
    summary = 'Transcriptome assembly and differential expression analysis for RNA-Seq.'
    home = 'https://github.com/cole-trapnell-lab/cufflinks'
    software_doc = 'https://github.com/cole-trapnell-lab/cufflinks'
    tags = 'Genomics'
    docker_instance = Docker()
    print(docker_instance.version())
