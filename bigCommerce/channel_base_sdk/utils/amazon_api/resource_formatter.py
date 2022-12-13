# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.resource_formatter import DataTrans
from ..common.exceptions import NotParseableException

class PayloadDataInTrans(DataTrans):
    """
    General data transformer for Amazon resource from channel to app
    """
    transform_singular: DataTrans
    
    def __call__(self, data):
        data = data.get('payload', {})
        if isinstance(data, list):
            result = list(map(self.transform_singular, data))
        elif isinstance(data, dict):
            result = self.transform_singular(data)
        elif 'errors' in data:
            result = data
        else:
            raise NotParseableException('Data not processed')
        return result
    
class DataInTrans(DataTrans):
    """
    General data transformer for Amazon resource from channel to app
    """
    transform_singular: DataTrans
    
    def __call__(self, data):
        if isinstance(data, list):
            result = list(map(self.transform_singular, data))
        elif isinstance(data, dict):
            result = self.transform_singular(data)
        elif 'errors' in data:
            result = data
        else:
            raise NotParseableException('Data not processed')
        return result


class DataOutTrans(DataTrans):
    """
    General data transformer for Amazon resource from app to channel
    """
    transform_singular: DataTrans

    def __call__(self, data):
        if isinstance(data, list):
            result = list(map(self.transform_singular, data))
        elif isinstance(data, dict):
            result = self.transform_singular(data)
        else:
            raise NotParseableException('Data not processed')
        return result
