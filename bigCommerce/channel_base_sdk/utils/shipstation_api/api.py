import base64

from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.api import RestfulAPI
from ..restful.connection import RestfulConnection

from .registry import model_registry


class ShipStationAPI(RestfulAPI):
    """
    ShipStation API gateway
    """
    api_key: str
    api_secret: str

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """
        api_key, api_secret = self.extract_credentials(credentials)
        self.connection = self.build_connection(api_key, api_secret)

    @classmethod
    def extract_credentials(cls, credentials):
        """
        :param credentials: Credentials needed for connecting to channel.
        It should be something like:
        {
            'api_key': 'a1945b8fe6f9e21fa1595c0b51bc6405',
            'api_secret': 'a1945b8fe6f9e21fa1595c0b51bc6405',
        }
        :exception: MissingRequiredKey raises if the required keys are missing
        Required keys: hostname, access_token
        """
        try:
            api_key = credentials['api_key']
            api_secret = credentials['api_secret']
            return api_key, api_secret
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @classmethod
    def build_connection(cls, api_key: str, api_secret: str):
        """
        Build connection from the provided api_key and api_secret
        """
        connection = RestfulConnection(
            scheme='https://',
            uri='',
            hostname='ssapi.shipstation.com/',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Basic %s' % base64.b64encode(bytes("%s:%s" % (api_key, api_secret), 'utf-8')).decode('utf-8')
            },
        )
        return connection


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for ShipStation connector
    """
    return ShipStationAPI(credentials, model_registry)
