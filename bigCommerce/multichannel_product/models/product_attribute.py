# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    is_visible = fields.Boolean(readonly=True)

    @api.model
    def create(self, vals):
        if 'position' in vals:
            del vals['position']
        return super(ProductTemplateAttributeLine, self).create(vals)

    def write(self, vals):
        if 'position' in vals:
            del vals['position']
        return super(ProductTemplateAttributeLine, self).write(vals)


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    channel_attribute_ids = fields.One2many('product.channel.attribute', 'attribute_id', string='Channel Attributes')

    @api.model
    def create_attribute_line(self, attribute_name, data):
        is_visible = True
        channel_id = None
        id_on_channel = None
        if isinstance(data, dict):
            is_visible = data['is_visible']
            channel_id = data.get('channel_id')
            id_on_channel = data.get('id_on_channel')
            data = data['options']

        attribute = self.sudo().search([('name', '=', attribute_name)], limit=1)
        value_ids = []
        if not attribute:
            val = {
                'name': attribute_name,
            }
            if channel_id and id_on_channel:
                val.update({
                    'channel_attribute_ids': [(0, 0, {
                        'channel_id': channel_id,
                        'id_on_channel': id_on_channel,
                    })]
                })
            attribute = self.sudo().create(val)
        else:
            if channel_id and id_on_channel:
                att = attribute.channel_attribute_ids.filtered(lambda a: a.channel_id.id == channel_id
                                                                         and a.id_on_channel == id_on_channel)
                if not att:
                    attribute.sudo().update({
                        'channel_attribute_ids': [(0, 0, {
                            'channel_id': channel_id,
                            'id_on_channel': id_on_channel,
                        })]
                    })

        available_values = attribute.value_ids.mapped('name')
        new_values = list(filter(lambda e: e not in available_values, data))
        existed_values = attribute.value_ids.filtered(lambda e: e.name in data)
        if existed_values:
            value_ids.extend(existed_values.mapped('id'))
        if new_values:
            value_list = [{'name': e, 'attribute_id': attribute.id} for e in new_values]
            value_ids.extend(self.env['product.attribute.value'].sudo().create(value_list).mapped('id'))

        return (0, 0, {'attribute_id': attribute.id,
                       'value_ids': [(6, 0, value_ids)],
                       'is_visible': is_visible})
