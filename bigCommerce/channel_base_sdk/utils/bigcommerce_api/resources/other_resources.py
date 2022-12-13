# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful.request_builder import RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList

from ..resource import BigCommerceResourceModelV2 as ModelV2,\
    BigCommerceResourceModelV3 as ModelV3
from ..registry import bulk_register_models
from ..request_builder import BigCommercePaginated


class RestfulFullBasic(
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    BigCommercePaginated,
):
    pass


RESOURCES = {
    'store': (
        (ModelV2, RestfulList, BigCommercePaginated),
        dict(path='store', primary_key=None)
    ),
    'price_lists': (
        (ModelV3, RestfulFullBasic),
        dict(path='pricelists', primary_key='id')
    ),
    'order_statuses': (
        (ModelV2, RestfulGet, RestfulList, BigCommercePaginated),
        dict(path='order_statuses', primary_key='id')
    ),
    'order_transactions': (
        (ModelV3, RestfulList, BigCommercePaginated),
        dict(prefix='orders/{order_id}/', path='transactions', primary_key='id', secondary_keys=('order_id',))
    ),
    'product_custom_fields': (
        (ModelV3, RestfulFullBasic),
        dict(prefix='catalog/products/{product_id}/', path='custom-fields',
             primary_key='id', secondary_keys=('product_id',)),
    ),
    'product_bulk_pricing_rules': (
        (ModelV3, RestfulFullBasic),
        dict(prefix='catalog/products/{product_id}/', path='bulk-pricing-rules',
             primary_key='id', secondary_keys=('product_id',)),
    ),
}

bulk_register_models(RESOURCES)
