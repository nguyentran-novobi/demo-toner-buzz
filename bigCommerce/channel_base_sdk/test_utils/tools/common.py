# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import os


def get_absolute_location_from_script(script_path, path):
    dir_name = os.path.dirname(os.path.realpath(script_path))
    return os.path.join(dir_name, path)
