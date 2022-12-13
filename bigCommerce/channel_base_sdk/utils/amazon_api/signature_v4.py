# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import re
import hmac
import hashlib
import urllib.parse

from typing import Union, Tuple
from datetime import datetime
from dataclasses import dataclass

from .const import BASIC_ISO_DATE_STAMP_FORMAT, DATE_STAMP_FORMAT

char = Union[bytes, str]


@dataclass
class AuthorizationBuilder:
    """
    This follows Amazon steps to generate request signature which will be put into the request headers
    https://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html
    There are total 4 tasks:
    - Task 1: Create a canonical request
    - Task 2: Create a string to sign
    - Task 3: Calculate the signature
    - Task 4: Add the signature to the HTTP request

    This class has some below attributes:

    uri: str,               e.g.: '/', '/documents%2520and%2520settings/'
    headers: dict,          e.g.: {'host': 'ec2.amazonaws.com', 'x-amz-date': '20201225'}
    params: dict,           e.g.: {'Action': 'DescribeRegions', 'Version': '2013-10-15'}
    data: char,             e.g.: '{"id":3,"order":"OO-23dd-nss"}', b'\x33\x01\x92r='
    method: str,            e.g.: 'GET', 'POST'
    access_key: str,        e.g.: 'A7KN4I4K5A'
    secret_access_key: str, e.g.: 'A5k4I4NK7a'
    request_time: datetime, e.g.: datetime(2020, 12, 25, 16, 22, 19)
    region: str,            e.g.: 'us-east-1', 'eu-west-1'
    service: str,           e.g.: 'execute-api', 'ec2'
    """
    NAME = 'AWS4'
    ALGORITHM = 'AWS4-HMAC-SHA256'
    TERMINATION_STRING = 'aws4_request'
    CREDENTIAL_KEYS = ('Credential', 'SignedHeaders', 'Signature')
    HEADER_KEY = 'Authorization'
    DATE_FORMAT = DATE_STAMP_FORMAT
    BASIC_ISO_DATE_FORMAT = BASIC_ISO_DATE_STAMP_FORMAT

    uri: str
    headers: dict
    params: dict
    data: char
    method: str
    access_key: str
    secret_access_key: str
    request_time: datetime
    region: str
    service: str

    @property
    def canonical_uri(self) -> str:
        res = urllib.parse.quote(self.uri)
        if not res.startswith('/'):
            res = f'/{res}'
        return res

    @property
    def canonical_querystring(self) -> str:
        return urllib.parse.urlencode(sorted(self.params.items()))

    @property
    def canonical_headers(self) -> str:
        return '\n'.join(f'{self.trim(k.lower())}:{self.trim(v)}' for k, v in sorted(self.headers.items())) + '\n'

    @property
    def signed_headers(self) -> str:
        return ';'.join(k.lower() for k in sorted(self.headers.keys()))

    @property
    def date_stamp(self):
        return self.request_time.strftime(self.DATE_FORMAT)

    @property
    def basic_iso_date_stamp(self):
        return self.request_time.strftime(self.BASIC_ISO_DATE_FORMAT)

    def create_canonical_request(self) -> str:
        canonical_request = '\n'.join([
            self.method,
            self.canonical_uri,
            self.canonical_querystring,
            self.canonical_headers,
            self.signed_headers,
            self.hash_sha256(self.data or '').hex(),
        ])
        return canonical_request

    @classmethod
    def trim(cls, msg: str) -> str:
        msg = msg.strip()
        return re.sub(r'\s{2,}', '', msg)

    def create_string_to_sign(self, canonical_request: str) -> Tuple[str, str]:
        credential_scope = '/'.join([
            self.date_stamp,
            self.region,
            self.service,
            self.TERMINATION_STRING,
        ])
        string_to_sign = '\n'.join([
            self.ALGORITHM,
            self.basic_iso_date_stamp,
            credential_scope,
            self.hash_sha256(canonical_request).hex(),
        ])
        return string_to_sign, credential_scope

    @classmethod
    def hash_sha256(cls, msg: char) -> bytes:
        return cls._hash_sha256(cls.to_bytes(msg))

    @classmethod
    def _hash_sha256(cls, msg: bytes) -> bytes:
        return hashlib.sha256(msg).digest()

    @classmethod
    def to_bytes(cls, msg: char):
        try:
            return msg.encode()
        except AttributeError:
            return msg

    def calculate_signature(self, string_to_sign: str) -> str:
        k_date = self._sign(f'{self.NAME}{self.secret_access_key}', self.date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        k_signing = self._sign(k_service, self.TERMINATION_STRING)
        signature_bytes = self._sign(k_signing, string_to_sign)
        return signature_bytes.hex()

    @classmethod
    def _sign(cls, key: char, msg: char) -> bytes:
        return cls.sign_sha256(key, msg)

    @classmethod
    def sign_sha256(cls, key: char, msg: char) -> bytes:
        return cls._sign_sha256(cls.to_bytes(key), cls.to_bytes(msg))

    @classmethod
    def _sign_sha256(cls, key: bytes, msg: bytes) -> bytes:
        return hmac.new(key, msg, hashlib.sha256).digest()

    def build_auth_headers(self, signature: str, credential_scope: str) -> dict:
        auth_type = self.ALGORITHM
        credentials = ', '.join([
            f'{self.CREDENTIAL_KEYS[0]}={self.access_key}/{credential_scope}',
            f'{self.CREDENTIAL_KEYS[1]}={self.signed_headers}',
            f'{self.CREDENTIAL_KEYS[2]}={signature}'
        ])
        authorization_header = f'{auth_type} {credentials}'
        return {
            self.HEADER_KEY: authorization_header
        }

    def finalize(self) -> dict:
        canonical_request = self.create_canonical_request()
        string_to_sign, credential_scope = self.create_string_to_sign(canonical_request)
        signature = self.calculate_signature(string_to_sign)
        return self.build_auth_headers(signature, credential_scope)


def get_authorization_headers(**kwargs):
    builder = AuthorizationBuilder(**kwargs)
    return builder.finalize()
