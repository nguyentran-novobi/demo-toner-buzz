# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json

from . import common


def load(script_path, data_path):
    location = common.get_absolute_location_from_script(script_path, data_path)
    with open(location, 'r') as fp:
        return json.load(fp)
