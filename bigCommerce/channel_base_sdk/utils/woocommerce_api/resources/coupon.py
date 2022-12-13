# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import WooCommercePaginated
from ...common import resource_formatter as common_formatter
from .. import resource_formatter as woocommerce_formatter

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Woo Coupon from channel to app
    """

    def __call__(self, coupon):
        basic_data = self.process_basic_data(coupon)
        result = {
            **basic_data,
        }
        return result
                
    @classmethod
    def process_basic_data(cls, coupon):
        return coupon


class DataInTrans(woocommerce_formatter.DataInTrans):
    """
    Specific data transformer for Woo Coupon from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('coupons')
class WooCommerceCouponModel(
    resource.WooCommerceResourceModel,
    request_builder.RestfulGet,
    request_builder.RestfulList,
    WooCommercePaginated,
):
    """
    An interface of Woo Coupon
    """
    path = 'coupons'
    primary_key = 'id'
    transform_in_data = DataInTrans()
