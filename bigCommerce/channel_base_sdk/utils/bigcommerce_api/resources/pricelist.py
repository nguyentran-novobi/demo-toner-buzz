# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import resource_formatter as common_formatter
from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated
from .. import resource_formatter as bigcommerce_formatter


class DataInTrans(bigcommerce_formatter.DataInTransV3):
    """
    Specific data transformer for Bigcommerce category from channel to app
    """
    transform_singular = common_formatter.NoneTrans()


@register_model('pricelists')
class BigCommercePricelistModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Pricelists
    """
    path = 'pricelists'
    primary_key = 'id'
    transform_in_data = DataInTrans()

    @request_builder.delegated
    def remove_all_rules(self, prop=None):
        pricelist = prop.self
        acknowledged = self.env['pricelist_records'].acknowledge(None, pricelist_id=pricelist.key)
        return acknowledged.delete_all()

    @request_builder.delegated
    def upsert_records(self, record_data, prop=None):
        pricelist = prop.self
        acknowledged = self.env['pricelist_records'].recognize(pricelist_id=pricelist.key)
        acknowledged.data = record_data
        return acknowledged.upsert()
