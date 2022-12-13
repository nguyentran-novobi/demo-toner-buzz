# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import datetime
from typing import Optional
import json
from json import JSONEncoder

import dateutil.parser

def map_address(
        address: dict,
        mapping: Optional[dict] = None,
        default: Optional[dict] = None,
        excluded: Optional[set] = None
):
    """
    Change default Odoo address keys with the mapping keys
    """
    if mapping is None:
        mapping = dict()
    if default is None:
        default = dict()
    if excluded is None:
        excluded = set()

    return {
        **{v: address[k] for k, v in mapping.items() if k in address},
        **{k: v for k, v in address.items() if k not in mapping and k not in excluded},
        **default,
    }

class DateTimeEncoder(JSONEncoder):
    # Overide default method to handle datetime type
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()

def json_dumps(obj):
    return json.dumps(obj, indent=4, cls=DateTimeEncoder)

def json_dump(obj, fp):
    return json.dump(obj, fp, indent=4, cls=DateTimeEncoder)

def decode_datetime(dict_obj, key_list=[]):
    for key, value in dict_obj.items():
        if key in key_list:
            dict_obj[key] = dateutil.parser.parse(value)

def json_loads(fp, datetime_fields=[]):
    data = json.load(fp)
    if isinstance(data, dict):
        decode_datetime(data, datetime_fields)
    elif isinstance(data, list):
        for item in data:
            decode_datetime(item, datetime_fields)
    return data
