import base64

from utils import shipstation_api as shipstation

from test_utils.restful.common import patch_request
from test_utils.shipstation_api import common


def test_get_store_all():
    expected = dict(abc=123)
    api = shipstation.connect_with(common.CREDENTIALS)

    with patch_request(json=expected) as mock_request:
        stores = api.stores.all()

    mock_request.assert_called_once_with(
        'GET',
        'https://ssapi.shipstation.com/stores',
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % base64.b64encode(bytes("%s:%s" % (common.API_KEY, common.API_SECRET), 'utf-8')).decode('utf-8')
        },
    )

    assert stores.data == expected
