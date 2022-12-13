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
    Transform only 1 single data of Bigcommerce gateway group from channel to app
    """

    def __call__(self, payment_gateway):
        basic_data = self.process_basic_data(payment_gateway)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, payment_gateway):
        return {
            'code': payment_gateway['code'],
            'name': payment_gateway['name'],
            'id_on_channel': payment_gateway['code'],
        }


class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for Bigcommerce gateway group from channel to app
    """
    transform_singular = SingularDataInTrans()


@register_model('payment_gateway')
class BigCommercePaymentGatewayModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce payment gateway
    """

    transform_in_data = DataInTrans()

    prefix = 'payments/'
    path = 'methods'
    primary_key = 'id'

