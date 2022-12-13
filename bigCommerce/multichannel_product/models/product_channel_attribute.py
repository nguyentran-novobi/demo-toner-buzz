# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductChannelAttribute(models.Model):
    _name = 'product.channel.attribute'
    _description = 'Product Channel Attribute'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    id_on_channel = fields.Char(string='ID on Store', index=True, readonly=True)
    attribute_id = fields.Many2one('product.attribute', string='Attribute', required=True)
