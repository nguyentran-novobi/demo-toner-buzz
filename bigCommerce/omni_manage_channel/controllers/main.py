from odoo import http
from odoo.http import request
import requests
import logging
import json
import base64
import hashlib
import hmac
import werkzeug
from odoo.addons.web.controllers.main import Home, login_and_redirect, CONTENT_MAXAGE
from odoo.tools import ustr

_logger = logging.getLogger(__name__)


OB_SECRETKEY = 'I8D32XcuVhynw2MgC212wFe5lV3Dzwcma'

APPS = ['account_accountant', 'crm', 'mass_mailing',
        'helpdesk', 'purchase', 'point_of_sale', 'sale_subscription',
        'sale_renting', 'social_sale', 'mrp', 'sign', 'website']

class Main(http.Controller):

    @http.route(['/omniborder/connect'], type='json', auth='public', csrf=False)
    def omniborder_connect(self, **kwargs):
        payload = json.loads(request.httprequest.get_data().decode(request.httprequest.charset))
        logging.warning(payload)
        ICP = request.env['ir.config_parameter'].sudo()
        ICP.set_param("web.base.url", payload['base_url'])
        try:
            ICP.create({'key': 'web.base.url.freeze',
                        'value': 'True'})
        except Exception:
            pass
        request.env.cr.commit()
        return True

    @http.route('/omniborder/install_apps', auth='public', type='json')
    def omniborder_install_apps(self, **kwargs):
        payload = json.loads(request.httprequest.get_data().decode(request.httprequest.charset))
        try:
            module = request.env['ir.module.module'].sudo().search([('name', '=', payload.get('app'))])
            if module:
                module.with_context(prefetch_fields=False).with_user(1).button_immediate_install()
            return {'success': True}
        except Exception as e:
            _logger.exception("Can't install apps")
            _logger.info(payload)
            return {'error': e}

    def verify_signed_request(self, signed_payload):
        """
        Used for verifying load callback request
        :param signed_payload:
        :param client_secret:
        :return:
        """

        message_parts = signed_payload.split(".")
        encoded_json_payload = message_parts[0]
        encoded_hmac_signature = message_parts[1]
        decode_payload = base64.urlsafe_b64decode(encoded_json_payload.encode("utf-8"))
        expected_signature = hmac.new(OB_SECRETKEY.encode("utf-8"), decode_payload, 'sha256').hexdigest()
        provided_signature = base64.urlsafe_b64decode(encoded_hmac_signature.encode("utf-8"))

        if hmac.compare_digest(expected_signature.encode("utf-8"), provided_signature):
            return json.loads(decode_payload.decode("utf-8"))
        return None

    @http.route(['/ob/login'], type='http', auth='public', csrf=False)
    def ob_login(self, signed_payload, set_up=None):
        payload_object = self.verify_signed_request(signed_payload)
        if payload_object:
            menu = request.env.ref('omni_manage_channel.menu_multichannel_root')
            action = request.env.ref('omni_manage_channel.action_client_onboarding')

            user = request.env['res.users'].sudo().browse(2)
            url = '/web'
            ir_params_sudo = request.env['ir.config_parameter'].sudo()
            is_set_up = True if ir_params_sudo.get_param('ob_set_up_state') == 'True' else False
            if is_set_up and payload_object.get('channel_id', False):
                ir_params_sudo.set_param('ob_set_up_state', 'False')
                url = '/web#id={channel_id}&action={action}&menu_id={menu_id}'.format(channel_id=int(payload_object['channel_id']),
                                                                                      action=action.id,
                                                                                      menu_id=menu.id)
            resp = login_and_redirect(request.session.db,
                                      user.login,
                                      OB_SECRETKEY, url)
            resp.set_cookie(
                'session_id', request.httprequest.session.sid, max_age=90 * 24 * 60 * 60, httponly=True)
            return resp
        return werkzeug.wrappers.Response(status=400)