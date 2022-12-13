# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils.shopify_api.resources.location import DataInTrans

from test_utils.tools import dump_data, json_data


@pytest.mark.parametrize('json_path,dump_path', [
    ('location01.json', 'location01.dump'),
    ('locations01.json', 'locations01.dump'),
])
def test_location_transformation(json_path, dump_path):
    data = json_data.load(__file__, f'data/locations/{json_path}')
    dump_result = dump_data.load_from_script(__file__, f'data/locations/{dump_path}')
    in_transform = DataInTrans()

    in_result = in_transform(data)
    assert in_result == dump_result
