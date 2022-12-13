# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.api import RestfulAPI
from ..restful.connection import RestfulConnection

from .registry import model_registry


class BigCommerceAPI(RestfulAPI):
    """
    BigCommerce API gateway
    """
    store_hash: str
    access_token: str

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """
        store_hash, access_token = self.extract_credentials(credentials)
        self.connection = self.build_connection(store_hash, access_token)

    @classmethod
    def extract_credentials(cls, credentials):
        """
        :param credentials:
            Credentials needed for connecting to channel. It should be something like::

                {
                    'store_hash': '2khj4821',
                    'access_token': 'f9e21a1945b8fb51bce6fa1595c06405',
                }

        :exception MissingRequiredKey:
            raises if the required keys are missing. Required keys: store_hash, access_token
        """
        try:
            return credentials['store_hash'], credentials['access_token']
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @classmethod
    def build_connection(cls, store_hash: str, access_token: str):
        """
        Build connection from the provided hostname and access token
        """
        connection = RestfulConnection(
            scheme='https://',
            hostname='api.bigcommerce.com/',
            uri=f'stores/{store_hash}/',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Auth-Token': access_token,
            },
        )
        return connection


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for Bigcommerce connector
    """
    return BigCommerceAPI(credentials, model_registry)
