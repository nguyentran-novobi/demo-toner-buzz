# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter
from ...restful.request_builder import RestfulGet, RestfulPost, RestfulDelete, RestfulList, RestfulPut

from .. import resource_formatter as shopify_formatter
from ..registry import register_model
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated


class ExtractingDataTrans(common_formatter.DataTrans):
    """
    Extract only needed keys of Shopify smart collection for comparison
    """
    extract_data = common_formatter.PickedDictTrans([
        'title',
        'sort_order',
        'body_html',
        'rules',
    ])

    def __call__(self, data):
        """
        Extract data
        """
        if 'smart_collection' in data:
            smart_collection = data['smart_collection']
            extracted = self.extract_singular(smart_collection)
            result = {
                'smart_collection': extracted
            }
        else:
            smart_collections = data['smart_collections']
            extracted = list(map(self.extract_singular, smart_collections))
            result = {
                'smart_collections': extracted
            }
        return result

    def extract_singular(self, product):
        """
        Extract data of a single product data
        """
        extracted = self.extract_data(product)
        result = {
            **extracted,
        }
        return result


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'smart_collection'
    resource_plural_name = 'smart_collections'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify smart collection from channel to app
    """
    datetime_str_to_datetime = common_formatter.StrToDatetimeTrans()

    def __call__(self, collection):
        basic_data = self.process_basic_data(collection)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, collection):
        """
        Process basic data of the collection
        """
        published_at = collection['published_at']
        result = {
            'id': str(collection['id']),
            'name': collection['title'],
            'type': 'smart',
            'sort_order': collection['sort_order'],
            'published': True if collection['published_at'] else False,
            'published_at': cls.datetime_str_to_datetime(published_at) if published_at else None,
            'description': collection['body_html'],
            'disjunctive': collection.get('disjunctive', False),
            'status': 'published',
            'url': '/collections/%s' % collection['handle'],
            'image': {
                'src': collection.get('image', {}).get('src', '')
            },
            'rules': collection['rules']
        }
        return result


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify Smart Collection from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    """
    Specific data transformer for Shopify Smart Collection from app to channel
    """
    def __call__(self, data):
        basic_data = self.process_basic_data(data)
        rules_data = self.process_rules_data(data)

        result = {
            **basic_data,
            **rules_data
        }
        return result

    @classmethod
    def process_basic_data(cls, data):
        """
        Process data to prepare basic info for smart collection
        """
        return {
            "title": data['name'],
            "sort_order": data['sort_order'],
            "published": data['published'],
            "body_html": data['description'],
            "image": {
                'src': data['image']['src']
            } if data.get('image', {}) else '',
        }

    @classmethod
    def process_rules_data(cls, data):
        """
        Process data to prepare basic info for rules of smart collection
        """
        rules = [{
            'column': rule['column'],
            'relation': rule['relation'],
            'condition': rule['condition']
        } for rule in data.get('rules', [])]

        return {'rules': rules}


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify Smart Collection from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('smart_collections')
class ShopifySmartCollectionModel(
    ShopifyResourceModel,
    RestfulPut,
    RestfulGet,
    RestfulPost,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Smart Collection
    """
    path = 'smart_collections'
    postfix = '.json'

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
