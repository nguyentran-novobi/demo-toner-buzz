# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import PropagatedParam, resource_formatter as common_formatter
from ...common.resource import delegated
from ...restful import request_builder
from .. import resource
from .. import resource_formatter as bigcommerce_formatter
from ..registry import register_model
from ..request_builder import BigCommercePaginated


class DataInTrans(bigcommerce_formatter.DataInTransV3):
    """
    Specific data transformer for BigCommerce product from channel to app
    """
    transform_singular = common_formatter.NoneTrans()


@register_model('products')
class BigCommerceProductModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce product
    """
    prefix = 'catalog/'
    path = 'products'
    primary_key = 'id'

    transform_in_data = DataInTrans()

    @delegated
    def put_batch(self, data, prop: PropagatedParam = None):
        """
        Update products in batch
        """
        products = prop.self.create_new_with(data)
        return products.put_data()
