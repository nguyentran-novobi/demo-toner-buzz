# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import urllib.parse

from ..common import PropagatedParam
from ..common.resource import delegated

from ..restful.request_builder import make_request_builder, RequestBuilder,\
    RestfulRequestBulkBuilder


class BigCommercePaginated(RestfulRequestBulkBuilder):
    """
    Manages operations that fetch resources from a list of many pages
    """

    @delegated
    def get_next_page(self, prop: PropagatedParam = None, **kwargs):
        if 'v2' in self.version:
            return prop.self.get_next_page_v2(**kwargs)
        return prop.self.get_next_page_v3(**kwargs)

    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def get_next_page_v2(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get remaining resource in the next page
        """
        last_request = prop.last_response.request if prop.last_response else None
        if last_request:
            last_params = last_request.params
            params = dict(page=last_params.get('page', 1) + 1)
            return self.build_json_send_handle_json(
                request_builder,
                prop=prop,
                url=last_request.url,
                params={**last_params, **params, **kwargs},
            )
        return self.pass_result_to_handler(nil=True)

    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def get_next_page_v3(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get remaining resource from the next link
        """
        next_params = self._get_next_page_params(prop.last_response)
        if next_params:
            last_request = prop.last_response.request
            return self.build_json_send_handle_json(
                request_builder,
                prop=prop,
                url=last_request.url,
                params={**next_params, **kwargs},
            )
        return self.pass_result_to_handler(nil=True)

    def _get_next_page_params(self, last_response):
        last_request = last_response.request if last_response else None
        if last_request:
            try:
                return self._try_get_next_page_params(last_response)
            except KeyError:
                pass
        return None

    @classmethod
    def _try_get_next_page_params(cls, last_response):
        last_request = last_response.request
        res_json = last_response.response.response.json()
        pagination = res_json['meta']['pagination']
        if cls.has_next_page_v3(pagination):
            try:
                return cls.extract_params(pagination['links']['next'])
            except KeyError:
                return cls.build_next_page_params(last_request, pagination)
        return None

    @classmethod
    def has_next_page_v3(cls, pagination):
        return pagination['current_page'] < pagination['total_pages']

    @classmethod
    def extract_params(cls, query):
        parsed = urllib.parse.urlparse(query)
        params = urllib.parse.parse_qs(parsed.query)
        params = dict(
            (k, v[0]) if len(v) == 1 else (f'{k}[]', v)
            for k, v in params.items()
        )
        return params

    @classmethod
    def build_next_page_params(cls, last_request, pagination):
        args = last_request.params.copy()
        args['page'] = pagination['current_page'] + 1
        return args
