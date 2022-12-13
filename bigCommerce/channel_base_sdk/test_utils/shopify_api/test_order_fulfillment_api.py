# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.shopify_api.resources.order_fulfillment import DataInTrans, ShopifyOrderFulfillmentModel

from test_utils.tools import json_data, dump_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@not_transform_data(ShopifyOrderFulfillmentModel)
def test_fulfillment_cancel():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.order_fulfillment.acknowledge(12742109321, order_id=81426531462)

    with patch_request(json={}) as mock_request:
        acknowledged.cancel()

    mock_request.assert_called_once_with(
        'POST',
        'https://test-store.myshopify.com/admin/api/2022-01/orders/81426531462/fulfillments/12742109321/cancel.json',
        headers=BASE_HEADERS
    )


@pytest.mark.parametrize('json_path,dump_path', [
    ('order_fulfillment01.json', 'order_fulfillment01.dump'),
    ('order_fulfillment02.json', 'order_fulfillment02.dump'),
    ('order_fulfillment03.json', 'order_fulfillment03.dump'),
    ('order_fulfillment04.json', 'order_fulfillment04.dump'),
])
def test_fulfillment_transformation(json_path, dump_path):
    data = json_data.load(__file__, f'data/order_fulfillment/{json_path}')
    dump_result = dump_data.load_from_script(__file__, f'data/order_fulfillment/{dump_path}')
    in_transform = DataInTrans()

    in_result = in_transform(data)
    assert in_result == dump_result
