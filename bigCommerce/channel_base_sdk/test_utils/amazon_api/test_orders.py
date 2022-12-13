# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from datetime import datetime

from utils import amazon_api as amazon

from test_utils.restful.common import patch_request
from test_utils.amazon_api import common


def test_get_order_all():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)
    created_after = datetime(2021, 5, 30, 0, 0).replace(second=0).isoformat(sep='T')

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.all(CreatedAfter=created_after, MarketplaceIds='ATVPDKIKX0DER')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders',
        headers=common.common_headers,
        params={
            'CreatedAfter': created_after,
            'MarketplaceIds': 'ATVPDKIKX0DER',
        }
    )

    assert orders.data == expected


def test_get_specific_order():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.get_specific('114-0045834-6800219')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders/114-0045834-6800219',
        headers=common.common_headers,
    )

    assert orders.data == expected


def test_get_buyer_info_of_specific_order():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.get_buyer_info('114-0045834-6800219')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders/114-0045834-6800219/buyerInfo',
        headers=common.common_headers,
    )

    assert orders.data == expected


def test_get_address_of_specific_order():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.get_address('114-0045834-6800219')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders/114-0045834-6800219/address',
        headers=common.common_headers,
    )

    assert orders.data == expected


def test_get_items_of_specific_order():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.get_items('114-0045834-6800219')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders/114-0045834-6800219/orderItems',
        headers=common.common_headers,
    )

    assert orders.data == expected


def test_get_items_buyer_info_of_specific_order():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        orders = api.orders.get_items_buyer_info('114-0045834-6800219')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/orders/v0/orders/114-0045834-6800219/orderItems/buyerInfo',
        headers=common.common_headers,
    )

    assert orders.data == expected
