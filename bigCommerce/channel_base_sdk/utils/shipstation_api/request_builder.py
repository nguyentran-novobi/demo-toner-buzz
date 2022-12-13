# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.resource import delegated

from ..restful import request_builder as restful_builder
from ..restful.request_builder import make_request_builder


class ShipStationPaginated(restful_builder.RestfulRequestBulkBuilder):
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
        next_page = self._get_next_page(prop.last_response)
        if next_page:
            last_request = prop.last_response.request
            last_params = last_request.params
            params = dict(page=next_page)
            return self.build_json_send_handle_json(
                request_builder,
                prop=prop,
                url=last_request.url,
                params={**last_params, **params, **kwargs}
            )
        return self.pass_result_to_handler(nil=True)

    def _get_next_page(self, last_response):
        last_request = last_response.request if last_response else None
        if last_request:
            res_json = last_response.response.json()
            try:
                next_page = int(res_json['page']) + 1
                if int(next_page) > int(res_json['pages']):
                    return None
            except KeyError:
                pass
            else:
                return next_page
        return None
