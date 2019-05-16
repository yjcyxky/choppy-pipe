# -*- coding: utf-8 -*-
"""
    choppy.core.models
    ~~~~~~~~~~~~~~~~~~

    Module to define database modles for choppy.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import json
import logging
import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from choppy.config import get_global_config

logger = logging.getLogger(__name__)
global_config = get_global_config()
Base = declarative_base()


class Workflow(Base):
    __tablename__ = 'workflow'
    id = Column(String(60), primary_key=True)
    name = Column(String(250), nullable=True)
    status = Column(String(30), nullable=False)
    start = Column(DateTime(), nullable=True)
    end = Column(DateTime, nullable=True)
    person_id = Column(String(250), nullable=True)
    notified = Column(Boolean, nullable=False)

    @staticmethod
    def parse_time(dt_str):
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1]

        return datetime.datetime.strptime(dt_str.split(".")[0], "%Y-%m-%dT%H:%M:%S") if dt_str else None

    @staticmethod
    def get_or_none(field, dict):
        return dict[field] if field in dict else None

    @staticmethod
    def get_person_id(metadata):
        if 'labels' in metadata and 'username' in metadata['labels']:
            return metadata['labels']['username']
        else:
            if 'submittedFiles' in metadata and 'labels' in metadata['submittedFiles']:
                if 'username' in json.loads(metadata['submittedFiles']['labels']):
                    return json.loads(metadata['submittedFiles']['labels'])['username']

        return None

    def __init__(self, cromwell, w_id):
        metadata = cromwell.query_metadata(w_id)
        self.id = metadata["id"]
        self.name = self.get_or_none("workflowName", metadata)
        self.status = metadata["status"]
        self.start = self.parse_time(self.get_or_none("start", metadata))
        self.notified = False
        self.person_id = self.get_person_id(metadata)
        self.cached_metadata = metadata

        # super(Workflow, self).__init__(id=metadata["id"], name=self.get_or_none("workflowName", metadata), # noqa
        #                        status=metadata["status"], start=self.parse_time(self.get_or_none("start")), # noqa
        #                        notified=False, person_id=self.get_person_id(metadata)) # noqa

    def update_status(self, status):
        self.status = status
        self.notified = True


# Create an engine that stores data in the local directory's
# sqlalchemy_example.db file.
if global_config:
    engine = create_engine('sqlite:///' + global_config.get_path('general', 'workflow_db'))

    # Create all tables in the engine. This is equivalent to "Create Table"
    # statements in raw SQL.
    Base.metadata.create_all(engine)
else:
    logger.warning('To access `g.config`, '
                   'you need to call `get_global_config` firstly.')
