# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import WooCommercePaginated
from ...restful.request_builder import make_request_builder
from ...common.resource import delegated
from ...common import PropagatedParam
from ...restful.request_builder import RequestBuilder
@register_model('variations')
class WooCommerceVariantModel(
    resource.WooCommerceResourceModel,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    WooCommercePaginated,
):
    """
    An interface of WooCommerce product variant
    """
    prefix = 'products/{product_id}/'
    path = 'variations'
    primary_key = 'id'
    secondary_keys = ('product_id',)


    @delegated
    @make_request_builder(
        method='POST',
        uri='/batch',
    )
    def post_batch(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Cancel order
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )