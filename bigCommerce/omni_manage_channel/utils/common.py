# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import base64
import requests


class ImageUtils:
    ERROR_MSG = 'Could not get image content'

    engine = requests

    @classmethod
    def get_safe_image_b64(cls, image_url_or_image):
        try:
            return cls.get_image_b64(image_url_or_image)
        except ValueError:
            return None

    @classmethod
    def get_image_b64(cls, image_url_or_image):
        """
        Check whether the input is an URL or image content
        Fetch image content if is is an URL
        Always return the image content (in b64 encoded)
        """
        if image_url_or_image:
            if cls.is_image(image_url_or_image):
                return image_url_or_image
            else:
                return cls.try_getting_get_image_b64_from_url(image_url_or_image)
        else:
            raise ValueError(cls.ERROR_MSG)

    @classmethod
    def is_image(cls, raw_data):
        """
        Whether the ``raw_data`` is image
        """
        return cls.is_binary(raw_data)

    @classmethod
    def is_binary(cls, raw_data):
        """
        Whether the ``raw_data`` is a binary
        """
        try:
            raw_data.decode()
            return True
        except (UnicodeDecodeError, AttributeError):
            return False

    @classmethod
    def try_getting_get_image_b64_from_url(cls, url):
        try:
            return cls.get_image_b64_from_url(url)
        except (ValueError, IOError) as ex:
            raise ValueError(cls.ERROR_MSG) from ex

    @classmethod
    def get_image_b64_from_url(cls, url):
        content = cls.get_image_content_from_url(url)
        return base64.b64encode(content)

    @classmethod
    def get_image_content_from_url(cls, url):
        response = cls.engine.get(url)
        if response.ok:
            return response.content
        response.raise_for_status()


class AddressUtils:
    @classmethod
    def get_country_state_record(cls, env, country_code, state_code):
        country = cls.get_country_record(env, country_code)
        state = cls.get_state_record(env, country, state_code)
        return country, state

    @classmethod
    def get_country_record(cls, env, country_code):
        return env['res.country'].sudo().search([('code', '=ilike', country_code)], limit=1)

    @classmethod
    def get_state_record(cls, env, country, state_code):
        state = env['res.country.state'].sudo().search([
            ('code', '=', state_code),
            ('country_id', '=', country.id)
        ], limit=1)
        return state

    @classmethod
    def get_state_record_by_code_or_name(cls, env, country, state_code, state_name):
        state = env['res.country.state'].sudo().search([
            '|', ('code', '=', state_code), ('name', '=ilike', state_name),
            ('country_id', '=', country.id),
        ], limit=1)
        return state
