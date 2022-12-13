# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ...common import resource_formatter as common_formatter
from .. import resource_formatter as bigcommerce_formatter


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Bigcommerce category from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, category):
        return {
            'id': category['id'],
            'name': category['name'],
            'parent_id': category['parent_id'],
            'url': category['url'],
            'children': category['children'],
        }


class DataInTrans(bigcommerce_formatter.DataInTransV3):
    """
    Specific data transformer for Bigcommerce category from channel to app
    """
    transform_singular = SingularDataInTrans()


@register_model('category_tree')
class BigCommerceCategoryTreeModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulList,
):
    """
    An interface of BigCommerce category
    """

    transform_in_data = DataInTrans()

    prefix = 'catalog/'
    path = 'categories/tree'
    primary_key = 'id'
