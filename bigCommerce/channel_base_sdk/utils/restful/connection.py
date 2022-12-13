# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import re
import requests
import logging
import contextlib
from requests_oauthlib import OAuth1

from typing import Any, Union
from dataclasses import dataclass

from ..common.connection import Connection, Request, Response
from ..common.resource_formatter import DataTrans
from ..common.exceptions import NotParseableException


_logger = logging.getLogger(__name__)


class LoggerWrapper:
    def __init__(self, request, logger_cls):
        self.request = request
        self.logger = logger_cls()

    @classmethod
    @contextlib.contextmanager
    def wrap(cls, request, logger_cls):
        logger = cls(request, logger_cls)
        try:
            yield logger
        except Exception as ex:
            logger.log_error(ex)
            raise

    def log_request(self, **options):
        self.logger.log_start(self.request, **options)

    def log_response(self, response):
        self.logger.log_end(self.request, response)

    def log_error(self, ex):
        self.logger.log_error(self.request, ex)


class RestfulRequestLogger:
    EMPTY = '<EMPTY>'

    logger = _logger

    def log_start(self, request: 'RestfulRequest', **kwargs):
        self.logger.info('Sending method %s to %s with %s', request.method, request.url, kwargs)

    def log_end(self, request: 'RestfulRequest', response):
        formatted = self.format_response(response)
        self.logger.info('Received from %s: %s', request.url, formatted)

    def log_error(self, request: 'RestfulRequest', ex):
        self.logger.error('Error while sending to %s: %s', request.url, str(ex))

    @classmethod
    def format_response(cls, response):
        code = cls.format_response_code(response)
        headers = cls.format_response_headers(response)
        body = cls.format_response_body(response)
        return str(dict(code=code, headers=headers, body=body))

    @classmethod
    def format_response_body(cls, response) -> str:
        try:
            return cls.format_response_json(response)
        except ValueError:
            return cls.format_response_content(response)

    @classmethod
    def format_response_content(cls, response) -> str:
        return response.content or cls.EMPTY

    @classmethod
    def format_response_json(cls, response) -> str:
        res_json = response.json()
        return json.dumps(res_json)

    @classmethod
    def format_response_headers(cls, response) -> str:
        return str(response.headers)

    @classmethod
    def format_response_code(cls, response) -> str:
        return str(response.status_code)


class RestfulRequestTrimmingLogger(RestfulRequestLogger):
    max_lines = 2**12
    max_line_length = 2**8
    max_json_unreadable_length = 2**7

    word_sep_pattern = r'[\s.,]'
    min_sep_density = 0.05

    @classmethod
    def format_response_json(cls, response) -> str:
        res_json = response.json()
        res_json = cls.trim_json(res_json)
        return json.dumps(res_json)

    @classmethod
    def trim_json(cls, data):
        if isinstance(data, dict):
            return cls.trim_json_dict(data)
        elif isinstance(data, list):
            return cls.trim_json_list(data)
        elif isinstance(data, str):
            return cls.trim_json_str(data)
        return data

    @classmethod
    def trim_json_dict(cls, dictionary):
        return {k: cls.trim_json(v) for k, v in dictionary.items()}

    @classmethod
    def trim_json_list(cls, array):
        return [cls.trim_json(v) for v in array]

    @classmethod
    def trim_json_str(cls, text):
        if len(text) > cls.max_json_unreadable_length and cls._is_human_readable(text):
            return text[:cls.max_json_unreadable_length - 3] + '...'
        elif len(text) > cls.max_line_length:
            return text[:cls.max_line_length - 3] + '...'
        return text

    @classmethod
    def _is_human_readable(cls, text):
        return (len(re.findall(cls.word_sep_pattern, text)) / len(text)) >= cls.min_sep_density

    @classmethod
    def format_response_content(cls, response) -> str:
        return ''.join(map(cls.trim_content_str, (line.decode() for line in response.iter_lines()))) or cls.EMPTY

    @classmethod
    def trim_content_str(cls, text):
        if len(text) > cls.max_line_length - 1:
            return text[:cls.max_line_length - 4] + '...\n'
        return text + '\n'


@dataclass
class RestfulRequest(Request):
    """
    This contains information for sending a single restful request to channel
    """
    logger = RestfulRequestTrimmingLogger
    logger_wrapper = LoggerWrapper
    engine = requests
    engine_request_error = requests.exceptions.RequestException
    engine_response_error = requests.HTTPError
    session = None

    url: str
    headers: dict
    method: str
    params: dict
    data: Any
    json: dict

    def send(self) -> 'RestfulResponse':
        """
        Send the request and receive the restful response
        """
        options = self.prepare_sending_options()
        result = self._send(**options)
        return result

    def prepare_sending_options(self):
        def update_kw_if_not_empty(key, value):
            if value:
                options[key] = value

        options = dict(timeout=(30, 60))
        for option_key in ('headers', 'params', 'data', 'json'):
            if hasattr(self, option_key):
                update_kw_if_not_empty(option_key, getattr(self, option_key))
        if 'OAuth' in options['headers'] and options['headers']['OAuth'] == '1.0':
            oauth = OAuth1(options['headers']['Authorization']['consumer_key'], client_secret=options['headers']['Authorization']['consumer_secret'])
            options['auth'] = oauth
        return options

    def _send(self, **kwargs):
        try:
            response = self._send_request_with_logging(**kwargs)
            res = self._prepare_response(response)
        except self.engine_request_error as ex:
            res = self._prepare_unsuccessful_response(ex)
        return res

    def _send_request_with_logging(self, **kwargs):
        with self.logger_wrapper.wrap(self, self.logger) as logger:
            logger.log_request(**kwargs)
            response = self._send_request(self.method, self.url, **kwargs)
            logger.log_response(response)
        return response

    def _send_request(self, method, url, **kwargs):
        return self.carrier.request(method, url, **kwargs)

    def _prepare_response(self, response):
        res = RestfulResponse()
        res.response = response
        res.request = self
        return res

    def _prepare_unsuccessful_response(self, ex):
        res = RestfulUnsuccessfulRequest()
        res.response = None
        res.reason = str(ex)
        res.request = self
        return res

    @property
    def carrier(self):
        return self.session or self.engine

    @classmethod
    def get_new_engine_session(cls):
        return cls.engine.Session()


class RestfulResponse(Response):
    """
    This contains information related to the response received from the restful request
    """
    response: requests.Response
    request: RestfulRequest

    def __getattr__(self, name):
        """
        Pass all other functions to the real response
        """
        return getattr(self.response, name)

    @property
    def headers(self):
        """
        Fetch headers from response
        """
        return self.response.headers

    def ok(self) -> bool:
        """
        Whether the request is sent successfully and the response is received with green status
        """
        try:
            self.raise_for_status()
        except RestfulRequest.engine_response_error:
            return False
        return True

    def raise_for_status(self):
        """
        Raise error if the request is not successful
        """
        self.response.raise_for_status()

    def json(self, **kwargs) -> Union[list, dict]:
        """
        Extract data from response and parse it to the JSON-like format
        This may raise Exception if the response is not in expected format
        """
        return self.response.json(**kwargs)

    @property
    def error_message(self):
        """
        Extract error message from json
        """
        if not self.ok():
            return self.json()
        raise ValueError('No error')


class RestfulResponseRetryLater(RestfulResponse):
    """
    This response allows resubmit request to channel
    """

    def ok(self) -> bool:
        """
        Whether the request is sent successfully and the response is received with green status
        Always False since the request is not successful.
        """
        return False


class RestfulUnsuccessfulRequest(RestfulResponseRetryLater):
    """
    This is the result of the request that is not able to make it to the channel
    """
    reason: str

    @property
    def error_message(self):
        """
        The reason is the error message
        """
        return self.reason

    @property
    def status_code(self):
        """
        There is no response, so there is no status code
        """
        return None

    def raise_for_status(self):
        """
        Raise error if the request is not successful
        """
        raise IOError(self.reason)


class RestfulTransformerWrapper:
    _wrap_name: str

    def __getattr__(self, name):
        """
        Propagate method call to specific attribute
        """
        return getattr(self.__dict__[self._wrap_name], name)


@dataclass
class RestfulTransformerResponseWrapper(RestfulTransformerWrapper):
    _wrap_name = 'response'

    response: RestfulResponse
    transform_in_data: DataTrans
    transform_error_message: DataTrans

    def __getattr__(self, name):
        """
        Pass all other functions to the real response
        """
        return getattr(self.response, name)

    @property
    def headers(self):
        """
        Fetch headers from response
        """
        return self.response.headers

    def json(self):
        result = self.response.json()
        transformed = self.transform_in_data(result)
        return transformed

    def iter(self):
        yield from map(self.transform_in_data, self.response.iter())

    def get_error(self):
        error_message = self.response.error_message
        try:
            transformed = self.transform_error_message(error_message)
            return transformed
        except NotParseableException:
            return error_message


@dataclass
class RestfulTransformerRequestWrapper(RestfulTransformerWrapper):
    _wrap_name = 'request'

    request: RestfulRequest
    transform_in_data: DataTrans
    transform_out_data: DataTrans
    transform_error_message: DataTrans
    transform_request_param: DataTrans

    def send(self) -> RestfulTransformerResponseWrapper:
        self.format_sending_params()
        self.format_sending_data()

        response = self.request.send()
        return self.handle_response(response)

    def format_sending_params(self):
        if self.request.params is not None:
            self.request.params = self.transform_request_param(self.request.params)

    def format_sending_data(self):
        if self.request.json:
            try:
                self.request.json = self.transform_out_data(self.request.json)
            except AttributeError:
                pass

    def handle_response(self, response):
        wrapper = RestfulTransformerResponseWrapper(
            response=response,
            transform_in_data=self.transform_in_data,
            transform_error_message=self.transform_error_message,
        )
        return wrapper


@dataclass
class RestfulConnection(Connection):
    """
    Contain information needed to establish an connection to channel with restful methods
    """
    _request_cls = RestfulRequest
    session = None

    scheme: str
    hostname: str
    uri: str
    headers: dict

    def __post_init__(self):
        self.session = self.get_new_engine_session()

    @property
    def prefix_url(self) -> str:
        """
        Generate the first part of the request URL
        """
        return f'{self.scheme}{self.hostname}{self.uri}'

    @classmethod
    def get_new_engine_session(cls):
        return cls._request_cls.get_new_engine_session()


@dataclass
class RestfulConnectionLazyHeaders(RestfulConnection):
    def __init__(self, *args, **kwargs):
        def get_empty_dict():
            return {}

        super().__init__(*args, **kwargs)
        self._get_headers = kwargs.get('headers', get_empty_dict)

    @property
    def headers(self):
        return self._get_headers()

    @headers.setter
    def headers(self, value):
        self._get_headers = value
