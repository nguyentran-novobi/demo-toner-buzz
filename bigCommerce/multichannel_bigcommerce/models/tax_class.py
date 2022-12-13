# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID, _
import logging
import requests

_logger = logging.getLogger(__name__)

class TaxClass(models.Model):
    _name = "tax.class"
    _description = 'Tax Class on BigCommerce'

    id_on_channel = fields.Char(string='ID on Store', required=True)
    name = fields.Char(string='Name', required=True)
    channel_id = fields.Many2one('ecommerce.channel', string='Store')

    _sql_constraints = [
        ('uniq_tax', 'unique (id_on_channel,channel_id)',
         'This tag already exists on Channel!')
    ]

    @api.model
    def bigcommerce_get_data(self, channel_id, id_on_channel=None):
        """
        :param vals:
        :return:
        """
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        bc_store_hash, headers = channel.bigcommerce_generate_url_header()

        url = "https://api.bigcommerce.com/stores/%s/v2/tax_classes" % bc_store_hash

        if id_on_channel:
            url += '/%s' % id_on_channel

        try:
            response = requests.get(url=url, headers=headers)
            if response.status_code == 200:
                vals = response.json()
                if type(vals) == dict:
                    vals = [vals]
                result = []
                existed_records = self.sudo().search([('channel_id.id', '=', channel_id)])
                existed_ids = existed_records.mapped('id_on_channel')
                for val in vals:
                    if str(val['id']) not in existed_ids:
                        result.append({
                            'id_on_channel': str(val['id']),
                            'name': val['name'],
                            'channel_id': channel_id
                        })

                records = self.sudo().create(result)
                self.env.cr.commit()
                return existed_records + records
        except Exception as e:
            _logger.exception("Error in synching tax from BigCommerce: %s", str(e))
            return self
