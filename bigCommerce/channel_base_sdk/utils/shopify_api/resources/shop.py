# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter
from ...common.exceptions import NotParseableException

from ...restful.request_builder import RestfulList

from ..resource import ShopifyResourceModel
from .. import resource_formatter as shopify_formatter
from ..registry import register_model


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify Shop for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'email',
        'weight_unit',
        'myshopify_domain',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        if 'shop' in data:
            shop = data['shop']
            extracted = self.extract_singular(shop)
            result = {
                'shop': extracted
            }
        else:
            raise NotParseableException('Incorrect Format')
        return result

    def extract_singular(self, shop):
        """
        Extract data of a single shop data
        """
        result = self.extract_data(shop)
        return result


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Shop from channel to app
    """

    def __call__(self, shop):
        result = {
            'id': str(shop['id']),
            'admin_email': shop['email'],
            'weight_unit': shop['weight_unit'],
            'secure_url': 'https://%s' % shop['myshopify_domain'],
        }
        return result


class DataInTrans(shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Shop from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_singular_name = 'shop'
    resource_plural_name = None


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Specific data transformer for Shopify Shop from app to channel
    """

    def __call__(self, data):
        result = {
            'id': int(data['id']),
            'email': data['admin_email'],
            'weight_unit': data['weight_unit'],
            'myshopify_domain': data['secure_url'].lstrip('https://'),
        }
        return result


class DataOutTrans(shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify Shop from app to channel
    """
    transform_singular = SingularDataOutTrans()
    resource_singular_name = 'shop'
    resource_plural_name = None


@register_model('shop')
class ShopifyShopModel(
    ShopifyResourceModel,
    RestfulList,
):
    """
    An interface of Shopify Shop
    """
    path = 'shop'
    postfix = '.json'
    primary_key = None

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
