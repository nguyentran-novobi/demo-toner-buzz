# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import bigcommerce_api as bigcommerce

from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.bigcommerce_api.common import BASE_HEADERS, CREDENTIALS, STORE_HASH


@not_transform_data()
@pytest.mark.parametrize('model,uri', [
    ('store', 'v2/store'),
    ('price_lists', 'v3/pricelists'),
    ('order_statuses', 'v2/order_statuses'),
])
def test_get_simple_other_resource_information_called(model, uri):
    api = bigcommerce.connect_with(CREDENTIALS)

    with patch_request(json=dict()) as mock_request:
        api[model].all()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/{uri}',
        headers=BASE_HEADERS
    )


@not_transform_data()
@pytest.mark.parametrize('model,kw,uri', [
    ('order_transactions', dict(order_id=123), 'v3/orders/123/transactions'),
])
def test_get_complex_other_resource_information_called(model, kw, uri):
    api = bigcommerce.connect_with(CREDENTIALS)
    ack = api[model].acknowledge(None, **kw)

    with patch_request(json=dict()) as mock_request:
        ack.all()

    mock_request.assert_called_once_with(
        'GET',
        f'https://api.bigcommerce.com/stores/{STORE_HASH}/{uri}',
        headers=BASE_HEADERS
    )
