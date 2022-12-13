import requests
from werkzeug.urls import url_join

from odoo import _
from odoo.exceptions import UserError
import json

API_BASE_URL = 'https://api.easypost.com/v2/'


class EasypostRequest():
    "Implementation of Easypost API"

    def __init__(self, api_key, debug_logger):
        self.api_key = api_key
        self.debug_logger = debug_logger

    def _make_api_request(self, endpoint, request_type='get', data=None):
        """make an api call, return response"""
        access_url = url_join(API_BASE_URL, endpoint)
        try:
            self.debug_logger("%s\n%s\n%s" % (access_url, request_type, data if data else None), 'easypost_request_%s' % endpoint)
            if request_type == 'get':
                response = requests.get(access_url, auth=(self.api_key, ''), data=data)
            else:
                response = requests.post(access_url, auth=(self.api_key, ''), data=data)
            self.debug_logger("%s\n%s" % (response.status_code, response.text), 'easypost_response_%s' % endpoint)
            response = response.json()
            # check for any error in response
            if 'error' in response:
                raise UserError(_('Easypost returned an error: ') + response['error'].get('message'))
            return response
        except Exception as e:
            raise e

    def verify_address(self, address):
        data = {}
        data['verify'] = ['delivery']
        data['address'] = address
        try:
            response = self._make_api_request(endpoint='addresses', request_type='post', data=json.dumps(data))
            if 'verification' in response and 'delivery' in response['verification']:
                if response['verification']['delivery']['success']:
                    ep_address = {
                        'street1': response['street1'],
                        'street2': response['street2'],
                        'city': response['city'],
                        'state': response['state'],
                        'zip': response['zip'],
                        'country': response['country'],
                        'residential': response['residential']
                    }
                    success = True
                    errors = []
                    for key in address:
                        if address[key].upper() != ep_address[key]:
                            success = False
                            errors = [{'message': "According to EasyPost, your address doesn't appear to be in the correct format!",
                                       'new_address': ep_address}]
                            break

                    return {'success': success,
                            'suggestion': not success,
                            'errors': errors}
                else:
                    return {'success': False, 'errors': response['verification']['delivery']['errors']}
        except Exception as e:
            return {'success': True, 'errors': []}