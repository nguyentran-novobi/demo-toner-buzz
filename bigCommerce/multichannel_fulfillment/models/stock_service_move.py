# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError


class StockServiceMove(models.Model):
    _name = "stock.service.move"
    _description = "Stock Service Move"
    _order = 'service_picking_id, id'

    name = fields.Char('Description', index=True, required=True)

    date = fields.Datetime(
        'Date', default=fields.Datetime.now, index=True, required=True,
        states={'done': [('readonly', True)]},
        help="Move date: scheduled date until move is done, then date of actual move processing")
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', '=', 'service')], index=True, required=True,
        states={'done': [('readonly', True)]})
    product_qty = fields.Float(
        'Real Quantity', compute='_compute_product_qty', inverse='_set_product_qty',
        digits=0, store=True, compute_sudo=True,
        help='Quantity in the default UoM of the product')
    product_uom_qty = fields.Float(
        'Initial Demand',
        digits='Product Unit of Measure',
        default=0.0, required=True, states={'done': [('readonly', True)]},
        help="This is the quantity of products from an inventory "
             "point of view. For moves in the state 'done', this is the "
             "quantity of products that were actually moved. For other "
             "moves, this is the quantity of product that is planned to "
             "be moved")
    product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure', required=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product Template',
        related='product_id.product_tmpl_id', readonly=False,
        help="Technical: used in views")

    partner_id = fields.Many2one(
        'res.partner', 'Destination Address',
        states={'done': [('readonly', True)]},
        help="Optional address where goods are to be delivered, specifically used for allotment")

    sale_line_id = fields.Many2one('sale.order.line', 'Sale Line', index=True)
    service_picking_id = fields.Many2one('stock.service.picking', 'Transfer Reference',
                                         index=True, states={'done': [('readonly', True)]})
    service_picking_partner_id = fields.Many2one('res.partner', 'Transfer Destination Address',
                                                 related='service_picking_id.partner_id', readonly=False)

    state = fields.Selection([
        ('draft', 'New'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], string='Status',
        copy=False, default='draft', index=True, readonly=True,
        help="* New: When the stock move is created and not yet confirmed.\n"
             "* Done: When the shipment is processed, the state is 'Done'.\n"
             "* Canceled: When the shipment is canceled")

    origin = fields.Char("Source Document")

    quantity_done = fields.Float('Quantity Done', digits='Product Unit of Measure')

    product_type = fields.Selection(related='product_id.type', readonly=True)

    reference = fields.Char(compute='_compute_reference', string="Reference", store=True)

    @api.depends('service_picking_id', 'name')
    def _compute_reference(self):
        for move in self:
            move.reference = move.service_picking_id.name if move.service_picking_id else move.name

    @api.depends('product_id', 'product_uom_id', 'product_uom_qty')
    def _compute_product_qty(self):
        rounding_method = self._context.get('rounding_method', 'UP')
        for record in self:
            record.product_qty = record.product_uom_id._compute_quantity(
                record.product_uom_qty, record.product_id.uom_id, rounding_method=rounding_method)

    def _action_confirm(self):
        return self._assign_picking()

    def _get_new_picking_values(self):
        return {
            'origin': self.origin,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'sale_id': self.sale_line_id.order_id.id
        }

    def _search_picking_for_assignation(self):
        self.ensure_one()
        picking = self.env['stock.service.picking'].search([
                ('origin', '=', self.origin),
                ('state', 'in', ['draft', 'assigned'])], limit=1)
        return picking or False

    def _assign_picking(self):
        Picking = self.env['stock.service.picking']
        for move in self:
            picking = move._search_picking_for_assignation()
            if not picking:
                picking = Picking.with_context(check_empty_line=False).create(move._get_new_picking_values())
            move.write({'service_picking_id': picking.id, 'state': 'draft'})
        return True

    @api.model
    def _get_stock_move_values(self, sale_line_id):
        return {
            'name': sale_line_id.product_id.name[:2000],
            'company_id': sale_line_id.company_id.id,
            'product_id': sale_line_id.product_id.id,
            'product_uom_id': sale_line_id.product_id.uom_id.id,
            'product_uom_qty': max(sale_line_id.product_qty - sale_line_id._get_assigned_service_qty(), 0.0),
            'partner_id': sale_line_id.order_id.partner_shipping_id.id or False,
            'origin': sale_line_id.order_id.name,
            'date': sale_line_id.order_id.expected_date,
            'sale_line_id': sale_line_id.id,
            'quantity_done': 0.0,
        }

    def action_done(self):
        set_full = bool(self.env.context.get('set_all_unset_to_full'))
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for record in self.filtered(lambda r: r.state == 'draft'):
            if float_compare(record.quantity_done, 0, precision_digits=precision) < 0:
                raise UserError(_('Invalid Done Quantity!'))
            vals = dict(state='done', date=fields.Datetime.now())
            if float_is_zero(record.quantity_done, precision_digits=record.product_uom_id.rounding):
                if set_full:
                    vals.update(dict(quantity_done=record.product_uom_qty))
                else:
                    vals.update(dict(state='cancel'))
            record.update(vals)

    def action_cancel(self):
        self.filtered(lambda m: m.state != 'cancel').update(dict(state='cancel'))
