# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import PropagatedParam
from ...common.resource import delegated

from ...restful.request_builder import RestfulPost, RestfulList
from ...restful.request_builder import make_request_builder, RequestBuilder

from ..registry import register_model
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated


@register_model('inventory_levels')
class ShopifyInventoryLevelModel(
    ShopifyResourceModel,
    RestfulList,
    ShopifyPaginated,
    RestfulPost
):
    """
    An interface of Shopify Inventory Level
    """
    path = 'inventory_levels'
    postfix = '.json'
    primary_key = None
    secondary_keys = ('inventory_item_id', 'location_id')

    @delegated
    @make_request_builder(
        method='POST',
        uri='/set',
    )
    def set_available(self, prop: PropagatedParam = None,
                      request_builder: RequestBuilder = None, **kwargs):
        """
        Update Quantity of Inventory Item on Shopify
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
