# -*- coding:utf-8 -*-
import os
import uuid
import logging
import hashlib
import requests
import docker
import json
from .app_utils import parse_json
from jinja2 import Environment, FileSystemLoader
from . import config as c
from .bash_colors import BashColors
from .check_utils import check_dir


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

    def version(self):
        try:
            self._exist_docker()
            version_json = self.client.version()
            if version_json:
                print(json.dumps(parse_json(version_json), indent=2, sort_keys=True))
        except Exception as err:
            self.logger.error(str(err))
            c.print_color(BashColors.FAIL, str(err))

    def clean_containers(self, filters):
        try:
            containers = self.client.containers.list(filters=filters)
            for container in containers:
                container.remove(force=True)
        except docker.errors.APIError as err:
            self.logger.error("Clean Containers: %s" % str(err))

    def clean_images(self, filters):
        try:
            images = self.client.images.list(filters=filters)
            for image in images:
                self.client.images.remove(image=image.id, force=True)
        except docker.errors.APIError as err:
            self.logger.error("Clean Images: %s" % str(err))

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
              home='', software_doc='', tags='', channels=list(), base_image=None):
        """
        Build docker image.
        """
        try:
            self._exist_docker()
            tmp_dir = os.path.join('/tmp', 'choppy', str(uuid.uuid1()))
            check_dir(tmp_dir)
            tmp_dockerfile = os.path.join(tmp_dir, 'Dockerfile')
            choppy_tag = '%s-%s' % (software_name, software_version)
            self._gen_dockerfile(software_name, software_version, summary=summary, home=home,
                                 software_doc=software_doc, tags=tags, output_file=tmp_dockerfile,
                                 choppy_tag=choppy_tag, channels=channels, base_image=base_image)
            cli = docker.APIClient(base_url=self.base_url)
            logs = cli.build(path=tmp_dir, tag=tag_name, decode=True,
                             nocache=True, rm=True, pull=False)

            for line in logs:
                streamline = line.get('stream')
                if streamline:
                    print(streamline.strip())
        except (docker.errors.APIError, Exception) as err:
            err_msg = "Build docker(%s-%s): %s" % (software_name, software_version, str(err))
            self.logger.error(err_msg)
            c.print_color(BashColors.FAIL, err_msg)


if __name__ == "__main__":
    software_name = 'cufflinks'
    software_version = '2.2.1'
    summary = 'Transcriptome assembly and differential expression analysis for RNA-Seq.'
    home = 'https://github.com/cole-trapnell-lab/cufflinks'
    software_doc = 'https://github.com/cole-trapnell-lab/cufflinks'
    tags = 'Genomics'
    docker_instance = Docker()
    print(docker_instance.version())
