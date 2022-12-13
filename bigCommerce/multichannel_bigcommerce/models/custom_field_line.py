# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ChannelCustomFieldLine(models.Model):
    _name = 'product.channel.custom.field.line'
    _description = 'Product Channel Custom Field Line'
    _rec_name = 'key'

    product_channel_id = fields.Many2one('product.channel', string='Product Mapping', ondelete='cascade')
    id_on_channel = fields.Char(string='ID on Store', copy=False)
    key = fields.Char(string='Key', required=True)
    value = fields.Char(string='Value')
