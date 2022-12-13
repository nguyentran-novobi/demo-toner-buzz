# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import os
import json


def get_data_path(
        script_path: str,
        data_path: str,
):
    """
    Get full data path for open function to read
    """
    dir_name = os.path.dirname(os.path.realpath(script_path))
    return os.path.join(dir_name, data_path)


def load_json_from_relative(
        script_path: str,
        data_path: str,
):
    path = get_data_path(script_path, data_path)
    with open(path, 'r') as fp:
        return json.load(fp)
