# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shopify_api as shopify
from utils.common.resource_data import EmptyDataError
from utils.shopify_api.resources.customer import DataInTrans, DataOutTrans,\
    ExtractingDataTrans, ShopifyCustomerModel

from test_utils.tools import json_data
from test_utils.common.common import not_transform_data
from test_utils.restful.common import patch_request
from test_utils.shopify_api.common import BASE_HEADERS, CREDENTIALS


@not_transform_data(ShopifyCustomerModel)
def test_get_customer_one_connection_error():
    api = shopify.connect_with(CREDENTIALS)
    acknowledged = api.customers.acknowledge(12742109321)
    error_message = 'This is a testing error'

    with patch_request(error=error_message) as mock_request:
        result = acknowledged.get_by_id()

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/customers/12742109321.json',
        headers=BASE_HEADERS
    )

    assert not result.ok()
    with pytest.raises(EmptyDataError):
        assert bool(result.data is None)
    assert result.get_error_message() == error_message
    assert result.get_status_code() is None


@not_transform_data(ShopifyCustomerModel)
def test_get_customer_all_with_pagination_called():
    api = shopify.connect_with(CREDENTIALS)
    expected = [{'customer': 'ok', 'id': f'{seq}'} for seq in range(15)]

    with patch_request(json=expected, headers={'Link': 'abc.com'}) as mock_request:
        customers = api.customers.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://test-store.myshopify.com/admin/api/2022-01/customers.json',
        headers=BASE_HEADERS,
        params={
            'created_at_min': '2018-04-25T10:02:53+00:00'
        }
    )

    assert customers.ok()
    assert customers.data == expected
    assert customers._extra_content == {
        'paginated_link': 'abc.com'
    }


@pytest.mark.parametrize('json_path', [
    'customer01.json',
    'customers01.json',
    'customers02.json',
])
def test_customer_transformation(json_path):
    data = json_data.load(__file__, f'data/customers/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
