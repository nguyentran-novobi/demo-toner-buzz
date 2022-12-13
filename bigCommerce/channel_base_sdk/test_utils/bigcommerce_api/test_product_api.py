# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import bigcommerce_api as bigcommerce

from test_utils.restful.common import patch_request
from test_utils.bigcommerce_api.common import BASE_HEADERS, CREDENTIALS, STORE_HASH


def test_get_product_information_called():
    api = bigcommerce.connect_with(CREDENTIALS)

    with patch_request(json=dict(id=123)) as mock_request:
        api.products.all()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products',
        headers=BASE_HEADERS
    )
