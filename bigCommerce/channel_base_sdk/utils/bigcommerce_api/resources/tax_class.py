# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated


@register_model('tax_classes')
class BigCommerceTaxClassModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce tax class
    """
    path = 'tax_classes'
    primary_key = 'id'
