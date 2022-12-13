# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import amazon_api as amazon

from test_utils.amazon_api.common import CREDENTIALS, COMPLETE_CREDENTIALS


@pytest.mark.parametrize('cred', [
    CREDENTIALS,
    COMPLETE_CREDENTIALS,
])
def test_get_api(cred):
    api = amazon.connect_with(cred)
    assert api
