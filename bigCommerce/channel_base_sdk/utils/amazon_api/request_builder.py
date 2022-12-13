# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json

from datetime import datetime

from ..common.resource import delegated

from ..restful import request_builder as restful_builder

from . import signature_v4
from .connection import AmazonConnection
from .const import BASIC_ISO_DATE_STAMP_FORMAT
    
class AmazonCompleteRequestBuilder(restful_builder.RequestBuilder):
    BASIC_ISO_DATE_FORMAT = BASIC_ISO_DATE_STAMP_FORMAT

    now: datetime = None
    amz_now: str = None

    def build_headers(self):
        assert isinstance(self.conn, AmazonConnection)
        self.assign_current_time()
        data = self.data or (self.json and json.dumps(self.json)) or None
        headers = self.build_headers_without_signature()
        authorization_headers = signature_v4.get_authorization_headers(
            uri=self.build_uri(),
            headers=headers,
            params=self.params,
            data=data,
            method=self.method,
            access_key=self.conn.access_key,
            secret_access_key=self.conn.secret_access_key,
            request_time=self.now,
            region=self.conn.region,
            service=self.conn.service,
        )
        headers.update(authorization_headers)
        return headers

    def build_headers_without_signature(self):
        return {
            'x-amz-date': self.amz_now,
            **(self.connection_headers or {}),
            **(self.headers or {}),
        }

    def assign_current_time(self):
        self.now, self.amz_now = self.get_current_time_tuple()

    def get_current_time_tuple(self):
        now = datetime.utcnow()
        amz_now = now.strftime(self.BASIC_ISO_DATE_FORMAT)
        return now, amz_now


def make_request_builder(set_to='request_builder', **kwargs):
    """
    Build a restful request from the signature of the method
    Keywords can be: method, uri
    """
    def wrapper(func):
        request_builder = AmazonCompleteRequestBuilder()
        request_builder.method = kwargs.get('method', 'GET')
        request_builder.uri = kwargs.get('uri', '')

        passer = restful_builder.RequestPasser(func, request_builder, set_to)

        return passer

    return wrapper


class AmazonList(restful_builder.RestfulList):
    """
    Contains general get many function for resource
    """

    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def all(self, prop=None, request_builder=None, **kwargs):
        """
        Get only all resources match the searching criteria from Amazon
        """
        return super().all(prop=prop, request_builder=request_builder, **kwargs)
    
class AmazonGet(restful_builder.RestfulGet):
    
    @delegated
    @make_request_builder(
        method='GET',
        uri='/{id}',
        no_body=True,
    )
    def get_by_id(self, prop= None, request_builder= None, **kwargs):
        """
        Get only one resource with the id from channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        return super().get_by_id(prop=prop, request_builder=request_builder, **kwargs)
    
class AmazonPost(restful_builder.RestfulPost):
    
    @delegated
    @make_request_builder(
        method='POST',
        uri='',
    )
    def publish(self, prop=None, request_builder=None, **kwargs):
        """
        Post this resource to channel
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return super().publish(prop=prop, request_builder=request_builder, **kwargs)
    
    
class AmazonPaginated(restful_builder.RestfulRequestBulkBuilder):
    """
    Manages operations that fetch resources from a list of many pages
    """
    
    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def get_next_page(self, prop=None, request_builder=None, **kwargs):
        """
        Get remaining resource from the next link
        """
        next_token = self._get_next_token(prop.last_response)
        if next_token:
            last_request = prop.last_response.request
            return self.build_json_send_handle_json(
                request_builder,
                prop=prop,
                url=last_request.url,
                params={**{'NextToken': next_token}, **kwargs},
            )
        return self.pass_result_to_handler(nil=True)
    
    def _get_next_token(self, last_response):
        last_request = last_response.request if last_response else None
        if last_request:
            res_json = last_response.response.json()
            try:
                next_token = res_json['payload']['NextToken']
            except KeyError:
                pass
            else:
                return next_token
        return None