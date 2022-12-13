# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter

from ...restful.request_builder import RestfulGet, RestfulPut, RestfulList

from .. import resource_formatter as shopify_formatter
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from ..registry import register_model


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify inventory item from channel to app
    """

    def __call__(self, item):
        return {
            'id': str(item['id']),
            'sku': item['sku'],
            'requires_shipping': item['requires_shipping'],
            'tracked': item['tracked'],
        }


class DataInTrans(shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify inventory item from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_singular_name = 'inventory_item'
    resource_plural_name = 'inventory_items'


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify inventory item from app to channel
    """

    def __call__(self, data):
        return {
            'id': int(data['id']),
            'sku': data['sku'],
            'requires_shipping': data['requires_shipping'],
            'tracked': data['tracked'],
        }


class DataOutTrans(shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify inventory item from app to channel
    """
    transform_singular = SingularDataOutTrans()
    resource_singular_name = 'inventory_item'
    resource_plural_name = 'inventory_items'


@register_model('inventory_items')
class ShopifyInventoryItemModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPut,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Inventory Item
    """
    path = 'inventory_items'
    postfix = '.json'
    primary_key = 'id'

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
