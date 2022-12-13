# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful.request_builder import RestfulGet, RestfulPost, RestfulList

from ..resource import ShopifyResourceModel
from ..registry import register_model


@register_model('order_transactions')
class ShopifyOrderTransactionModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulList,
):
    """
    An interface of Shopify Order Transaction
    """
    prefix = 'orders/{order_id}/'
    path = 'transactions'
    postfix = '.json'
    primary_key = 'id'
