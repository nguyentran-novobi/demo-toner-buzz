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
    Transform only 1 single data of Bigcommerce customer group from channel to app
    """

    def __call__(self, customer_group):
        basic_data = self.process_basic_data(customer_group)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, customer_group):
        return {
            'id': customer_group['id'],
            'name': customer_group['name'],
            'category_access': True if customer_group['category_access']['type'] == 'all' else False,
            'categories': customer_group['category_access'].get('categories'),
        }


class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for Bigcommerce customer group from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
    def __call__(self, customer_group):
        basic_data = self.process_basic_data(customer_group)

        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, customer_group):
        vals = {
            'name': customer_group['name'],
            'category_access': {
                'type': customer_group['category_access'],
            }
        }
        if customer_group['category_access'] == 'specific':
            vals['category_access'].update({
                'categories': customer_group['categories']
            })
        return vals


class DataOutTrans(bigcommerce_formatter.DataOutTrans):
    """
    Specific data transformer for Bigcommerce customer group from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('customer_group')
class BigCommerceCustomerGroupModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce customer group
    """

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()

    path = 'customer_groups'
    primary_key = 'id'

