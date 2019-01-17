# -*- coding:utf-8 -*-
import logging
import json
import requests
import sys
from requests.utils import quote
from ratelimit import rate_limited
from requests.compat import urljoin
from . import config as c
from . import exit_code
from .exceptions import (UnauthorizedException, UnFoundException,
                         BadRequestException)

module_logger = logging.getLogger('choppy.choppy_store')
ONE_MINUTE = 60


class ChoppyStore:
    """ Module to interact with Choppy App Store. Example usage:
        choppy_store = ChoppyStore()
        choppy_store.listapps()
        choppy_store.query()

        Generated json payload:
        {
            "message": "Success",
            "data": []
        }
    """

    def __init__(self, choppy_web_api, username=None, password=None):
        self.choppy_web_api = choppy_web_api
        self.auth = (username, password) if username and password else None

        self.logger = logging.getLogger('choppy.choppy_store.ChoppyStore')
        self.logger.debug('URL:{}'.format(self.choppy_web_api))

        v_url = urljoin(self.choppy_web_api, "/api/v1/version")

        try:
            self.version = json\
                .loads(requests
                       .get(v_url, auth=self.auth)
                       .content)['version']
        except (requests.ConnectionError, ValueError) as e:
            msg = "Unable to connect to {}:\n{}".format(
                self.choppy_web_api, str(e))
            print_log_exit(msg, sys_exit=False)

    def get(self, endpoint, params=None, headers=None, v2=False):
        """
        A generic get request function.
        :param endpoint: choppy web api endpoint.
        :param headers: Optional headers for request.
        :return: json of request response
        """
        api_prefix = '/api/v1/' if not v2 else '/api/v2/'
        endpoint = endpoint.strip('/')
        api_url = urljoin(self.choppy_web_api, api_prefix)
        url = urljoin(api_url, endpoint)
        self.logger.debug("GET REQUEST:{}".format(url))
        if headers:
            r = requests.get(url, headers=headers, auth=self.auth)
        else:
            r = requests.get(url, auth=self.auth)

        # TODO: More Conditions
        if r.status_code == 200:
            return json.loads(r.content)
        elif r.status_code == 401:
            raise UnauthorizedException('Unauthorized for %s' % url)
        elif r.status_code == 400:
            raise BadRequestException('Bad request for %s: %s' % (url, params))
        elif r.status_code == 404:
            raise UnFoundException(
                'No such resource for %s: %s' % (url, params))
        else:
            r.raise_for_status()

    def post(self, endpoint, headers=None, v2=False):
        """
        A generic post request function.
        :param endpoint: choppy web api endpoint.
        :param headers: Optional headers for request.
        :return: json of request response
        """
        api_prefix = '/api/v1/' if not v2 else '/api/v2/'
        endpoint = endpoint.strip('/')
        api_url = urljoin(self.choppy_web_api, api_prefix)
        url = urljoin(api_url, endpoint)
        self.logger.debug("GET REQUEST:{}".format(url))
        if headers:
            r = requests.post(url, headers=headers, auth=self.auth)
        else:
            r = requests.post(url, auth=self.auth)

        # TODO: More Conditions
        if r.status_code == 201:
            return {"message": r.text}
        elif r.status_code == 401:
            raise UnauthorizedException('Unauthorized for %s' % url)
        elif r.status_code == 400:
            raise BadRequestException('Bad request for %s: %s' % (url, params))
        elif r.status_code == 404:
            raise UnFoundException(
                'No such resource for %s: %s' % (url, params))
        else:
            r.raise_for_status()

    def patch(self, endpoint, payload, headers, v2=False):
        """
        Make a patch request to the Cromwell server.
        :param endpoint: choppy web api endpoint.
        :param payload: the json data to patch.
        :param headers: payload headers.
        :return: request result
        """
        api_prefix = '/api/v1/' if not v2 else '/api/v2/'
        endpoint = endpoint.strip('/')
        api_url = urljoin(self.choppy_web_api, api_prefix)
        url = urljoin(api_url, endpoint)
        self.logger.debug("GET REQUEST:{}".format(url))
        tries = 4
        while tries != 0:
            r = requests.patch(url, data=payload,
                               headers=headers, auth=self.auth)
            if r.status_code == 200:
                logging.info('{} request succeeded.'.format(endpoint))
                tries = 0
            else:
                logging.warning("{} failed. Error {}: {}".format(
                    endpoint, r.status_code, json.loads(r.text)['message']))
                logging.info("Retrying...")
                tries -= tries
        # Should return none only if patch request fails.
        return r

    @rate_limited(300, ONE_MINUTE)
    def search(self, q_str, page=1, limit=10, mode='source', sort='created', order='asc'):
        """
        Search apps from choppy app store.
        :param q_str: query string.
        :param page: page number of results to return (1-based).
        :param limit: page size of results, maximum page size is 50.
        :param mode: type of repository to search for. Supported values are "fork", "source", "mirror" and "collaborative".
        :param sort: sort repos by attribute. Supported values are "alpha", "created", "updated", "size", and "id". Default is "alpha".
        :param order: sort order, either “asc” (ascending) or “desc” (descending). Default is "asc", ignored if “sort” is not specified.
        :return: request result
        """
        search_params = {
            "q": q_str,
            "page": page,
            "limit": limit,
            "mode": mode,
            "sort": sort,
            "order": order
        }
        try:
            results = self.get('/repos/search', params=search_params)
            results['message'] = 'Success'
            results.update(search_params)
            return results, 200
        except BadRequestException as err:
            results = {
                "message": str(err)
            }
            return results, 400
        except (UnauthorizedException, UnFoundException,
                requests.exceptions.HTTPError) as err:
            results = {
                "message": str(err)
            }
            return results, 500

    @rate_limited(300, ONE_MINUTE)
    def list_releases(self, owner, repo_name):
        """
        List a repo's releases.
        :param owner: owner of the repo.
        :param repo_name: name of the repo.
        :return: request result
        """
        endpoint = "/repos/%s/%s/releases" % (owner, repo_name)
        try:
            data = self.get(endpoint)
            results = {
                "data": data,
                "message": "Success"
            }
            return results, 200
        except BadRequestException as err:
            results = {
                "message": str(err)
            }
            return results, 400
        except (UnauthorizedException, UnFoundException,
                requests.exceptions.HTTPError) as err:
            results = {
                "message": str(err)
            }
            return results, 500


def print_log_exit(msg, sys_exit=True, ple_logger=module_logger):
    """
    Function for standard print/log/exit routine for fatal errors.
    :param msg: error message to print/log.
    :param sys_exit: Cause choppy to exit.
    :param ple_logger: Logger to use when logging message.
    :return:
    """
    ple_logger.critical(msg)
    if sys_exit:
        sys.exit(exit_code.GENERAL_ERROR)
