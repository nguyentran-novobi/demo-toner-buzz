# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.resource import ResourceModel
from ..common.resource_data import DelegatedReturn
from ..common.resource_formatter import ResourceFormatterMixin


class RestfulResourceModel(ResourceModel, ResourceFormatterMixin):
    """
    This class contains all needed method to apply and make restful request on resource
    """
    version: str = ''
    prefix: str = ''
    path: str = ''
    postfix: str = ''

    @classmethod
    def pass_result_to_handler(cls, **kwargs):
        return DelegatedReturn(**kwargs)
