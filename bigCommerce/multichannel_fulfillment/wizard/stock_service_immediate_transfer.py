# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class StockServiceImmediateTransfer(models.TransientModel):
    _name = 'stock.service.immediate.transfer'
    _description = 'Service Immediate Transfer'

    pick_id = fields.Many2one('stock.service.picking')

    def process(self):
        self.ensure_one()
        self.pick_id.with_context(set_all_unset_to_full=True).action_done()
