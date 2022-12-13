# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated


@register_model('variant_options')
class BigCommerceVariantOptionModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce product variant option
    """
    prefix = 'catalog/products/{product_id}/'
    path = 'options'
    primary_key = 'id'
    secondary_keys = ('product_id',)
