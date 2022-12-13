# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..restful.request_builder import RestfulResourceModel


class BigCommerceResourceModel(RestfulResourceModel):
    """
    This class contains all needed method to apply and make Bigcommerce request on resource
    """


class BigCommerceResourceModelV2(BigCommerceResourceModel):
    """
    This class contains all needed method to apply and make Bigcommerce V2 requests
    """
    version = 'v2/'


class BigCommerceResourceModelV3(BigCommerceResourceModel):
    """
    This class contains all needed method to apply and make Bigcommerce V3 requests
    """
    version = 'v3/'
