# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.shopify_api.resources.product_image import ShopifyProductImageModel, \
    DataInTrans, DataOutTrans, ExtractingDataTrans

from test_utils.tools import json_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@not_transform_data(ShopifyProductImageModel)
def test_get_all_in_product():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.product_images.acknowledge(None, product_id=81426531462)
    expected = [{
        'id': f'{seq}',
        'url': f'https://image/{seq}.png',
        'product_id': 81426531462,
    } for seq in range(4)]

    with patch_request(json=expected) as mock_request:
        images = acknowledged.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/products/81426531462/images.json',
        headers=BASE_HEADERS,
        params={
            'created_at_min': '2018-04-25T10:02:53+00:00'
        }
    )
    assert images.ok()
    assert images.data == expected


@pytest.mark.parametrize('json_path', [
    'product_image01.json',
    'product_images01.json',
    'product_images02.json',
    'product_images03.json',
])
def test_product_image_transformation(json_path):
    data = json_data.load(__file__, f'data/product_images/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
