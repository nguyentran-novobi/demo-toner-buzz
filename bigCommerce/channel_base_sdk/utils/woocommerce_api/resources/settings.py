# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ...restful.request_builder import make_request_builder
from ...common.resource import delegated
from ...common import PropagatedParam
from ...restful.request_builder import RequestBuilder

@register_model('settings')
class WooCommerceSettingsModels(
    resource.WooCommerceResourceModel,
    request_builder.RestfulGet,
    request_builder.RestfulList,
):
    """
    An interface of WooCommerce settings
    """
    path = 'settings'
    
    @delegated
    @make_request_builder(
        method='GET',
        uri='/products',
    )
    def products(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get product settings
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
