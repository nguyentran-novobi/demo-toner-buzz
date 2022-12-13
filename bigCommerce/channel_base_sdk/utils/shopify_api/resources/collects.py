# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter, fields
from ...restful.request_builder import RestfulGet, RestfulPost, RestfulDelete, RestfulList, RestfulPut

from ..registry import register_model
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from .. import resource_formatter as shopify_formatter


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify collect for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'collection_id',
        'position',
        'product_id',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        if 'collect' in data:
            collect = data['collect']
            extracted = self.extract_singular(collect)
            result = {
                'collect': extracted
            }
        else:
            collects = data['collects']
            extracted = list(map(self.extract_singular, collects))
            result = {
                'collects': extracted
            }
        return result

    def extract_singular(self, collect):
        """
        Extract data of a single collect data
        """
        result = self.extract_data(collect)
        return result


class BasicTrans(common_formatter.DescriptorTrans):
    id = fields.Int2Str()
    collection_id = fields.Int2Str()
    position = fields.Retaining()
    product_id = fields.Int2Str()


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'collect'
    resource_plural_name = 'collects'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify Custom Collection from channel to app
    """
    transform_basic_data = BasicTrans()

    def __call__(self, collection):
        basic_data = self.transform_basic_data(collection)
        result = {
            **basic_data,
        }
        return result


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Smart Collection from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Specific data transformer for Shopify Custom Collection from app to channel
    """
    transform_basic_data = BasicTrans.inverse

    def __call__(self, data):
        basic_data = self.transform_basic_data(data)
        result = {
            **basic_data,
        }
        return result


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify Smart Collection from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('collects')
class ShopifyCollectsModel(
    ShopifyResourceModel,
    RestfulPut,
    RestfulGet,
    RestfulPost,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Collects
    """
    path = 'collects'
    postfix = '.json'

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
