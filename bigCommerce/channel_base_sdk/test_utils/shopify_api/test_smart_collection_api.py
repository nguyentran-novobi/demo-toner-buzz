# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils.shopify_api.resources.smart_collection import DataInTrans, DataOutTrans, ExtractingDataTrans

from test_utils.tools import json_data


@pytest.mark.parametrize('json_path', [
    'smart_collection01.json',
    'smart_collections01.json',
    'smart_collections02.json',
])
def test_smart_collection_transformation(json_path):
    data = json_data.load(__file__, f'data/smart_collections/{json_path}')
    in_transform = DataInTrans()
    out_transform = DataOutTrans()
    extract = ExtractingDataTrans()

    in_result = in_transform(data)
    out_result = out_transform(in_result)
    assert extract(data) == extract(out_result)
