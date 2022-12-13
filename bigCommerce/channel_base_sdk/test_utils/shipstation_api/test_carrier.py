import base64

from utils import shipstation_api as shipstation

from test_utils.restful.common import patch_request
from test_utils.shipstation_api import common


def test_get_carrier_all():
    expected = dict(abc=123)
    api = shipstation.connect_with(common.CREDENTIALS)

    with patch_request(json=expected) as mock_request:
        carriers = api.carriers.all()

    mock_request.assert_called_once_with(
        'GET',
        'https://ssapi.shipstation.com/carriers',
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % base64.b64encode(bytes("%s:%s" % (common.API_KEY, common.API_SECRET), 'utf-8')).decode('utf-8')
        },
    )

    assert carriers.data == expected

def test_get_services_from_carrier():
    expected = dict(abc=123)
    api = shipstation.connect_with(common.CREDENTIALS)
    carrier_code = 123
    with patch_request(json=expected) as mock_request:
        services = api.carriers.get_list_services(carrier_code)
        mock_request.assert_called_once_with(
            'GET',
            'https://ssapi.shipstation.com/carriers/listservices',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Basic %s' % base64.b64encode(
                    bytes("%s:%s" % (common.API_KEY, common.API_SECRET), 'utf-8')).decode('utf-8')
            },
            params={'carrierCode': 123}
        )

        assert services.data == expected
