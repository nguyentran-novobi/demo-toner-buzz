# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.common import ResourceComposite

from test_utils.shopify_api.common import CREDENTIALS


@pytest.mark.parametrize('get_gateway_from', [
    lambda api: api.shop,
    lambda api: api.locations,
    lambda api: api.customers,
    lambda api: api.orders,
    lambda api: api.order_transactions,
    lambda api: api.order_fulfillment,
    lambda api: api.collects,
    lambda api: api.custom_collections,
    lambda api: api.smart_collections,
    lambda api: api.products,
    lambda api: api.product_variants,
    lambda api: api.product_images,
    lambda api: api.inventory_items,
    lambda api: api.inventory_levels,
])
def test_get_resource_gateway(get_gateway_from):
    api = shopify.connect_with(CREDENTIALS)
    res = get_gateway_from(api)
    assert res is not None
    assert not res and isinstance(res, ResourceComposite)


@pytest.mark.parametrize('get_gateway_by_dot,get_gateway_by_getter,get_gateway_by_attr', [
    (lambda api: api.shop, lambda api: api['shop'], lambda api: getattr(api, 'shop')),
    (lambda api: api.locations, lambda api: api['locations'], lambda api: getattr(api, 'locations')),
    (lambda api: api.customers, lambda api: api['customers'], lambda api: getattr(api, 'customers')),
    (lambda api: api.orders, lambda api: api['orders'], lambda api: getattr(api, 'orders')),
    (lambda api: api.order_transactions, lambda api: api['order_transactions'],
     lambda api: getattr(api, 'order_transactions')),
    (lambda api: api.order_fulfillment, lambda api: api['order_fulfillment'],
     lambda api: getattr(api, 'order_fulfillment')),
    (lambda api: api.collects, lambda api: api['collects'], lambda api: getattr(api, 'collects')),
    (lambda api: api.custom_collections, lambda api: api['custom_collections'],
     lambda api: getattr(api, 'custom_collections')),
    (lambda api: api.smart_collections, lambda api: api['smart_collections'],
     lambda api: getattr(api, 'smart_collections')),
    (lambda api: api.products, lambda api: api['products'], lambda api: getattr(api, 'products')),
    (lambda api: api.product_variants, lambda api: api['product_variants'],
     lambda api: getattr(api, 'product_variants')),
    (lambda api: api.product_images, lambda api: api['product_images'], lambda api: getattr(api, 'product_images')),
    (lambda api: api.inventory_items, lambda api: api['inventory_items'], lambda api: getattr(api, 'inventory_items')),
    (lambda api: api.inventory_levels, lambda api: api['inventory_levels'],
     lambda api: getattr(api, 'inventory_levels')),
])
def test_get_resource_gateway_by_many_ways(get_gateway_by_dot, get_gateway_by_getter, get_gateway_by_attr):
    api = shopify.connect_with(CREDENTIALS)
    dot, getter, attr = get_gateway_by_dot(api), get_gateway_by_getter(api), get_gateway_by_attr(api)
    assert dot._model.__class__ is getter._model.__class__
    assert getter._model.__class__ is attr._model.__class__
