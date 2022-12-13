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

    def __call__(self, address):
        address_data = self.process_address_data(address)
        result = {
            **address_data
        }
        return result
                
    @classmethod
    def process_address_data(cls, address):
        return {
            'street': address.get('address1', ''),
            'street2': address.get('address2', ''),
            'city': address.get('city', ''),
            'state_name': address.get('state'),
            'country_code': address.get('country_iso2'),
            'zip': address.get('postal_code', ''),
            'first_name': address.get('first_name', ''),
            'last_name': address.get('last_name', ''),
            'company': address.get('company', ''),
        }

class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Customer from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('customer_addresses')
class BigCommerceCustomerAddressModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Customer Address
    """
    prefix = 'customers/{customer_id}/'
    path = 'addresses'
    primary_key = 'id'
    secondary_keys = ('customer_id',)
    transform_in_data = DataInTrans()
