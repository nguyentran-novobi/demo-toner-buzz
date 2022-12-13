# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils.shopify_api.resources import collects

from test_utils.tools import json_data


@pytest.mark.parametrize('json_path', [
    'collect01.json',
    'collects01.json',
    'collects02.json',
])
def test_product_transformation(json_path):
    data = json_data.load(__file__, f'data/collects/{json_path}')
    in_transform = collects.DataInTrans()
    out_transform = collects.DataOutTrans()
    extract = collects.ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
