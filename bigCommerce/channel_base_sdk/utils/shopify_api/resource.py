# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..restful.request_builder import RestfulResourceModel

from .const import API_VERSION


class ShopifyResourceModel(RestfulResourceModel):
    """
    This class contains all needed method to apply and make Shopify request on resource
    """
    version = f'{API_VERSION}/'
