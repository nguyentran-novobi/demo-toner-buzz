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


@register_model('pricelist_assignments')
class BigCommercePricelistAssignmentModel(
    resource.BigCommerceResourceModelV3,
    request_builder.RestfulList,
    request_builder.RestfulPost,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Pricelists
    """
    prefix = 'pricelists/'
    path = 'assignments'
    primary_key = 'id'
    transform_in_data = DataInTrans()

    @request_builder.delegated
    @request_builder.make_request_builder(
        set_to='builder',
        method='POST',
        uri='',
    )
    def assign_all(self, prop=None, builder=None, **kwargs):
        """
        Post bulk assignment requests
        :param prop: The data propagated from the handler
        :param builder: Request builder from the handler
        :param kwargs: Optional options
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
        Delete all pricelist assignments matched the query criteria
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
