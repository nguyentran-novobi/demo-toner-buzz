# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated


@register_model('order_taxes')
class BigCommerceOrderTaxModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce order tax
    """
    prefix = 'orders/{order_id}/'
    path = 'taxes'
    primary_key = 'id'
    secondary_keys = ('order_id',)
