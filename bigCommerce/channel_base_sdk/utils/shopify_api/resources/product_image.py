# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter
from ...common import fields

from ...restful.request_builder import \
    RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList

from ..resource import ShopifyResourceModel
from .. import resource_formatter as shopify_formatter
from ..registry import register_model


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify product image for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'product_id',
        'position',
        'alt',
        'src',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        result = {}
        if 'images' in data:
            images = data['images']
            extracted = list(map(self.extract_singular, images))
            result.update({
                'images': extracted
            })
        return result

    def extract_singular(self, image):
        """
        Extract data of a single product image
        """
        if isinstance(image, dict):
            result = self.extract_data(image)
            return result
        return image


class BasicTrans(common_formatter.DescriptorTrans):
    id = fields.Int2Str()
    product_id = fields.Int2Str()
    position = fields.Retaining()
    alt = fields.Retaining()
    src = fields.Retaining()
    variant_ids = fields.Retaining()


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'image'
    resource_plural_name = 'images'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify product image from channel to app
    """
    transform_basic = BasicTrans()

    def __call__(self, image):
        result = self.transform_basic(image)
        return result


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify product from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify product image from app to channel
    """
    transform_basic = BasicTrans.inverse

    def __call__(self, data):
        result = self.transform_basic(data)
        return result


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify product variant from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('product_images')
class ShopifyProductImageModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList
):
    """
    An interface of Shopify Product Image
    """
    prefix = 'products/{product_id}/'
    path = 'images'
    postfix = '.json'
    primary_key = 'id'
    secondary_keys = ('product_id',)

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
