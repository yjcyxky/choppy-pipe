# -*- coding: utf-8 -*-
"""
    choppy.config.schema
    ~~~~~~~~~~~~~~~~~~~~

    Custom schema validator for choppy config.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from jsonschema.exceptions import ValidationError
from jsonschema import validators, Draft7Validator


def is_port(validator, value, instance, schema):
    if not isinstance(value, bool):
        yield ValidationError("%s is not a boolean" % value)

    try:
        port = int(instance)
        if port < 1 or port > 65535:
            yield ValidationError("%r is not a valid port" % (instance,))
    except Exception:
        yield ValidationError("%r is not a number" % instance)


all_validators = dict(Draft7Validator.VALIDATORS)
all_validators['is_port'] = is_port

ChoppyValidator = validators.create(
    meta_schema=Draft7Validator.META_SCHEMA, validators=all_validators
)
