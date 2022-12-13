# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import bigcommerce_api as bigcommerce

from test_utils.restful.common import patch_request
from test_utils.bigcommerce_api.common import BASE_HEADERS, CREDENTIALS, STORE_HASH


def test_get_brand_information_called():
    api = bigcommerce.connect_with(CREDENTIALS)

    with patch_request(json=dict(id=123)) as mock_request:
        api.brands.all()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/brands',
        headers=BASE_HEADERS
    )


def test_get_brand_all_with_pagination_and_pagination_called():
    api = bigcommerce.connect_with(CREDENTIALS)
    response = {
        'data': [
            dict(id=123),
            dict(id=456),
        ],
        'meta': {
            'pagination': {
                "total": 15,
                "count": 2,
                "per_page": 2,
                "current_page": 1,
                "total_pages": 8,
                "links": {
                    "next": "?limit=2&page=2",
                    "current": "?limit=2&page=1"
                }
            }
        }
    }

    with patch_request(json=response):
        brands = api.brands.all(limit=2)

    with patch_request(json=response) as mock_request:
        brands.get_next_page()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/brands',
        headers=BASE_HEADERS,
        params={
            'limit': '2',
            'page': '2',
        }
    )


def test_get_brand_all_with_pagination_and_end_of_pagination():
    api = bigcommerce.connect_with(CREDENTIALS)
    response = {
        'data': [
            dict(id=123),
        ],
        'meta': {
            'pagination': {
                "total": 15,
                "count": 1,
                "per_page": 2,
                "current_page": 8,
                "total_pages": 8,
                "links": {
                    "previous": "?limit=2&page=7",
                    "current": "?limit=2&page=8"
                }
            }
        }
    }

    with patch_request(json=response):
        brands = api.brands.all(limit=2)

    with patch_request(json=response) as mock_request:
        brands.get_next_page()

    assert not mock_request.called
