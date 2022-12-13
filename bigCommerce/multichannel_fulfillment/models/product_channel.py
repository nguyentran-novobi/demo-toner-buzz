# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductChannel(models.Model):
    _inherit = 'product.channel'

    is_enable_inventory_sync = fields.Boolean(related='channel_id.is_enable_inventory_sync')
    free_qty = fields.Float(string='Available', compute='_compute_free_qty')

    def _compute_free_qty(self):
        for record in self:
            record.free_qty = sum(
                record.mapped('product_variant_ids.free_qty')
            )
