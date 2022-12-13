# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.shopify_api.resources.order import ShopifyOrderModel, DataInTrans

from test_utils.tools import dump_data, json_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@pytest.mark.parametrize('json_path,dump_path', [
    ('order01.json', 'order01.dump'),
])
def test_order_transformation(json_path, dump_path):
    data = json_data.load(__file__, f'data/orders/{json_path}')
    dump_result = dump_data.load_from_script(__file__, f'data/orders/{dump_path}')
    in_transform = DataInTrans()

    in_result = in_transform(data)
    assert in_result == dump_result


@not_transform_data(ShopifyOrderModel)
def test_cancel_order():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.orders.acknowledge(12742109321)
    expected = {'order': 'ok', 'msg': 'gotcha'}

    with patch_request(json=expected) as mock_request:
        order = acknowledged.cancel()

    mock_request.assert_called_once_with(
        'POST',
        'https://test-store.myshopify.com/admin/api/2022-01/orders/12742109321/cancel.json',
        headers=BASE_HEADERS
    )

    assert order.data == expected
