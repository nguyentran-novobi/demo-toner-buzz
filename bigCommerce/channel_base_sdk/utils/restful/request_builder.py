# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from typing import Type

from ..common import PropagatedParam
from ..common.resource import delegated
from ..common.connection import Request
from ..common.resource_formatter import DataTrans

from ..restful.connection import RestfulRequest, RestfulConnection, RestfulTransformerRequestWrapper
from ..restful.resource import RestfulResourceModel as RestfulResourceModelBase


class RequestBuilder:
    """
    Contain information needed to build a request
    """
    method: str
    url: str = None
    uri: str
    transform_in_data: DataTrans
    transform_out_data: DataTrans
    transform_error_message: DataTrans
    transform_request_param: DataTrans
    model_path: str
    model_postfix: str
    conn: RestfulConnection
    connection_prefix_url: str
    connection_headers: dict = None
    headers: dict = None
    options: dict = None
    params: dict = None
    _json: dict = None
    _data: object = None
    no_body: bool = False

    @property
    def model(self):
        return self.model_path, self.model_postfix

    @model.setter
    def model(self, value: Type[RestfulResourceModelBase]):
        self.model_path = f'{value.version}{value.prefix}{value.path}'
        self.model_postfix = value.postfix

    @property
    def connection(self):
        return self.conn

    @connection.setter
    def connection(self, value: RestfulConnection):
        self.conn = value
        self.connection_prefix_url = value.prefix_url
        self.connection_headers = value.headers

    @property
    def request(self):
        request = self.build_request()
        return self.build_request_wrapper(request)

    def build_request(self):
        wrapped_request = RestfulRequest(
            url=self.build_url(),
            headers=self.build_headers(),
            method=self.method,
            params=self.params,
            data=self.data,
            json=self.json,
        )
        try:
            wrapped_request.session = self.conn.session
        except AttributeError:
            pass
        return wrapped_request

    def build_url(self):
        if self.url:
            return self.url
        else:
            model_uri = self.build_uri()
            return f'{self.connection_prefix_url}{model_uri}'

    def build_uri(self):
        model_uri = f'{self.model_path}{self.uri}'
        model_uri = model_uri.format(**(self.options or {}))
        return f'{model_uri}{self.model_postfix}'

    def build_headers(self):
        headers = {
            **(self.connection_headers or {}),
            **(self.headers or {}),
        }
        return headers

    @property
    def json(self):
        return self._json

    @json.setter
    def json(self, value):
        if not self.no_body:
            self._json = value

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        if not self.no_body:
            self._data = value

    def build_request_wrapper(self, request):
        return RestfulTransformerRequestWrapper(
            request=request,
            transform_in_data=self.transform_in_data,
            transform_out_data=self.transform_out_data,
            transform_error_message=self.transform_error_message,
            transform_request_param=self.transform_request_param,
        )


class RequestPasser:
    """
    Make a decorator which pass a built request to the method
    """

    __slots__ = (
        '_func',
        '_request_builder',
        '_set_to',
        '_wrapper',
        '_owner',
        '_instance',
    )

    def __init__(self, func, request_builder, set_to):
        """
        Initiate passer
        """
        def wrapper(*args, **kwargs):
            """
            `wrapper` wraps `call`, `call` wraps func
            """
            return self(*args, **kwargs)

        self._func = func
        self._request_builder = request_builder
        self._set_to = set_to
        self._wrapper = wrapper

    def __call__(self, *args, **kwargs):
        if self.is_applicable(kwargs):
            return self.build_and_pass_request_builder(*args, **kwargs)
        return self.call_method(*args, **kwargs)

    def is_applicable(self, call_kwargs):
        return self._set_to not in call_kwargs

    def build_and_pass_request_builder(self, *args, **kwargs):
        request_builder = self.make_request_builder()
        return self.call_method(*args, **{self._set_to: request_builder}, **kwargs)

    def call_method(self, *args, **kwargs):
        return self._func(self._instance, *args, **kwargs)

    def make_request_builder(self):
        builder = self._request_builder
        model = self._owner
        builder.model = model
        builder.transform_in_data = getattr(model, 'transform_in_data')
        builder.transform_out_data = getattr(model, 'transform_out_data')
        builder.transform_error_message = getattr(model, 'transform_error_message')
        builder.transform_request_param = getattr(model, 'transform_request_param')
        return builder

    def __get__(self, instance, owner):
        self._owner = owner
        self._instance = instance
        return self._wrapper

    def __setattr__(self, key, value):
        """
        Set non-private attributes to the wrapped function and the internal wrapper
        """
        try:
            super().__setattr__(key, value)
        except AttributeError:
            setattr(self._func, key, value)
            setattr(self._wrapper, key, value)


def make_request_builder(set_to='request_builder', **kwargs):
    """
    Build a restful request from the signature of the method
    Keywords can be: method, uri, send_no_data
    """
    def wrapper(func):
        request_builder = RequestBuilder()
        request_builder.method = kwargs.get('method', 'GET')
        request_builder.uri = kwargs.get('uri', '')
        request_builder.no_body = kwargs.get('no_body', False)

        passer = RequestPasser(func, request_builder, set_to)

        return passer

    return wrapper


class RestfulResourceModel(RestfulResourceModelBase):

    @delegated
    def get_status_code(self, prop: PropagatedParam = None):
        """
        Get status code of the last response
        return None if there is no last response
        :param prop: The data propagated from the handler
        """
        last_response = prop['last_response']
        return last_response.status_code

    @delegated
    def get_error_message(self, prop: PropagatedParam = None):
        """
        Get error message of the last response
        If the last response is a success, None will be returned
        :param prop: The data propagated from the handler
        """
        last_response = prop['last_response']
        try:
            message = last_response.get_error()
        except ValueError:
            message = None
        return message


class RestfulRequestBuilder(RestfulResourceModel):
    """
    Mixin for building request from resource
    """

    @classmethod
    def build_json_send_handle_json(cls, builder, prop, **kwargs):
        response = cls.build_and_send_json_request_from(builder, prop, **kwargs)
        return cls.handle_json_response_data(response)

    @classmethod
    def build_data_send_handle_json(cls, builder, prop, **kwargs):
        response = cls.build_and_send_data_request_from(builder, prop, **kwargs)
        return cls.handle_json_response_data(response)

    @classmethod
    def build_and_send_json_request_from(cls, builder, prop, **kwargs):
        """
        Build a complete request from builder for json
        Send request to get response
        """
        request = cls.get_json_request_from_builder(builder, prop, **kwargs)
        response = request.send()
        return response

    @classmethod
    def build_and_send_data_request_from(cls, builder, prop, **kwargs):
        """
        Build a complete request from builder for data
        Send request to get response
        """
        request = cls.get_data_request_from_builder(builder, prop, **kwargs)
        response = request.send()
        return response

    @classmethod
    def get_data_request_from_builder(cls, builder, prop, **kwargs):
        propagated_mapping = [
            ('connection', 'connection'),
            ('options', 'options'),
            ('data', 'data'),
        ]
        return cls._get_request_from_builder(builder, prop, propagated_mapping, **kwargs)

    @classmethod
    def get_json_request_from_builder(cls, builder, prop, **kwargs):
        propagated_mapping = [
            ('connection', 'connection'),
            ('options', 'options'),
            ('data', 'json'),
        ]
        return cls._get_request_from_builder(builder, prop, propagated_mapping, **kwargs)

    @classmethod
    def _get_request_from_builder(cls, builder, prop, mapping, **kwargs):
        for kp, kb in mapping:
            if kp in prop:
                setattr(builder, kb, prop[kp])
        for k, v in kwargs.items():
            setattr(builder, k, v)
        return builder.request

    @classmethod
    def handle_json_response_data(cls, response, **kwargs):
        """
        Extract json data from response
        If the response is not OK, extract error instead
        """
        if response.ok():
            try:
                data = response.json()
            except ValueError:
                # Response is not in JSON format or other issues while parsing
                return cls.pass_result_to_handler(nil=True, response=response, **kwargs)
            return cls.pass_result_to_handler(data=data, response=response, **kwargs)
        return cls.pass_result_to_handler(error=True, response=response)


class RestfulRequestSingularBuilder(RestfulRequestBuilder):
    """
    Mixin for building request from singular resource
    """


class RestfulRequestBulkBuilder(RestfulRequestBuilder):
    """
    Mixin for building request for action with multiple resources
    """


class RestfulGet(RestfulRequestSingularBuilder):
    """
    Contains general get function for resource
    """

    def find(self) -> Request:
        """
        Build a request to get one single resource from channel
        """

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{id}',
        no_body=True,
    )
    def get_by_id(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get only one resource with the id from channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )


class RestfulPost(RestfulRequestSingularBuilder):
    """
    Contains general post function for resource
    """

    def post_one(self) -> Request:
        """
        Build a request to create one single resource on channel
        """

    @delegated
    @make_request_builder(
        method='POST',
        uri='',
    )
    def publish(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Post this resource to channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )


class RestfulPut(RestfulRequestSingularBuilder):
    """
    Contains general put function for resource
    """

    @delegated
    @make_request_builder(
        method='PUT',
        uri='/{id}',
    )
    def put_one(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Put this resource to channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='PUT',
        uri='',
    )
    def put_data(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Put this resource to channel without id
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )


class RestfulDelete(RestfulRequestSingularBuilder):
    """
    Contains general delete function for resource
    """

    @delegated
    @make_request_builder(
        method='DELETE',
        uri='/{id}',
        no_body=True,
    )
    def delete_one(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Delete permanently this resource on channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        response = self.build_and_send_json_request_from(
            request_builder,
            prop=prop,
            params=kwargs,
        )
        return self.pass_result_to_handler(nil=True, response=response)


class RestfulList(RestfulRequestBulkBuilder):
    """
    Contains general get many function for resource
    """

    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def all(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get only all resources match the searching criteria
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
