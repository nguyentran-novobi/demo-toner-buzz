# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils import shipstation_api as shipstation

from test_utils.shipstation_api.common import CREDENTIALS


@pytest.mark.parametrize('cred', [
    CREDENTIALS,
])
def test_get_api(cred):
    api = shipstation.connect_with(cred)
    assert api
