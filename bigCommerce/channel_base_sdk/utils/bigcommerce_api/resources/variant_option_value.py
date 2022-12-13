# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated


@register_model('variant_option_values')
class BigCommerceVariantOptionValueModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce product variant option value
    """
    prefix = 'catalog/products/{product_id}/options/{option_id}/'
    path = 'values'
    primary_key = 'id'
    secondary_keys = ('product_id', 'option_id')
