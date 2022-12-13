# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, tools, _


class Pricelist(models.Model):
    _inherit = 'product.pricelist'

    channel_id = fields.Many2one('ecommerce.channel', string='Channel')
