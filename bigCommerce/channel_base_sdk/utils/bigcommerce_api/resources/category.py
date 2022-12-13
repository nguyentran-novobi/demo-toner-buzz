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
    Transform only 1 single data of Bigcommerce category from channel to app
    """

    def __call__(self, category):
        basic_data = self.process_basic_data(category)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, category):
        return {
            'id': category['id'],
            'name': category['name'],
            'url': category['custom_url']['url'],
            'description': category['description'],
            'sort_order': category['sort_order'],
            'default_product_sort': category['default_product_sort'],
            'image_url': category['image_url'],
            'page_title': category['page_title'],
            'meta_keywords': ','.join(category['meta_keywords']),
            'search_keywords': category['search_keywords'],
            'meta_description': category['meta_description'],
            'is_visible': category['is_visible'],
        }


class DataInTrans(bigcommerce_formatter.DataInTransV3):
    """
    Specific data transformer for Bigcommerce category from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    def __call__(self, category):
        basic_data = self.process_basic_data(category)

        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, category):
        return {
            'name': category['name'],
            'parent_id': category['parent_id'],
            'custom_url': {
                'url': category['url'],
                'is_customized': True,
            },
            'description': category['description'],
            'sort_order': category['sort_order'],
            'default_product_sort': category['default_product_sort'],
            'image_url': category['image_url'],
            'page_title': category['page_title'],
            'meta_keywords': category['meta_keywords'],
            'search_keywords': category['search_keywords'],
            'meta_description': category['meta_description'],
            'is_visible': category['is_visible'],
        }


class DataOutTrans(bigcommerce_formatter.DataOutTrans):
    """
    Specific data transformer for Bigcommerce category from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('categories')
class BigCommerceCategoryModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce category
    """

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()

    prefix = 'catalog/'
    path = 'categories'
    primary_key = 'id'

