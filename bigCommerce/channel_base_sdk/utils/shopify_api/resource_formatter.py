# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.resource_formatter import DataTrans
from ..common.exceptions import NotParseableException

import logging

class DataCommonTrans:
    resource_singular_name: str
    resource_plural_name: str


class DataInTrans(DataCommonTrans, DataTrans):
    """
    General data transformer for Shopify resource from channel to app
    """
    transform_singular: DataTrans
    
    def __call__(self, data):
        if self.resource_plural_name in data:
            result = list(map(self.transform_singular, data[self.resource_plural_name]))
        elif self.resource_singular_name in data:
            result = self.transform_singular(data[self.resource_singular_name])
        elif 'errors' in data:
            result = data
        else:
            raise NotParseableException('Data not processed')
        return result


class DataOutTrans(DataCommonTrans, DataTrans):
    """
    General data transformer for Shopify resource from app to channel
    """
    transform_singular: DataTrans

    def __call__(self, data):
        if isinstance(data, list):
            transformed_data = list(map(self.transform_singular, data))
            result = {
                self.resource_plural_name: transformed_data
            }
        elif isinstance(data, dict):
            transformed_data = self.transform_singular(data)
            result = {
                self.resource_singular_name: transformed_data
            }
        else:
            raise NotParseableException('Data not processed')
        return result
