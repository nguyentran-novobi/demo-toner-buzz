from odoo import http
from odoo.http import request, Response
import requests
import logging
import json
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)

class MainController(http.Controller):

    @http.route(['/bigcommerce/disconnected'], type='json', auth='public')
    def disconnected(self, **kw):
        try:
            payload = json.loads(request.httprequest.get_data().decode(request.httprequest.charset))
            token = payload['token']
            record = request.env['ecommerce.channel'].sudo().search([('bc_access_token', '=', token)], limit=1)
            if record:
                record.sudo().disconnect()
                return True
            return False
        except Exception:
            return False

    def _bigcommerce_get_store_info(self, bc_store_hash, headers):
        end_point = 'https://api.bigcommerce.com/stores/%s/v2/store' % bc_store_hash

        response = requests.get(url=end_point, headers=headers)
        weight_unit = 'oz'
        dimension_unit = 'in'
        if response.status_code == 200:
            json_response = response.json()
            weight_units = json_response['weight_units']
            dimension_units = json_response['dimension_units']

            if weight_units == 'Pounds':
                weight_unit = 'lb'
            elif weight_units == 'Kilograms':
                weight_unit = 'kg'
            elif weight_units == 'Grams':
                weight_unit = 'g'
            elif weight_units == 'Tonnes':
                weight_unit = 't'

            if dimension_units == 'Centimeters':
                dimension_unit = 'cm'

        return weight_unit, dimension_unit

    @http.route(['/bigcommerce/connected'], type='json', auth='public')
    def connected(self, **kw):
        ir_params_sudo = request.env['ir.config_parameter'].sudo()
        payload = json.loads(request.httprequest.get_data().decode(request.httprequest.charset))
        image = False
        if payload['logo']:
            buffered = BytesIO(requests.get(payload['logo']).content)
            image = base64.b64encode(buffered.getvalue())

        app_client_id = ir_params_sudo.get_param('bigcommerce.app_client_id')

        new_channel = request.env['ecommerce.channel'].sudo().create({
            'name': payload['business_name'],
            'platform': 'bigcommerce',
            'bc_access_token': payload['bc_access_token'],
            'bc_store_hash': payload['bc_store_hash'],
            'image': image,
            'active': True,
            'app_client_id': app_client_id
        })

        request.env.cr.commit()

        return {
            'channel_id': new_channel.id
        }

    @http.route(['/bigcommerce/test'], type='json', auth='public')
    def bigcommerce_test(self, **kw):
        _logger.info("Test")
        payload = json.loads(request.httprequest.get_data().decode(request.httprequest.charset))
        channel_id = payload.get('channel_id')
        channel = request.env['ecommerce.channel'].sudo().browse(int(channel_id))
        models = payload.get('models')
        for m in models:
            channel.get_data(m)