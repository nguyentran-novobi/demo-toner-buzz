# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    service_move_ids = fields.One2many('stock.service.move', 'sale_line_id', string='Service Moves')

    assigned_service_qty = fields.Float('Assigned Service Quantity', compute='_compute_assigned_service_qty',
                                        help='Total initial demand of this line in service transfers not cancelled.')

    def _compute_assigned_service_qty(self):
        for record in self:
            draft_service_moves = record.service_move_ids.filtered(lambda l: l.state == 'draft')
            done_service_moves = record.service_move_ids.filtered(lambda l: l.state == 'done')
            assigned_draft_service_qty = sum(m.product_uom_id._compute_quantity(m.product_uom_qty, record.product_uom)
                                             for m in draft_service_moves)
            assigned_done_service_qty = sum(m.product_uom_id._compute_quantity(m.quantity_done, record.product_uom)
                                            for m in done_service_moves)
            record.assigned_service_qty = assigned_draft_service_qty + assigned_done_service_qty

    def _get_assigned_service_qty(self):
        self.ensure_one()
        draft_service_moves = self.service_move_ids.filtered(lambda l: l.state == 'draft')
        done_service_moves = self.service_move_ids.filtered(lambda l: l.state == 'done')
        assigned_draft_service_qty = sum(m.product_uom_id._compute_quantity(m.product_uom_qty, self.product_uom)
                                         for m in draft_service_moves)
        assigned_done_service_qty = sum(m.product_uom_id._compute_quantity(m.quantity_done, self.product_uom)
                                        for m in done_service_moves)
        return assigned_draft_service_qty + assigned_done_service_qty

    def calculate_shipped_service_quantity(self):
        for line in self.filtered(lambda r: r.product_id.is_deliverable_service):
            done_moves = line.service_move_ids.filtered(lambda r: r.state == 'done')
            line.qty_delivered = sum(m.product_uom_id._compute_quantity(m.quantity_done, line.product_uom) for m in done_moves)
