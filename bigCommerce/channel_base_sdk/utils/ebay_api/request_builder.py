# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import urllib.parse

from ..common import PropagatedParam
from ..common.resource import delegated

from ..restful.request_builder import make_request_builder, RequestBuilder,\
    RestfulRequestBulkBuilder


class eBayPaginated(RestfulRequestBulkBuilder):
    """
    Manages operations that fetch resources from a list of many pages
    """
    
    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def get_next_page(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get remaining resource from the next link
        """
        next_link = self._get_next_link(prop.last_response)
        if next_link:
            return self.build_json_send_handle_json(
                request_builder,
                prop=prop,
                url=next_link,
                params={**kwargs},
            )
        return self.pass_result_to_handler(nil=True)
    
    def _get_next_link(self, last_response):
        last_request = last_response.request if last_response else None
        if last_request:
            res_json = last_response.response.json()
            try:
                link = res_json['next']
            except KeyError:
                pass
            else:
                return link
        return None