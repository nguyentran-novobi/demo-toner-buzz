# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError, ValidationError

from odoo.addons.omni_manage_channel.models.customer_channel import compare_address


class ServicePicking(models.Model):
    _name = "stock.service.picking"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transfer"
    _order = "date desc, id desc"

    name = fields.Char(
        'Reference', default='Draft',
        copy=False, index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    sale_id = fields.Many2one('sale.order', string='Sale Order')

    origin = fields.Char(
        'Source Document', index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Reference of the document")
    note = fields.Text('Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], string='Status', compute='_compute_state', store=True,
        copy=False, index=True,
        help=" * Draft: not confirmed yet and will not be scheduled until confirmed.\n"
             " * Done: has been processed, can't be modified or cancelled anymore.\n"
             " * Canceled: has been cancelled, can't be confirmed anymore.")

    date = fields.Datetime(
        'Creation Date',
        default=fields.Datetime.now, index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Creation Date, usually the time of the order")
    date_done = fields.Datetime('Date of Transfer', copy=False, readonly=True,
                                help="Date at which the transfer has been processed or cancelled.")

    move_lines = fields.One2many('stock.service.move', 'service_picking_id', string="Stock Service Moves", copy=True)

    partner_id = fields.Many2one(
        'res.partner', 'Partner',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    id_on_channel = fields.Char(string='ID on Channel', copy=False)

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per company!'),
    ]

    @api.depends('move_lines.state', 'move_lines.service_picking_id')
    def _compute_state(self):
        """ State of a picking depends on the state of its related stock.move
        - Draft: only used for "planned pickings"
        - Done: if the picking is done.
        - Canceled: if the picking is cancelled
        """
        for record in self:
            if not record.move_lines:
                record.state = 'draft'
            elif all(move.state == 'cancel' for move in record.move_lines):
                record.state = 'cancel'
            elif all(move.state in ['cancel', 'done'] for move in record.move_lines):
                record.state = 'done'
            else:
                record.state = 'draft'

    @api.model
    def create(self, vals):
        if 'name' not in vals:
            ref_num = self.env.ref('multichannel_fulfillment.sequence_service_picking').next_by_id()
            vals['name'] = 'SS{}'.format(ref_num)
        res = super(ServicePicking, self).create(vals)
        if not res.move_lines and self.env.context.get('check_empty_line', True):
            raise UserError(_('No items to add.'))
        return res

    def unlink(self):
        self.mapped('move_lines').action_cancel()
        self.mapped('move_lines').unlink()  # Checks if moves are not done
        return super(ServicePicking, self).unlink()

    def action_confirm(self):
        self.ensure_one()
        if not self.move_lines:
            raise UserError(_('No items to add.'))

        precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        no_quantities_done = all(float_is_zero(move_line.quantity_done, precision_digits=precision_digits) for move_line in
                                 self.move_lines.filtered(lambda m: m.state == 'draft'))
        no_reserved_quantities = all(
            float_is_zero(move_line.product_qty, precision_digits=move_line.product_uom_id.rounding) for move_line in self.move_lines)

        if no_reserved_quantities:
            raise UserError(_('No items to add.'))

        if no_quantities_done:
            wiz = self.env['stock.service.immediate.transfer'].create({'pick_id': self.id})
            return {
                'name': _('Immediate Transfer?'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.service.immediate.transfer',
                'views': [(False, 'form')],
                'view_id': False,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }
        self.action_done()

        service_lines = self.sale_id.order_line.filtered(lambda r: r.product_id.is_deliverable_service)
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        if any(float_compare(l._get_assigned_service_qty(), l.product_qty, precision_digits=precision) < 0 for l in service_lines):
            self.with_context(link_sale_id=self.sale_id.id).create({})

        return True

    def action_done(self):
        self.mapped('move_lines').filtered(lambda m: m.state == 'draft').action_done()
        self.mapped('move_lines').mapped('sale_line_id').calculate_shipped_service_quantity()

        for record in self:
            if 'for_synching' not in self.env.context and record.sale_id.channel_id.platform:
                record.with_delay(eta=5)._post_shipment_to_channel()
            # Automatically action done on order when that order is fully shipped
            if record.sale_id.shipping_status == 'shipped':
                record.sale_id.action_done()

    def action_cancel(self):
        if self.env.context.get('skip_done_service_transfers', False):
            self.mapped('move_lines').filtered(lambda m: m.state not in ('done', 'cancel')).action_cancel()
        else:
            self.mapped('move_lines').filtered(lambda m: m.state != 'cancel').action_cancel()
        self.mapped('move_lines').mapped('sale_line_id').calculate_shipped_service_quantity()

    @api.model
    def default_get(self, field_list):
        default = super(ServicePicking, self).default_get(field_list)
        if 'link_sale_id' in self.env.context:
            sale_order = self.env['sale.order'].browse(int(self.env.context['link_sale_id']))
            val_list = sale_order.order_line._generate_service_move_values()
            vals = {
                'origin': sale_order.name,
                'company_id': sale_order.company_id.id,
                'partner_id': sale_order.partner_shipping_id.id,
                'sale_id': sale_order.id,
                'move_lines': [(0, 0, v) for v in val_list]
            }
            default.update(vals)
        return default

    @api.model
    def process_shipment_data_from_channel(self, order_id, shipment_datas, channel):
        """
        Processing response from channel for shipment
        :param order_id: Odoo sale.order object, the order created the shipments
        :param shipment_datas: a list of order shipments on channel for that order
                Each element in list has to be included
                'id_on_channel'
                'shipping_address'
                'carrier_tracking_ref'
                'merchant_shipping_cost'
                'requested_carrier'
                'tracking_url'
                'note'
                'items': A list of items with 'order_line_id_on_channel' and 'quantity'
        :return:
        """
        synced_shipments = order_id.service_picking_ids.mapped('id_on_channel')
        shipments = list(filter(lambda s: s['id_on_channel'] not in synced_shipments, shipment_datas))
        if shipments and order_id.warehouse_id.delivery_steps != 'ship_only':
            raise ValidationError(_('Cannot import shipment. Multiple steps delivery is not supported.'))
        for shipment in shipments:
            picking = order_id.service_picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            if picking:
                picking = picking[0].with_context(for_synching=True)
            else:
                break
            move_lines = picking.move_lines
            if not move_lines:
                break
            for item in shipment['items']:
                # Seek stock move lines for order line
                order_line = picking.sale_id.order_line.filtered(
                    lambda l: l.id_on_channel == item['order_line_id_on_channel'])
                lines = move_lines.filtered(lambda l: l.product_id.id == order_line.product_id.id).sorted(
                    'product_qty')
                # In some cases, we have some stock move lines with the same product.
                # Allocate quantity of that product on shipment to all lines contains that product
                remaining_qty = item['quantity']
                for index, move_line in enumerate(lines):
                    if remaining_qty == 0:
                        break
                    product_uom_qty = move_line.product_uom_qty
                    if move_line.product_qty < remaining_qty:
                        qty_done = move_line.product_qty
                        if index == len(lines) - 1:
                            qty_done = remaining_qty
                            product_uom_qty = remaining_qty
                        remaining_qty = remaining_qty - qty_done
                    else:
                        qty_done = remaining_qty
                        remaining_qty = 0
                    move_line.write({'quantity_done': qty_done, 'product_uom_qty': product_uom_qty})
            shipping_address = shipment.get('shipping_address')
            shipping_address_id = picking.sale_id.partner_shipping_id.id
            if shipping_address:
                # Update shipping address
                country = self.env['res.country'].sudo().search([('code', '=ilike', shipping_address['country_iso2'])],
                                                                limit=1)
                country_id = country.id

                state_id = self.env['res.country.state'].sudo().search(
                    [('country_id.code', '=', shipping_address['country_iso2']),
                     ('name', '=', shipping_address['state'])], limit=1).id

                name = '%s %s' % (shipping_address['first_name'], shipping_address['last_name'])

                shipping_address_record = picking.sale_id.partner_id.child_ids.filtered(
                    lambda r: (r.type == 'invoice' and compare_address(
                        r,
                        {**shipping_address, **dict(name=name, country_id=country_id, state_id=state_id)},
                        country.code)))

                if shipping_address_record:
                    shipping_address_id = shipping_address_record[0].id
                else:
                    shipping_address_id = self.env['res.partner'].sudo().create({'name': name,
                                                                                 'email': shipping_address['email'],
                                                                                 'phone': shipping_address['phone'],
                                                                                 'street': shipping_address['street_1'],
                                                                                 'street2': shipping_address['street_2'],
                                                                                 'city': shipping_address['city'],
                                                                                 'zip': shipping_address['zip'],
                                                                                 'country_id': country_id,
                                                                                 'state_id': state_id,
                                                                                 'parent_id': picking.sale_id.partner_id.id,
                                                                                 'type': 'delivery'}).id
                    self.env.cr.commit()

            # Done picking after assigned qty_done
            picking.sudo().write({
                'partner_id': shipping_address_id,
                'id_on_channel': shipment['id_on_channel'],
            })
            picking.action_confirm()

    def _post_shipment_to_channel(self):
        for record in self:
            cust_method_name = '%s_post_record' % record.sale_id.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    def _put_shipment_to_channel(self, data):
        for record in self:
            cust_method_name = '%s_put_record' % record.sale_id.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)(data)

    @api.model
    def _log_exceptions_on_picking(self, title, exceptions):
        """
        Log exceptions on chatter
        :param exceptions: list of exceptions
        Each exception will include
        - title
        - reason
        :return:
        """
        render_context = {
            'origin_picking': self,
            'exceptions': exceptions,
            'title': title
        }
        self._activity_schedule_with_view(
            'mail.mail_activity_data_warning',
            user_id=self.env.user.id,
            views_or_xmlid='multichannel_fulfillment.exception_on_picking',
            render_context=render_context
        )
