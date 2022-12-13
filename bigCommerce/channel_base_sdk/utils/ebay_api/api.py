# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.api import RestfulAPI
from ..restful.connection import RestfulConnection
from base64 import b64encode
from .registry import model_registry


class eBayAPI(RestfulAPI):
    """
    WooCommerce API gateway
    """
    access_token: str

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """
        environment, access_token = self.extract_credentials(credentials)
                                
        self.connection = self.build_connection(environment, access_token)

    @classmethod
    def extract_credentials(cls, credentials):
        """
        :param credentials:
            Credentials needed for connecting to channel. It should be something like::

                {
                    'environment': 'sandbox',
                    'access_token': 'f9e21a1945b8fb51bce6fa1595c06405',
                }

        :exception MissingRequiredKey:
            raises if the required keys are missing. Required keys: app_client_id, app_client_secret
        """
        try:
            
            return credentials['environment'], credentials['access_token']             
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @classmethod
    def build_connection(cls, environment: str, access_token: str):
        """
        Build connection from the provided hostname and access token
        """
        end_point = 'api.sandbox.ebay.com' if environment == 'sandbox' else 'api.ebay.com'
        connection = RestfulConnection(
            scheme='https://',
            hostname=end_point,
            uri='',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
            },
        )
        return connection


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for WooCommerce connector
    """
    return eBayAPI(credentials, model_registry)
