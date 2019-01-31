# coding: utf-8
from __future__ import unicode_literals

import os
import choppy.config as c
from jinja2 import Environment, FileSystemLoader


class BaseComponent:
    def __init__(self, component_name, component_dir=c.component_dir, template='main.html'):
        self.component_name = component_name
        self.component_dir = component_dir
        self.template = template

    def render(self, **kwargs):
        self._validate(**kwargs)
        component_dir = os.path.join(self.component_dir, self.component_name)
        env = Environment(loader=FileSystemLoader(component_dir))
        template = env.get_template(self.template)
        return template.render(**kwargs)

    def _validate(self, **kwargs):
        """
        Validate render data by json schema file.
        """
        pass
