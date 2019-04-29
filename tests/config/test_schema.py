# -*- coding: utf-8 -*-
"""
    tests.config.test_schema
    ~~~~~~~~~

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""
import pytest


def test_is_port():
    from jsonschema.exceptions import ValidationError
    from choppy.config.schema import ChoppyValidator
    from jsonschema import validate
    schema = {
        'type': 'object',
        'properties': {
            'port': {
                'is_port': 'true'
            },
        }
    }

    instance = {
        'port': '8080'
    }

    with pytest.raises(ValidationError):
        validate(instance, schema, cls=ChoppyValidator)

    schema = {
        'type': 'object',
        'properties': {
            'port': {
                'is_port': True
            },
        }
    }

    instance = {
        'port': '8080'
    }
    assert validate(instance, schema, cls=ChoppyValidator) is None

    instance = {
        'port': 'test'
    }
    with pytest.raises(ValidationError):
        validate(instance, schema, cls=ChoppyValidator)

    instance = {
        'port': 8000
    }
    assert validate(instance, schema, cls=ChoppyValidator) is None

    # port > 65535 or port < 1
    instance = {
        'port': 100000
    }

    with pytest.raises(ValidationError):
        validate(instance, schema, cls=ChoppyValidator)
