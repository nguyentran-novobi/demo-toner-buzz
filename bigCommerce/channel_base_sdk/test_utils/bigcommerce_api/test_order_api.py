# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import bigcommerce_api as bigcommerce
from utils.bigcommerce_api.resources.order import BigCommerceOrderModel

from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.bigcommerce_api.common import BASE_HEADERS, CREDENTIALS, STORE_HASH


@not_transform_data(BigCommerceOrderModel)
def test_get_order_information_called():
    api = bigcommerce.connect_with(CREDENTIALS)

    with patch_request(json=dict(id=123)) as mock_request:
        api.orders.all()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders',
        headers=BASE_HEADERS
    )


@not_transform_data(BigCommerceOrderModel)
def test_get_order_all_with_pagination_and_pagination_called():
    api = bigcommerce.connect_with(CREDENTIALS)
    response = [
        dict(id=123),
        dict(id=456),
    ]

    with patch_request(json=response):
        orders = api.orders.all(limit=2)

    with patch_request(json=response) as mock_request:
        orders.get_next_page()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders',
        headers=BASE_HEADERS,
        params={
            'limit': 2,
            'page': 2,
        }
    )
