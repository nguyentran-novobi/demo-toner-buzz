# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from dataclasses import dataclass

from ..common import ResourceComposite
from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.connection import RestfulConnection, RestfulConnectionLazyHeaders
from ..restful.api import RestfulAPI

from .const import USER_AGENT
from .registry import model_registry
from .connection import AmazonConnection
from .resources.token import OAuthTokenModel


class NoValidTokenException(Exception):
    pass


@dataclass
class TokenHolder:
    """
    Holds token and the time that the token would be expired
    Expiration time is always in UTC
    """

    __slots__ = (
        'expires_at',
        'raw_token',
    )

    expires_at: datetime
    raw_token: str

    @property
    def token(self):
        if not self.is_provided or self.is_expired:
            raise NoValidTokenException()
        return self.raw_token

    @property
    def is_provided(self):
        return self.raw_token is not None

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= datetime.utcnow()


class TokenManager:
    _content: dict

    def __init__(self):
        self._content = dict()

    def __getitem__(self, refresh_token):
        return self._content[refresh_token]

    def __setitem__(self, refresh_token, value):
        if isinstance(value, dict):
            self.set_dict_value(refresh_token, value)
        elif isinstance(value, TokenHolder):
            self.set_holder_value(refresh_token, value)
        else:
            raise ValueError(f'Unsupported value: Cannot set token with this value: {value!r}')

    def set_dict_value(self, refresh_token, dictionary):
        self.set_holder_value(refresh_token, TokenHolder(
            expires_at=dictionary['expires_at'],
            raw_token=dictionary['token'],
        ))

    def set_holder_value(self, refresh_token, holder):
        self._content[refresh_token] = holder


class AmazonAPI(RestfulAPI):
    """
    Amazon API gateway
    """
    REGION_HOSTS = {
        'us-east-1': 'sellingpartnerapi-na.amazon.com',
        'eu-west-1': 'sellingpartnerapi-eu.amazon.com',
        'us-west-2': 'sellingpartnerapi-fe.amazon.com',
    }

    region: str
    _refresh_token: str
    _access_token_info = TokenManager()

    token_connection: RestfulConnection

    def update_credentials(self, credentials: dict):
        cred = self.extract_credentials(credentials)
        self.region = cred['region']
        self._refresh_token = cred['refresh_token']
        return cred

    @classmethod
    def extract_credentials(cls, credentials: dict):
        """
        :param credentials: Credentials needed for connecting to channel.
        It should be something like:
        {
            'region': 'us-east-1',
            'refresh_token': 'Atzr|IwEBIK',
        }
        region can be either: us-east-1, eu-west-1, us-west-2
        :exception: MissingRequiredKey raises if the required keys are missing
        Required keys: region, refresh_token
        """
        try:
            return {
                'region': credentials['region'],
                'refresh_token': credentials['refresh_token'],
            }
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @property
    def connection(self):
        return self.build_connection()

    def build_connection(self):
        """
        Build connection from the access token and the region
        """
        host = self.REGION_HOSTS[self.region]
        connection = RestfulConnectionLazyHeaders(
            scheme='https://',
            hostname=f'{host}/',
            uri='',
            headers=self.get_headers,
        )
        return connection

    @property
    def refresh_token(self):
        return self._refresh_token

    def get_headers(self):
        return {
            'host': self.REGION_HOSTS[self.region],
            'user-agent': USER_AGENT,
            'x-amz-access-token': self.access_token,
        }

    @property
    def access_token(self):
        return self._renew_access_token_if_necessary()

    def _renew_access_token_if_necessary(self):
        try:
            return self._cur_access_token
        except (KeyError, NoValidTokenException):
            return self.renew_access_token()

    @property
    def _cur_access_token(self):
        return self._access_token_info[self._refresh_token].token

    def renew_access_token(self):
        result = self.refresh_access_token()
        self._access_token_info[self._refresh_token] = self._renew_access_token_info(result)
        return self._cur_access_token

    @classmethod
    def _renew_access_token_info(cls, token_info):
        return {
            'expires_at': datetime.utcnow() + timedelta(seconds=token_info['expires_in']),
            'token': token_info['access_token'],
        }

    def refresh_access_token(self):
        raise NotImplementedError

    def get_token_composite(self):
        connection = self.build_token_connection()
        result = ResourceComposite.init_with(connection, OAuthTokenModel(), self.registry)
        return result

    @classmethod
    def build_token_connection(cls):
        """
        Build connection for getting token from Amazon OAuth server
        """
        connection = RestfulConnection(
            scheme='https://',
            hostname='api.amazon.com/',
            uri=f'auth/o2/token/',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        return connection


class CompleteAmazonAPI(AmazonAPI):
    _client_id: str
    _client_secret: str
    _access_key: str
    _secret_access_key: str

    def update_credentials(self, credentials: dict):
        cred = super().update_credentials(credentials)
        self._client_id = cred['client_id']
        self._client_secret = cred['client_secret']
        self._access_key = cred['access_key']
        self._secret_access_key = cred['secret_access_key']
        return cred

    @classmethod
    def extract_credentials(cls, credentials: dict):
        """
        :param credentials: Credentials needed for connecting to channel.
        It should be something like:
        {
            'region': 'us-east-1',
            'refresh_token': 'Atzr|IwEBIK',
            'client_id': 'amzn1.application-oa2-client.be54',
            'client_secret': 'c509e661cd3b1',
            'access_key': 'H294BS8SU3T4PKL1C5IW',
            'secret_access_key': 'PWVsLDq3HZjIb1qM6bn1tl0wYYI8Y98g0NbWgRNC',
        }
        region can be either: us-east-1, eu-west-1, us-west-2
        :exception: MissingRequiredKey raises if the required keys are missing
        Required keys: region, refresh_token, client_id,
                       client_secret, access_key, secret_access_key
        """
        res = super().extract_credentials(credentials)
        try:
            return {**res, **{
                'client_id': credentials['client_id'],
                'client_secret': credentials['client_secret'],
                'access_key': credentials['access_key'],
                'secret_access_key': credentials['secret_access_key'],
            }}
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    def build_connection(self):
        """
        Build connection from the access token and the region
        """
        host = self.REGION_HOSTS[self.region]
        connection = AmazonConnection(
            scheme='https://',
            hostname=f'{host}/',
            uri='',
            headers=self.get_headers,
            access_key=self._access_key,
            secret_access_key=self._secret_access_key,
            region=self.region,
            service='execute-api',
        )
        return connection

    def refresh_access_token(self):
        comp = self.get_token_composite()
        token = comp.create_new_with(dict(
            refresh_token=self.refresh_token,
            client_id=self._client_id,
            client_secret=self._client_secret,
        ))
        result = token.refresh_token()
        return result.data


class AmazonAPIFactory:
    COMPLETE_CREDENTIAL_KEYS = {
        'region',
        'refresh_token',
        'client_id',
        'client_secret',
        'access_key',
        'secret_access_key',
    }

    @classmethod
    def connect_with(cls, credentials: dict):
        if cls.has_all_mandatory_keys(credentials):
            return CompleteAmazonAPI(credentials, model_registry)
        return AmazonAPI(credentials, model_registry)

    @classmethod
    def has_all_mandatory_keys(cls, credentials: dict):
        complete = cls.COMPLETE_CREDENTIAL_KEYS
        return set(credentials.keys()) & complete == complete


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for Amazon connector
    """
    return AmazonAPIFactory.connect_with(credentials)
