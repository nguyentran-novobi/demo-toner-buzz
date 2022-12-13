# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    warehouse_id = fields.Many2one('stock.warehouse', compute='_get_warehouse', store=True)

    @api.depends('location_id')
    def _get_warehouse(self):
        for record in self:
            record.warehouse_id = record.location_id.warehouse_id
