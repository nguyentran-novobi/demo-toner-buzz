# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import shopify_api as shopify

from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


def test_set_inventory_levels_one_called():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.inventory_levels.acknowledge(None, inventory_item_id=12742109321, location_id=81426531462)
    acknowledged.data = dict(available=785)
    expected = {'inventory_item_id': 12742109321, 'location_id': 81426531462, 'available': 785}

    with patch_request(json=expected) as mock_request:
        product = acknowledged.set_available()

    mock_request.assert_called_once_with(
        'POST',
        'https://test-store.myshopify.com/admin/api/2022-01/inventory_levels/set.json',
        headers=BASE_HEADERS,
        json=expected,
    )

    assert product.ok()
    assert product.data == expected


def test_set_inventory_levels_one_wo_ack_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = {'inventory_item_id': 12742109321, 'location_id': 81426531462, 'available': 785}
    inv_level = api.inventory_levels.create_new_with(expected)

    with patch_request(json=expected) as mock_request:
        product = inv_level.set_available()

    mock_request.assert_called_once_with(
        'POST',
        'https://test-store.myshopify.com/admin/api/2022-01/inventory_levels/set.json',
        headers=BASE_HEADERS,
        json=expected,
    )

    assert product.ok()
    assert product.data == expected
