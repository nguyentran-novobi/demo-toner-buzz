# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated


@register_model('order_products')
class BigCommerceOrderProductModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce order product
    """
    prefix = 'orders/{order_id}/'
    path = 'products'
    primary_key = 'id'
    secondary_keys = ('order_id',)
