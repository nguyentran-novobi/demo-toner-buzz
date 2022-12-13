# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import urllib.parse

from ..common import PropagatedParam
from ..common.resource import delegated

from ..restful.request_builder import make_request_builder, RequestBuilder,\
    RestfulRequestBulkBuilder


class WooCommercePaginated(RestfulRequestBulkBuilder):
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