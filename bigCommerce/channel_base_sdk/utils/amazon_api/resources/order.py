# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common.resource import delegated
from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonList, AmazonGet, AmazonPaginated, make_request_builder
@register_model('orders')
class AmazonOrderModel(
    AmazonResourceModel,
    AmazonGet,
    AmazonList,
    AmazonPaginated
):
    """
    An interface of Amazon Order
    """

    path = 'orders/v0/orders'
    primary_key = 'id'

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{order_id}',
        no_body=True,
    )
    def get_specific(self, order_id, prop=None, request_builder=None, **kwargs):
        prop.options = {**prop.options, **dict(order_id=order_id)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{order_id}/buyerInfo',
        no_body=True,
    )
    def get_buyer_info(self, order_id, prop=None, request_builder=None, **kwargs):
        prop.options = {**prop.options, **dict(order_id=order_id)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{order_id}/address',
        no_body=True,
    )
    def get_address(self, order_id, prop=None, request_builder=None, **kwargs):
        prop.options = {**prop.options, **dict(order_id=order_id)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{order_id}/orderItems',
        no_body=True,
    )
    def get_items(self, order_id, prop=None, request_builder=None, **kwargs):
        prop.options = {**prop.options, **dict(order_id=order_id)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='GET',
        uri='/{order_id}/orderItems/buyerInfo',
        no_body=True,
    )
    def get_items_buyer_info(self, order_id, prop=None, request_builder=None, **kwargs):
        prop.options = {**prop.options, **dict(order_id=order_id)}
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
