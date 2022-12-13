# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.common.resource_data import EmptyDataError

from utils.shopify_api.resources.variant import ShopifyProductVariantModel, DataInTrans,\
    DataOutTrans, ExtractingDataTrans

from test_utils.tools import json_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


def test_acknowledge_product_variant():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.product_variants.acknowledge(12742109321, product_id=81426531462)
    expected = {'id': 12742109321, 'product_id': 81426531462}
    assert acknowledged.keys == expected


@not_transform_data(ShopifyProductVariantModel)
def test_get_product_variant_one_called():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.product_variants.acknowledge(12742109321, product_id=81426531462)
    expected = {'product_variant': 'ok', 'msg': 'gotcha'}

    with patch_request(json=expected) as mock_request:
        product = acknowledged.get_by_id()

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/variants/12742109321.json',
        headers=BASE_HEADERS
    )

    assert product.ok()
    assert product.data == expected


@not_transform_data(ShopifyProductVariantModel)
def test_get_product_variant_all_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15)]
    acknowledged = api.product_variants.acknowledge(None, product_id=81426531462)

    with patch_request(json=expected) as mock_request:
        products = acknowledged.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/variants.json',
        headers=BASE_HEADERS,
        params={
            'created_at_min': '2018-04-25T10:02:53+00:00'
        }
    )

    assert products.ok()
    assert products.data == expected


@not_transform_data(ShopifyProductVariantModel)
def test_publish_product_variant_one_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = {'product': 'ok', 'msg': 'gotcha', 'product_id': 81426531462}
    acknowledged = api.product_variants.acknowledge(None, product_id=81426531462)
    acknowledged.data = expected

    with patch_request(json=expected) as mock_request:
        acknowledged.publish()

    mock_request.assert_called_once_with(
        'POST',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/variants.json',
        headers=BASE_HEADERS,
        json=expected,
    )

    assert acknowledged.ok()
    assert acknowledged.data == expected


@not_transform_data(ShopifyProductVariantModel)
def test_put_product_variant_one_called():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.product_variants.acknowledge(12742109321, product_id=81426531462)
    data = {'product': 'ok', 'msg': 'gotcha', 'product_id': 81426531462}
    acknowledged.data = data
    expected = {**dict(id=12742109321), **data}

    with patch_request(json=expected) as mock_request:
        product = acknowledged.put_one()

    mock_request.assert_called_once_with(
        'PUT',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/variants/12742109321.json',
        headers=BASE_HEADERS,
        json=expected
    )

    assert product.ok()
    assert product.data == expected


@not_transform_data(ShopifyProductVariantModel)
def test_delete_product_variant_one_called():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.product_variants.acknowledge(12742109321, product_id=81426531462)

    with patch_request(json={}) as mock_request:
        result = acknowledged.delete_one()

    mock_request.assert_called_once_with(
        'DELETE',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/variants/12742109321.json',
        headers=BASE_HEADERS
    )
    assert result.ok()
    with pytest.raises(EmptyDataError):
        assert bool(result.data is None)


@not_transform_data(ShopifyProductVariantModel)
def test_get_product_variant_all_with_pagination_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15)]
    acknowledged = api.product_variants.acknowledge(None, product_id=81426531462)

    with patch_request(json=expected, headers={'Link': 'abc.com'}) as mock_request:
        products = acknowledged.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2020-10/products/81426531462/variants.json',
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


@pytest.mark.parametrize('json_path', [
    'variant01.json',
    'variant02.json',
    'variants01.json',
    'variants02.json',
    'variants03.json',
])
def test_product_variant_transformation(json_path):
    data = json_data.load(__file__, f'data/product_variants/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
