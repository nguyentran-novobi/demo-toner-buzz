# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from unittest.mock import call, patch

from utils.common.resource_data import EmptyDataError

from utils import shopify_api as shopify
from utils.shopify_api.resources.product import DataInTrans, DataOutTrans,\
    ExtractingDataTrans, ShopifyProductModel
from utils.shopify_api.resources.inventory_item import ShopifyInventoryItemModel

from test_utils.tools import json_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@not_transform_data(ShopifyProductModel)
def test_get_product_one_connection_error():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.products.acknowledge(12742109321)
    error_message = 'This is a testing error'

    with patch_request(error=error_message) as mock_request:
        result = acknowledged.get_by_id()

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/products/12742109321.json',
        headers=BASE_HEADERS
    )

    assert not result.ok()
    with pytest.raises(EmptyDataError):
        assert bool(result.data is None)
    assert result.get_error_message() == error_message
    assert result.get_status_code() is None


@not_transform_data(ShopifyProductModel)
def test_get_product_all_with_pagination_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15)]

    with patch_request(json=expected, headers={'Link': 'abc.com'}) as mock_request:
        products = api.products.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/products.json',
        headers=BASE_HEADERS,
        params={
            'created_at_min': '2018-04-25T10:02:53+00:00'
        }
    )

    assert products.ok()
    assert products.data == expected
    assert products._extra_content == {
        'paginated_link': 'abc.com'
    }


@not_transform_data(ShopifyProductModel)
def test_get_product_all_with_pagination_and_pagination_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15)]
    with patch_request(json=expected, headers={'Link': '<abc.com>; rel="next"'}):
        products = api.products.all(created_at_min='2018-04-25T10:02:53+00:00')

    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15, 30)]
    with patch_request(json=expected, headers={'Link': '<abc.com>; rel="next"'}):
        products = products.get_next_from_link()

    assert products.ok()
    assert products.data == expected


def test_extract_variants():
    api = shopify.connect_with(CREDENTIALS)
    variants = [{
        'msg': '12581283',
        'status': 'ok'
    }, {
        'msg': '78684086',
        'status': 'passed'
    }]
    data = {'variants': variants, 'msg': 'gotcha'}
    product = api.products.create_new()
    product.data = data
    product_variants = product.get_variants()
    assert product_variants.data == variants


def test_extract_variants_nil():
    api = shopify.connect_with(CREDENTIALS)
    product = api.products
    variants = product.get_variants()
    assert len(variants) == 0


def test_extract_variants_many():
    api = shopify.connect_with(CREDENTIALS)
    variant_values = [{
        'msg': '12581283',
        'status': 'ok',
    }, {
        'msg': '78684086',
        'status': 'passed',
    }, {
        'msg': '89721462',
        'status': 'fine',
    }]
    data = [{
        'variants': variant_values[:2],
        'msg': 'gotcha'
    }, {
        'variants': variant_values[2:],
        'msg': 'resting'
    }]
    products = api.products.create_collection_with(data)
    variants = products.get_variants()
    assert variants.data == variant_values


def test_import_inventory_item_info():
    api = shopify.connect_with(CREDENTIALS)
    inv_items = [{
        'id': '12783120947',
        'requires_shipping': False,
        'tracked': True,
    }, {
        'id': '12783120965',
        'requires_shipping': True,
        'tracked': False,
    }]
    mock_all_result = ShopifyInventoryItemModel.pass_result_to_handler(data=inv_items)
    data = {
        'variants': [{
            'inventory_item_id': '12783120947',
            'status': 'ok',
        }, {
            'inventory_item_id': '12783120965',
            'status': 'passed',
        }],
        'msg': 'gotcha'
    }
    expected = {
        'variants': [{
            'inventory_item_id': '12783120947',
            'status': 'ok',
            'requires_shipping': False,
            'inventory_tracking': True,
        }, {
            'inventory_item_id': '12783120965',
            'status': 'passed',
            'requires_shipping': True,
            'inventory_tracking': False,
        }],
        'msg': 'gotcha'
    }
    product = api.products.create_new()
    product.data = data
    with patch('utils.shopify_api.resources.inventory_item.ShopifyInventoryItemModel.all') as mock_all:
        mock_all.delegated = 'prop'
        mock_all.return_value = mock_all_result
        product = product.import_inventory_item_info()
    assert product.data == expected


def test_import_inventory_item_info_nil():
    api = shopify.connect_with(CREDENTIALS)
    result = api.products.import_inventory_item_info()
    assert result is not None and bool(result) is False


@not_transform_data(ShopifyProductModel)
def test_get_and_update_product_called():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.products.acknowledge(12742109321)
    expected1 = {'id': 12742109321, 'product': 'ok', 'msg': 'gotcha'}

    data = {'product': 'ko', 'msg': 'ach tog'}
    expected2 = {**dict(id=12742109321), **data}

    with patch_request(json=expected1):
        product = acknowledged.get_by_id()

    product.data = data

    with patch_request(json=expected2) as mock_request_2:
        product = product.put_one()

    mock_request_2.assert_called_with(
        'PUT',
        'https://test-store.myshopify.com/admin/api/2022-01/products/12742109321.json',
        headers=BASE_HEADERS,
        json=expected2
    )

    assert product.ok()
    assert product.data == expected2


@pytest.mark.parametrize('json_path', [
    'product01.json',
    'product02.json',
    'product03.json',
    'products01.json',
    'products02.json',
])
def test_product_transformation(json_path):
    data = json_data.load(__file__, f'data/products/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
