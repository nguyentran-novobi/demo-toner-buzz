# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from utils import amazon_api as amazon

from test_utils.tools import json_data
from test_utils.restful.common import patch_request
from test_utils.amazon_api.common import CLIENT_ID, CLIENT_SECRET, \
    COMPLETE_CREDENTIALS, REFRESH_TOKEN, TOKEN_HEADERS


def test_refresh_token_called():
    api = amazon.connect_with(COMPLETE_CREDENTIALS)
    expected = json_data.load(__file__, 'data/tokens.json')

    with patch_request(json=expected) as mock_request:
        result = api.refresh_access_token()

    mock_request.assert_called_once_with(
        'POST',
        'https://api.amazon.com/auth/o2/token/',
        headers=TOKEN_HEADERS,
        data={
            'grant_type': 'refresh_token',
            'refresh_token': REFRESH_TOKEN,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        },
    )

    assert result == expected
