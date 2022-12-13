# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.shopify_api.resources.shop import DataInTrans, DataOutTrans,\
    ExtractingDataTrans

from test_utils.tools import json_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@pytest.mark.parametrize('json_path', [
    'shop.json',
])
def test_shop_transformation(json_path):
    data = json_data.load(__file__, f'data/shop/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)


@pytest.mark.parametrize('json_path', [
    'shop.json',
])
def test_get_shop_all_called_real(json_path):
    data = json_data.load(__file__, f'data/shop/{json_path}')
    api = shopify.connect_with(CREDENTIALS)
    expected = {
        'id': '50572329130',
        'admin_email': 'hello@omniborders.com',
        'weight_unit': 'lb',
        'secure_url': 'https://qa-omnichannel.myshopify.com',
    }

    with patch_request(json=data) as mock_request:
        shop = api.shop.all()

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/shop.json',
        headers=BASE_HEADERS
    )

    assert shop.ok()
    assert shop.data == expected
