# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo.addons.channel_base_sdk.utils import bigcommerce_api as bigcommerce

_logger = logging.getLogger(__name__)


class RateLimit(Exception):

    def __init__(self, message):
        if type(message) == str:
            self.message = message
        else:
            self.message = json.dumps(message)

    def __str__(self):
        return self.message


class ExportError(BaseException):

    def __init__(self, message):
        if type(message) == str:
            self.message = message
        else:
            self.message = json.dumps(message)

        if self.message == 'null':
            self.message = "Your request is invalid. Please check your request data and try again!"

    def __str__(self):
        return self.message


class NotFoundError(BaseException):

    def __init__(self, message):
        if type(message) == str:
            self.message = message
        else:
            self.message = json.dumps(message)

    def __str__(self):
        return self.message


class BigCommerceHelper:

    @classmethod
    def connect_with_channel(cls, channel):
        credentials = {
            'store_hash': channel.bc_store_hash,
            'access_token': channel.bc_access_token,
        }
        return cls.connect_with_dict(credentials)

    @classmethod
    def connect_with_dict(cls, credentials):
        """
        :param credentials: Should have this format {
            'store_hash': '2khj4821',
            'access_token': 'f9e21a1945b8fb51bce6fa1595c06405',
        }
        :return: The api object
        """
        return bigcommerce.connect_with(credentials)
