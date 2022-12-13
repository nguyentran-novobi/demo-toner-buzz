# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import WooCommercePaginated
from ...common import resource_formatter as common_formatter
from .. import resource_formatter as woocommerce_formatter

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Woo Customer from channel to app
    """

    def __call__(self, customer):
        basic_data = self.process_basic_data(customer)
        result = {
            **basic_data,
        }
        return result
                
    @classmethod
    def process_basic_data(cls, customer):
        return customer


class DataInTrans(woocommerce_formatter.DataInTrans):
    """
    Specific data transformer for Woo Customer from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('customers')
class WooCommerceCustomerModel(
    resource.WooCommerceResourceModel,
    request_builder.RestfulGet,
    request_builder.RestfulList,
    WooCommercePaginated,
):
    """
    An interface of BigCommerce Customer
    """
    path = 'customers'
    primary_key = 'id'
    transform_in_data = DataInTrans()
