# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated
from ...common import resource_formatter as common_formatter
from .. import resource_formatter as bigcommerce_formatter


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Customer from channel to app
    """

    def __call__(self, method):
        return {
            'name': method['name'],
            'code': method['code']
        }
                
class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Customer from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('payment_method')
class BigCommercePaymentMethodModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Customer Address
    """
    prefix = 'payments/'
    path = 'methods'
    primary_key = 'id'
    transform_in_data = DataInTrans()
