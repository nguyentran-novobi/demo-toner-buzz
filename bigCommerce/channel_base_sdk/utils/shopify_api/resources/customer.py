# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter

from ...restful.request_builder import RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList

from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from .. import resource_formatter as shopify_formatter
from ..registry import register_model


class ExtractingAddressDataTrans(common_formatter.DataTrans):
    """Extract only needed keys of Shopify Customer Address for comparison"""

    extract_data = common_formatter.PickedDictTrans([
        'first_name',
        'last_name',
        'address1',
        'address2',
        'city',
        'zip',
        'phone',
        'state_code',
        'country_code',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        return self.extract_singular(data)

    def extract_singular(self, address):
        """
        Extract data of a single address data
        """
        return self.extract_data(address)


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify Customer for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'email',
        'default_address',
    ])
    extract_default_address = ExtractingAddressDataTrans()

    def __call__(self, data):
        """
        Extract data
        """
        if 'customer' in data:
            customer = data['customer']
            extracted = self.extract_singular(customer)
            result = {
                'customer': extracted
            }
        else:
            customers = data['customers']
            extracted = list(map(self.extract_singular, customers))
            result = {
                'customers': extracted
            }
        return result

    def extract_singular(self, customer):
        """
        Extract data of a single customer data
        """
        extracted = self.extract_data(customer)
        default_address = self.process_default_address(customer)
        result = {
            **extracted,
            **default_address,
        }
        return result

    def process_default_address(self, customer):
        default_address = self.extract_default_address(customer['default_address'])
        return {
            'default_address': default_address,
        }


class SingularAddressDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Customer Address from channel to app
    """

    def __call__(self, address):
        result = {
            'first_name': address['first_name'],
            'last_name': address['last_name'],
            'street': address['address1'],
            'street2': address['address2'],
            'city': address['city'],
            'zip': address['zip'],
            'phone': address['phone'],
            'state_code': address['province_code'],
            'country_code': address['country_code'],
        }
        return result


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Customer from channel to app
    """
    transform_address = SingularAddressDataInTrans()

    def __call__(self, customer):
        basic_data = self.process_basic_data(customer)
        default_address = self.transform_address(customer['default_address'])
        result = {
            **basic_data,
            **default_address,
        }
        return result

    @classmethod
    def process_basic_data(cls, customer):
        result = {
            'id': str(customer['id']),
            'email': customer['email'],
        }
        return result


class DataInTrans(shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Customer from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_singular_name = 'customer'
    resource_plural_name = 'customers'


class SingularAddressDataOutTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Customer Address from app to channel
    """

    def __call__(self, data):
        result = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'address1': data['street'],
            'address2': data['street2'],
            'city': data['city'],
            'zip': data['zip'],
            'phone': data['phone'],
            'province_code': data['state_code'],
            'country_code': data['country_code'],
        }
        return result


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Specific data transformer for Shopify Customer from app to channel
    """
    transform_address = SingularAddressDataOutTrans()

    def __call__(self, data):
        basic_data = self.process_basic_data(data)
        default_address = self.process_default_address(data)
        result = {
            **basic_data,
            **default_address,
        }
        return result

    @classmethod
    def process_basic_data(cls, data):
        result = {
            'id': int(data['id']),
            'email': data['email'],
        }
        return result

    def process_default_address(self, data):
        result = {
            'default_address': self.transform_address(data)
        }
        return result


class DataOutTrans(shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify Customer from app to channel
    """
    transform_singular = SingularDataOutTrans()
    resource_singular_name = 'customer'
    resource_plural_name = 'customers'


@register_model('customers')
class ShopifyCustomerModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Customer
    """
    path = 'customers'
    postfix = '.json'
    primary_key = 'id'
    
    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
