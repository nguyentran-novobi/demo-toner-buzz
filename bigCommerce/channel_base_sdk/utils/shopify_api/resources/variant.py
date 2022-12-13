# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import PropagatedParam, resource_formatter as common_formatter
from ...common import fields
from ...common.resource import delegated

from ...restful.request_builder import \
    RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList

from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from .. import resource_formatter as shopify_formatter
from ..registry import register_model


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify product variant for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'id',
        'product_id',
        'title',
        'price',
        'sku',
        'compare_at_price',
        'barcode',
        'image_id',
        'weight',
        'requires_shipping',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        if 'variant' in data:
            variant = data['variant']
            extracted = self.extract_singular(variant)
            result = {
                'variant': extracted
            }
        else:
            variants = data['variants']
            extracted = list(map(self.extract_singular, variants))
            result = {
                'variants': extracted
            }
        return result

    def extract_singular(self, product):
        """
        Extract data of a single product data
        """
        result = self.extract_data(product)
        return result


class BasicTrans(common_formatter.DescriptorTrans):
    to_float = common_formatter.DefaultFloatTrans()
    float_to_str = common_formatter.MonetaryStringTrans(prefix=False)

    id = fields.Int2Str()
    product_id = fields.Int2Str()
    title = fields.Retaining('name')
    price = fields.Custom(compute=to_float, inverse=float_to_str)
    sku = fields.Retaining()
    barcode = fields.Retaining()
    weight = fields.Custom(compute=to_float, inverse=to_float)
    requires_shipping = fields.Retaining()


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'variant'
    resource_plural_name = 'variants'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify product variant from channel to app
    """
    transform_basic_data = BasicTrans()
    to_float = common_formatter.DefaultFloatTrans()

    def __call__(self, product):
        basic_data = self.process_basic_data(product)
        options = self.process_options(product)
        result = {
            **basic_data,
            **options,
        }
        return result

    def process_basic_data(self, product):
        """
        Process basic data of the product
        """
        result = self.transform_basic_data(product)
        result.update({
            'position': product['position'],
            'compare_at_price': self.to_float(product.get('compare_at_price')),
            'image_id': product['image_id'],
            'weight_unit': 'lb',
            'inventory_item_id': str(product['inventory_item_id']),
            'inventory_quantity': self.to_float(product['inventory_quantity']),
            'inventory_tracking': True,
        })
        return result

    @classmethod
    def process_options(cls, product):
        """
        Process attribute options
        """
        options = [f'option{idx}' for idx in range(1, 4)]
        result = {
            key: product.get(key)
            for key in options
        }
        return result


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify product variant from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify product variant from app to channel
    """
    transform_basic_data = BasicTrans.inverse
    to_float = common_formatter.DefaultFloatTrans()
    float_to_str = common_formatter.MonetaryStringTrans(prefix=False)

    def __call__(self, data):
        basic_data = self.process_basic_data(data)
        options = self.process_options(data)
        image_data = self.process_image(data)
        result = {
            **basic_data,
            **options,
            **image_data,
        }
        return result

    def process_basic_data(self, data):
        """
        Process basic data of the product
        """
        result = self.transform_basic_data(data)
        result.update({
            'compare_at_price': self.float_to_str(data['compare_at_price']) if data.get('compare_at_price', False) else None,
        })
        return result

    @classmethod
    def process_options(cls, data):
        """
        Process attribute options
        """
        options = [f'option{idx}' for idx in range(1, 4)]
        result = {
            key: data[key]
            for key in options
            if data.get(key)
        }
        return result

    @classmethod
    def process_image(cls, data):
        """
        Generate Image Data of the product
        """
        result = {
            'image_id': data.get('image_id'),
        }
        return result


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify product variant from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('product_variants')
class ShopifyProductVariantModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Product Variant
    """
    prefix = 'products/{product_id}/'
    path = 'variants'
    postfix = '.json'
    primary_key = 'id'
    secondary_keys = ('product_id',)

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
    transform_float = common_formatter.DefaultFloatTrans()

    def update_images(self, images):
        """
        Update images of the product
        """

    @delegated
    def import_inventory_item_info(self, prop: PropagatedParam = None):
        """
        Get information of inventory item of the products
        Information will be appended into the product info itself
        """
        def extract_inv_item(inv):
            return {
                'requires_shipping': inv['requires_shipping'],
                'inventory_tracking': inv['tracked'],
            }

        if prop.resource:
            inv_ids = prop.resource.map_path('inventory_item_id')
            inv_items = self.env['inventory_items'].all(ids=','.join(inv_ids))
            for res in prop.resource:
                match_inv = next(inv_items.filter_field(id=res.data['inventory_item_id']), None)
                if match_inv:
                    res.data.update(extract_inv_item(match_inv.data))

        return self.pass_result_to_handler(resource=prop.resource)
