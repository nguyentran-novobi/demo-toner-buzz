# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import datetime
import itertools

from ...common import PropagatedParam, resource_formatter as common_formatter
from ...common import fields
from ...common.resource import delegated

from ...restful.request_builder import \
    RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList

from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from .. import resource_formatter as shopify_formatter
from ..registry import register_model

from . import variant
from . import product_image


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify product for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'title',
        'body_html',
        'vendor',
        'product_type',
        'tags',
        'variants',
        'options',
        'images',
    ])
    extract_variant_data = variant.ExtractingDataTrans()
    extract_image_data = product_image.ExtractingDataTrans()

    def __call__(self, data):
        """
        Extract data
        """
        if 'product' in data:
            product = data['product']
            extracted = self.extract_singular(product)
            result = {
                'product': extracted
            }
        else:
            products = data['products']
            extracted = list(map(self.extract_singular, products))
            result = {
                'products': extracted
            }
        return result

    def extract_singular(self, product):
        """
        Extract data of a single product data
        """
        extracted = self.extract_data(product)
        variants = self.extract_variant_data(product)
        images = self.extract_image_data(product)
        result = {
            **extracted,
            **variants,
            **images,
        }
        return result


class ExtractingBaseVariantDataInTrans(common_formatter.DescriptorTrans):
    """
    Specific data transformer for extracting base variant data
    """
    to_float = common_formatter.DefaultFloatTrans()

    price = fields.Custom(compute=to_float, inverse=str)
    compare_at_price = fields.Custom('compare_at_price', compute=to_float, inverse=str)
    default_code = fields.Retaining('sku')
    barcode = fields.Retaining()
    weight = fields.Retaining()
    weight_unit = fields.Retaining()
    requires_shipping = fields.Retaining()


class BasicTrans(common_formatter.DescriptorTrans):
    id = fields.Int2Str()
    title = fields.Retaining()
    body_html = fields.Retaining()
    vendor = fields.Retaining()
    product_type = fields.Retaining()
    tags = fields.Retaining()
    options = fields.Retaining()


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'product'
    resource_plural_name = 'products'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify product from channel to app
    """
    transform_basic_data = BasicTrans()
    transform_variant_data = variant.DataInTrans()
    extract_base_variant_data = ExtractingBaseVariantDataInTrans()
    transform_image_data = product_image.DataInTrans()
    datetime_str_to_datetime = common_formatter.StrToDatetimeTrans()

    def __call__(self, product):
        basic_data = self.process_basic_data(product)
        image_data = self.process_image(product)
        variant_data = self.process_variant(product)
        result = {
            **basic_data,
            **image_data,
            **variant_data,
        }
        return result

    def process_image(self, product):
        """
        Process image data pf the product
        """
        images_data = self.transform_image_data(product)
        result = {
            'images': images_data,
        }
        return result

    def process_variant(self, product):
        """
        Process variant data of the product
        """
        result = {}

        variant_data = self.transform_variant_data(product)
        result['variants'] = variant_data

        if len(variant_data) == 1:
            base_variant_data = variant_data[0]
            extracted_data = self.extract_base_variant_data(base_variant_data)
            result.update(extracted_data)

        result.update({
            'requires_shipping': any(var['requires_shipping'] for var in variant_data)
        })

        return result

    def process_basic_data(self, product):
        """
        Process basic data of the product
        """
        result = self.transform_basic_data(product)
        result.update({
            'handle': product['handle'],
            'url': "/products/%s" % product['handle'],
            'is_visible': bool(product['published_at']),
            'type': 'physical' if product.get('requires_shipping') else 'digital',
            'published_at': self.datetime_str_to_datetime(product['published_at']) if product['published_at'] else None,
            'published_scope': product.get('published_scope', False),
        })
        return result


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify product from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Specific data transformer for Shopify product from app to channel
    """
    transform_basic_data = BasicTrans.inverse
    datetime_to_datetime_str = common_formatter.DatetimeToStrTrans()
    transform_variant_data = variant.DataOutTrans()
    transform_image_data = product_image.DataOutTrans()

    def __call__(self, data):
        basic_data = self.process_basic_data(data)
        visibility_data = self.process_visibility(data)
        variant_data = self.transform_variant_data(data['variants'])
        image_data = self.transform_image_data(data['images']) if 'images' in data else {}
        result = {
            **basic_data,
            **visibility_data,
            **variant_data,
            **image_data,
        }
        return result

    def process_basic_data(self, data):
        """
        Generate basic data of the product
        """
        result = self.transform_basic_data(data)
        return result

    def process_visibility(self, data):
        """
        Generate visibility data of the product
        """
        is_visible = data.get('is_visible')
        if is_visible and not data['published_at']:
            published_at = self.datetime_to_datetime_str(self.get_datetime_now())
        elif not is_visible:
            published_at = ''
        elif data['published_at']:
            published_at = self.datetime_to_datetime_str(data['published_at'])
        else:
            published_at = ''
        result = {
            'published_at': published_at
        }
        return result

    @classmethod
    def get_datetime_now(cls):
        """
        Get the current datetime and eliminate microsecond
        """
        return datetime.datetime.now().replace(microsecond=0)


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify product from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('products')
class ShopifyProductModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Product
    """
    path = 'products'
    postfix = '.json'
    primary_key = 'id'

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()

    def update_images(self, images):
        """
        Update images of the product
        """

    def update_variants(self, variants):
        """
        Update variants of the product
        """

    @delegated
    def get_variants(self, prop: PropagatedParam = None):
        """
        Extract Variants from data
        :param prop: The data propagated from the handler
        """
        variant_data = list(itertools.chain(*prop.resource.map_path('variants')))
        return self.pass_result_to_handler(model='product_variants', data=variant_data)

    @delegated
    def import_inventory_item_info(self, prop: PropagatedParam = None):
        """
        Get information of inventory item of the products
        Information will be appended into the product info itself
        """
        variants = prop.self.get_variants()
        variants.import_inventory_item_info()
        return self.pass_result_to_handler(resource=prop.resource)
