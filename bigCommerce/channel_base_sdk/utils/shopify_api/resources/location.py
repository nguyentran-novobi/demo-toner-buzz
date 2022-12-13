# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter

from ...restful.request_builder import RestfulGet, RestfulList

from ..resource import ShopifyResourceModel
from .. import resource_formatter as shopify_formatter
from ..registry import register_model


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify location from channel to app
    """

    def __call__(self, product):
        basic_data = self.process_basic_data(product)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, location):
        """
        Process basic data of the product
        """
        result = {
            'id': str(location['id']),
            'name': location['name'],
            'street': location['address1'],
            'street2': location['address2'],
            'city': location['city'],
            'zip': location['zip'],
            'country_code': location['country_code'],
            'state_code': location['province_code'],
            'active': location['active'],
        }
        return result


class DataInTrans(shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify location from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_singular_name = 'location'
    resource_plural_name = 'locations'


@register_model('locations')
class ShopifyLocationModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulList,
):
    """
    An interface of Shopify Location
    """
    path = 'locations'
    postfix = '.json'
    primary_key = 'id'

    transform_in_data = DataInTrans()
