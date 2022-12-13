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


@register_model('pricelist_records')
class BigCommercePricelistRecordModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Pricelists
    """
    prefix = 'pricelists/{pricelist_id}/'
    path = 'records'
    primary_key = None
    secondary_keys = ('pricelist_id',)
    transform_in_data = DataInTrans()

    @request_builder.delegated
    @request_builder.make_request_builder(
        set_to='builder',
        method='PUT',
        uri='',
    )
    def upsert(self, prop=None, builder=None, **kwargs):
        """
        Update or insert up to 1000 items into the pricelist
        :param prop: The data propagated from the handler
        :param builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        response = self.build_and_send_json_request_from(
            builder,
            prop=prop,
            params=kwargs,
        )
        return self.pass_result_to_handler(nil=True, response=response)

    @request_builder.delegated
    @request_builder.make_request_builder(
        set_to='builder',
        method='DELETE',
        uri='',
    )
    def delete_all(self, prop=None, builder=None, **kwargs):
        """
        Update or insert up to 1000 items into the pricelist
        :param prop: The data propagated from the handler
        :param builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        response = self.build_and_send_json_request_from(
            builder,
            prop=prop,
            params=kwargs,
        )
        return self.pass_result_to_handler(nil=True, response=response)
