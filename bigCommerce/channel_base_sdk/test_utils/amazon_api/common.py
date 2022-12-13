# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import contextlib

from unittest.mock import ANY, patch

from utils.amazon_api import signature_v4
from utils.amazon_api.api import CompleteAmazonAPI
from utils.amazon_api.const import USER_AGENT


REFRESH_TOKEN = 'Atzr|IwEBIK'
ACCESS_TOKEN = 'Atza|IwEBIBE'
CLIENT_ID = 'amazon-sp-api-client-id'
CLIENT_SECRET = 'amazon-sp-api-client-secret'
ACCESS_KEY = 'H294BS8SU3T4PKL1C5IW'
SECRET_ACCESS_KEY = 'PWVsLDq3HZjIb1qM6bn1tl0wYYI8Y98g0NbWgRNC'
CREDENTIALS = {
    'region': 'us-east-1',
    'refresh_token': REFRESH_TOKEN,
}
COMPLETE_CREDENTIALS = {**CREDENTIALS, **{
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'access_key': ACCESS_KEY,
    'secret_access_key': SECRET_ACCESS_KEY,
}}
TOKEN_HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
}


request_signature = 'AWS4-HMAC-SHA256 55cfba678'
common_headers = {
    'Authorization': request_signature,
    'host': 'sellingpartnerapi-na.amazon.com',
    'user-agent': USER_AGENT,
    'x-amz-access-token': ACCESS_TOKEN,
    'x-amz-date': ANY,
}


@contextlib.contextmanager
def patch_access_token(access_token=None):
    access_token_info = dict(expires_in=3600, access_token=access_token)
    with patch.object(CompleteAmazonAPI, 'refresh_access_token', return_value=access_token_info) as mock_access_token:
        yield mock_access_token


@contextlib.contextmanager
def patch_signature(signature=None):
    headers = dict(Authorization=signature)
    with patch.object(signature_v4, 'get_authorization_headers', return_value=headers) as mock_signature:
        yield mock_signature


@contextlib.contextmanager
def patch_headers():
    with patch_access_token(ACCESS_TOKEN), patch_signature(request_signature):
        yield
