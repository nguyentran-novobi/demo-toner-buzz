# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Pricelist(models.Model):
    _inherit = 'product.pricelist'

    channel_pricelist_ids = fields.One2many('channel.pricelist', 'pricelist_id')
