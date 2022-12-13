import base64

from utils import shipstation_api as shipstation
from unittest.mock import ANY, patch

from test_utils.restful.common import patch_request
from test_utils.shipstation_api import common


def test_get_order_all():
    expected = dict(abc=123)
    api = shipstation.connect_with(common.CREDENTIALS)

    with patch_request(json=expected) as mock_request:
        orders = api.orders.all()

    mock_request.assert_called_once_with(
        'GET',
        'https://ssapi.shipstation.com/orders',
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % base64.b64encode(bytes("%s:%s" % (common.API_KEY, common.API_SECRET), 'utf-8')).decode('utf-8')
        },
    )

    assert orders.data == expected


def test_get_order_all_with_pagination_and_pagination_called():
    api = shipstation.connect_with(common.CREDENTIALS)
    response = {
        "orders": [
            {
                "orderId": 987654321,
                "orderNumber": "Test-International-API-DOCS",
            },
            {
                "orderId": 123456789,
                "orderNumber": "TEST-ORDER-API-DOCS",
            }
        ],
        "total": 14,
        "page": 1,
        "pages": 14
    }

    with patch_request(json=response) as mock_request:
        orders = api.orders.all()

    with patch_request(json=response) as mock_request:
        orders.get_next_page()

    mock_request.assert_called_once_with(
        'GET',
        'https://ssapi.shipstation.com/orders',
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % base64.b64encode(bytes("%s:%s" % (common.API_KEY, common.API_SECRET), 'utf-8')).decode('utf-8'),
        },
        params={
            'page': 2,
        }
    )
