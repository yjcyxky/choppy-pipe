#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
"""
Choppy is a tool for submitting workflows via command-line to the cromwell execution engine servers.
"""
import os
import sys

sys.path.append(os.path.dirname(__file__))

from choppy.__main__ import main # noqa

if __name__ == "__main__":
    sys.exit(main())
