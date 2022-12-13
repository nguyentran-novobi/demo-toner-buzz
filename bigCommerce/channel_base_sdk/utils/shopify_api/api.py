# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.api import RestfulAPI
from ..restful.connection import RestfulConnection

from .registry import model_registry


class ShopifyAPI(RestfulAPI):
    """
    Shopify API gateway
    """
    hostname: str
    access_token: str

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """
        hostname, access_token = self.extract_credentials(credentials)
        self.connection = self.build_connection(hostname, access_token)

    @classmethod
    def extract_credentials(cls, credentials):
        """
        :param credentials: Credentials needed for connecting to channel.
        It should be something like:
        {
            'hostname': 'test-store.myshopify.com',
            'access_token': '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',
        }
        :exception: MissingRequiredKey raises if the required keys are missing
        Required keys: hostname, access_token
        """
        try:
            hostname = credentials['hostname']
            access_token = credentials['access_token']
            return hostname, access_token
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @classmethod
    def build_connection(cls, hostname: str, access_token: str):
        """
        Build connection from the provided hostname and access token
        """
        connection = RestfulConnection(
            scheme='https://',
            hostname=hostname if hostname.endswith('/') else f'{hostname}/',
            uri=f'admin/api/',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Shopify-Access-Token': access_token,
            },
        )
        return connection


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for Shopify connector
    """
    return ShopifyAPI(credentials, model_registry)
