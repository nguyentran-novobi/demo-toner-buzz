# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.web.controllers.main import Binary
from odoo import http
from odoo.http import request

class BinaryInherit(Binary):

    @http.route([
        '/channel/image'], type='http', auth="public")
    def channel_content_image(self, xmlid=None, model='ir.attachment', id=None, field='datas',
                      filename_field='name', unique=None, filename=None, mimetype=None,
                      download=None, width=0, height=0, crop=False, access_token=None,
                      **kwargs):
        # other kwargs are ignored on purpose
        return self._sudo_content_image(xmlid=xmlid, model=model, id=id, field=field,
            filename_field=filename_field, unique=unique, filename=filename, mimetype=mimetype,
            download=download, width=width, height=height, crop=crop,
            quality=int(kwargs.get('quality', 0)), access_token=access_token)

    def _sudo_content_image(self, xmlid=None, model='ir.attachment', id=None, field='datas',
                       filename_field='name', unique=None, filename=None, mimetype=None,
                       download=None, width=0, height=0, crop=False, quality=0, access_token=None,
                       placeholder=None, **kwargs):
        status, headers, image_base64 = request.env['ir.http'].sudo().binary_content(
            xmlid=xmlid, model=model, id=id, field=field, unique=unique, filename=filename,
            filename_field=filename_field, download=download, mimetype=mimetype,
            default_mimetype='image/png', access_token=access_token)

        return BinaryInherit._content_image_get_response(
            status, headers, image_base64, model=model, id=id, field=field, download=download,
            width=width, height=height, crop=crop, quality=quality,
            placeholder=placeholder)
