# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def write(self, vals):
        res = super(StockMoveLine, self).write(vals)
        self.notify_line_changed()
        return res

    def notify_line_changed(self):
        self.mapped('picking_id').mark_line_changed()
