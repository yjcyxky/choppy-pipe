#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
"""
    choppy_api.api_server
    ~~~~~~~~~~~~~~~~~~~~~

    Launch a choppy api server for choppy.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

import os
import sys
import bjoern
import signal
import logging
import argparse
import verboselogs
import argcomplete
from gevent.pywsgi import WSGIServer
from choppy.utils import set_logger
from choppy.config import init_config, get_global_config

logging.setLoggerClass(verboselogs.VerboseLogger)
logger = logging.getLogger(__name__)

global_config = loglevel = None
# Regular argumnent parser configuration goes here
parser = argparse.ArgumentParser(
    description='Description: A tool for executing and monitoring WDLs to Cromwell instances.',
    usage='choppy <positional argument> [<args>]',
    formatter_class=argparse.RawDescriptionHelpFormatter)


def call_server(args):
    def get_default_server():
        server = global_config.get_section('server')
        host = server.host
        port = int(server.port)
        if host and port:
            return (host, port)
        elif host:
            return (host, 8000)
        elif port:
            return ('localhost', port)
        else:
            return ('0.0.0.0', 8000)

    from choppy_api import create_app
    from choppy_api.helper import register_helper
    flask_app = create_app(flask_config_name='production')
    register_helper(flask_app)

    global_config.cromwell_server = args.server
    framework = args.framework

    #
    # TODO: this starts the built-in server, which isn't the most
    # efficient.  We should use something better.
    #
    if framework == "gevent":
        logger.success("Starting gevent based server")
        logger.success('Running Server: %s:%s' % get_default_server())
        svc = WSGIServer(get_default_server(), flask_app)
        svc.serve_forever()
    elif framework == "bjoern":
        logger.success("Starting bjoern based server")
        host, port = get_default_server()
        logger.success('Running Server: %s:%s' % (host, port))
        bjoern.run(flask_app, host, port, reuse_port=True)
    else:
        flask_app.run(debug=True)


def parse_args():
    """parses and sets up the command line argument system above
    with config file parsing."""
    global parser, global_config, loglevel

    early_parser = argparse.ArgumentParser(description=__doc__,
                                           formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                           add_help=False)
    early_parser.add_argument('--config', '-c', type=os.path.exists, action='store',
                              help='change default configuration location')
    group = early_parser.add_mutually_exclusive_group()
    group.add_argument('--debug', action='store_true', default=False, help="Debug mode.")
    group.add_argument('-q', '--quite', action='store_true', default=False, help="Only display key message.")
    group.add_argument('-v', '--verbose', action='count', default=0, help='Increase output verbosity')

    args, remainder_argv = early_parser.parse_known_args()

    if args.debug:
        loglevel = logging.DEBUG
    elif args.verbose:
        verbose = args.verbose
        # Configure logger for requested verbosity.
        if verbose >= 3:
            loglevel = logging.SPAM
        elif verbose >= 2:
            loglevel = logging.DEBUG
        elif verbose >= 1:
            loglevel = logging.VERBOSE
    elif args.quite:
        loglevel = logging.ERROR

    set_logger('root', loglevel)

    # Override config file defaults if explicitly requested
    if args.config:
        init_config(config_file=args.config)
        global_config = get_global_config()
    else:
        init_config()
        global_config = get_global_config()

    if not (args.debug or args.verbose or args.quite):
        loglevel = global_config.get_loglevel('server', 'log_level')

    parser.add_argument('--handler', action='store', default='stream',
                        choices=('stream', 'file'), help="Log handler, stream or file?")
    server = parser.add_argument_group()
    server.add_argument('-S', '--server', action='store', default="localhost",
                        type=str, choices=global_config.servers,
                        help='Choose a cromwell server from {}'.format(global_config.servers))
    server.add_argument('-f', '--framework', action='store', default='flask',
                        choices=['bjoern', 'gevent', 'flask'], help='Run server with framework.')
    server.add_argument('-s', '--swagger', action='store_true', default=False,
                        help="Enable swagger documentation.")
    server.set_defaults(func=call_server)

    argcomplete.autocomplete(parser)
    args = parser.parse_args(remainder_argv)

    return args


def siginal_handler(signal_num, frame):
    if signal_num == signal.SIGINT:
        print('User Interrupted')
        sys.exit(0)


def main():
    # Setup Signal Handler
    signal.signal(signal.SIGINT, siginal_handler)

    args = parse_args()

    user = global_config.getuser()
    # Get user's username so we can tag workflows and logs for them.
    log_dir = global_config.get('server', 'log_dir')
    set_logger(user, loglevel=loglevel, handler=args.handler,
               subdir=None, log_dir=log_dir)

    try:
        args.func(args)
    except AttributeError as err:
        logger.debug(str(err))
        print("Wrong argument('%s --help' for help)" % sys.argv[0])


if __name__ == "__main__":
    sys.exit(main())
