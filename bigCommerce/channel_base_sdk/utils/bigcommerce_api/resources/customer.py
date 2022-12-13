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

    def __call__(self, customer):
        basic_data = self.process_basic_data(customer)
        address_data = self.process_address_data(customer)
        result = {
            **basic_data,
            **address_data
        }
        return result
                
    @classmethod
    def process_basic_data(cls, customer):
        return {
            'id': str(customer['id']),
            'email': customer['email'],
            'phone': customer['phone'],
            'first_name': customer['first_name'],
            'last_name': customer['last_name'],
            'company': customer['company']
        }

    @classmethod
    def process_address_data(cls, customer):
        default_address = {}
        # addresses = customer.get('addresses', [])
        # if addresses:
        #     default_address = addresses[0]
        return {
            'street': default_address.get('address1', ''),
            'street2': default_address.get('address2', ''),
            'city': default_address.get('city', ''),
            'state_name': default_address.get('state_or_province'),
            'country_code': default_address.get('country_code'),
            'zip': default_address.get('postal_code', ''),
        }

class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Customer from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('customers')
class BigCommerceCustomerModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Customer
    """
    path = 'customers'
    primary_key = 'id'
    transform_in_data = DataInTrans()
