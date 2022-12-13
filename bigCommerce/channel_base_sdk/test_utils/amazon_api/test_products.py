# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import amazon_api as amazon

from test_utils.restful.common import patch_request
from test_utils.amazon_api import common


def test_get_product_asin():
    expected = dict(abc=123)
    api = amazon.connect_with(common.COMPLETE_CREDENTIALS)

    with patch_request(json=expected) as mock_request, common.patch_headers():
        product = api.products.get_by_asin('1789532477', MarketplaceId='ATVPDKIKX0DER')

    mock_request.assert_called_once_with(
        'GET',
        'https://sellingpartnerapi-na.amazon.com/catalog/v0/items/1789532477',
        headers=common.common_headers,
        params={
            'MarketplaceId': 'ATVPDKIKX0DER',
        }
    )

    assert product.data == expected
