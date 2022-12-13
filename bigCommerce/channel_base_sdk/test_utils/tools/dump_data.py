# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pickle

from . import common


def dump(path, obj):
    with open(path, 'wb') as fp:
        pickle.dump(obj, fp)


def load(path):
    with open(path, 'rb') as fp:
        obj = pickle.load(fp)
    return obj


def load_from_script(script_path, data_path):
    location = common.get_absolute_location_from_script(script_path, data_path)
    return load(location)
