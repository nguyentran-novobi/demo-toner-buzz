# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import PropagatedParam
from ...common.resource import delegated
from ...restful.request_builder import RequestBuilder, RestfulGet

from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonList, make_request_builder

@register_model('products')
class AmazonProductModel(
    AmazonResourceModel,
    RestfulGet,
    AmazonList,
):
    """
    An interface of Amazon Product
    """

    path = 'catalog/v0/items'
    primary_key = 'id'

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{asin}',
        no_body=True,
    )
    def get_by_asin(self, asin, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        prop.options = {**prop.options, **dict(asin=asin)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
