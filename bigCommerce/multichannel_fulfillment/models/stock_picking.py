# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from itertools import groupby

from odoo import api, fields, models, _
from odoo.addons.omni_manage_channel.models.customer_channel import compare_address
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = 'stock.picking'

    shipping_date = fields.Date(string='Ship Date', copy=False)
    requested_carrier = fields.Char(string='Requested Service', copy=False)
    id_on_channel = fields.Char(string='ID on Channel', copy=False)
    move_line_changed_at = fields.Datetime(default=fields.Datetime.now, copy=False)
    shipping_info_changed_at = fields.Datetime(default=fields.Datetime.now, copy=False)
    channel_synching_at = fields.Datetime(copy=False)
    is_update_to_channel_needed = fields.Boolean(compute='_compute_is_update_to_channel_needed')
    carrier_name = fields.Char(
        string='Carrier',
        help='Used in storing carrier when shipment is created from channel',
        copy=False,
    )
    display_carrier_info = fields.Char(string='Carrier', compute='_get_carrier_info')

    def _get_carrier_info(self):
        for record in self:
            record.display_carrier_info = record.carrier_id.name or record.carrier_name

    def _compute_is_update_to_channel_needed(self):
        for record in self:
            is_outgoing = record.picking_type_code == 'outgoing'
            is_channel_set = record.sale_id.channel_id.platform not in (False, )
            is_on_channel = record.id_on_channel
            has_changes = record._has_changes_need_updating_to_channel()

            record.is_update_to_channel_needed = all([
                is_outgoing,
                is_channel_set,
                is_on_channel,
                has_changes,
            ])

    def _has_changes_need_updating_to_channel(self):
        self.ensure_one()
        res = self._is_move_line_changed()
        return res or self._is_shipping_info_changed()

    def _is_move_line_changed(self):
        self.ensure_one()
        synching_datetime = self.channel_synching_at or datetime.max
        is_changed = self.move_line_changed_at > synching_datetime
        return is_changed

    def _is_shipping_info_changed(self):
        self.ensure_one()
        synching_datetime = self.channel_synching_at or datetime.max
        is_changed = self.shipping_info_changed_at > synching_datetime
        return is_changed

    def write(self, vals):
        res = super(Picking, self).write(vals)
        self.mark_shipping_info_changed_if_applicable(vals)
        return res

    def mark_shipping_info_changed_if_applicable(self, values):
        if any(f in values for f in ('carrier_id', 'carrier_name', 'carrier_tracking_ref')):
            self.mark_shipping_info_changed()

    def mark_shipping_info_changed(self):
        self.update({'shipping_info_changed_at': fields.Datetime.now()})

    def _prepare_shipment_info(self, shipping_address_id, update_move_lines, shipment):
        vals = {
            'partner_id': shipping_address_id,
            'carrier_tracking_ref': shipment['carrier_tracking_ref'],
            'note': shipment.get('note', ''),
            'move_lines': update_move_lines,
            'shipping_date': shipment['shipping_date'],
            'carrier_name': shipment.get('merchant_shipping_carrier')
        }
        # Sometimes, shipment is created by external tool. So, we don't have this information to update to Odoo
        if 'id_on_channel' in shipment:
            vals['id_on_channel'] = shipment['id_on_channel']
        return vals

    def update_shipment_info(self, shipping_address_id, update_move_lines, shipment):
        self.ensure_one()
        vals = self._prepare_shipment_info(shipping_address_id, update_move_lines, shipment)
        self.sudo().with_context(for_synching=True).write(vals)
        self.sudo().with_context(for_synching=True)._action_done()
        self.mark_synced_with_channel()

    def get_shipping_provider(self, display=False):
        self.ensure_one()
        if display:
            providers_dict = dict(self.carrier_id._fields['delivery_type'].selection)
            return providers_dict.get(self.carrier_id.delivery_type) or ''
        return self.carrier_id.delivery_type or ''

    def _get_matching_picking_for_importing(self, shipment_data, states):
        picking = self.filtered(lambda p: (p.id_on_channel == shipment_data['id_on_channel'] and p.state in states))
        return picking

    def _prepare_clear_data_for_cancel_shipment(self):
        update_move_lines = []
        for line in self.move_lines:
            update_move_lines.append((1, line.id, {'quantity_done': 0}))
        return {
            'id_on_channel': False,
            'carrier_id': False,
            'carrier_tracking_ref': False,
            'merchant_shipping_carrier': False,
            'shipping_date': False,
            'tracking_url': False,
            'move_lines': update_move_lines
        }

    @api.model
    def _process_cancel_shipment_data_from_channel(self, order, cancel_shipments):
        for cancel_shipment in cancel_shipments:
            picking = order.picking_ids._get_matching_picking_for_importing(cancel_shipment, ['done'])
            if picking:
                context = self.env.context
                picking = picking[0].with_context(**{**context, **dict(for_synching=True)})

                picking.action_toggle_is_locked()
                vals = picking._prepare_clear_data_for_cancel_shipment()
                picking.write(vals)
                picking.action_toggle_is_locked()
                picking.mark_synced_with_channel(message=f'Shipment was cancelled on {order.channel_id.name}')

    @api.model
    def _process_update_shipment_data_from_channel(self, order, updated_shipments):
        for updated_shipment in updated_shipments:
            picking = order.picking_ids._get_matching_picking_for_importing(updated_shipment, ['assigned', 'done'])
            if picking and picking.carrier_tracking_ref != updated_shipment['carrier_tracking_ref']:
                picking.sudo().write({
                    'carrier_tracking_ref': updated_shipment['carrier_tracking_ref'],
                    'shipping_date': updated_shipment['shipping_date'],
                })
                picking.mark_synced_with_channel()

    def _get_matching_order_line_for_importing(self, item_data):
        order_line = self.sale_id.order_line.filtered(lambda l: l.id_on_channel == item_data['order_line_id_on_channel'])
        return order_line

    @api.model
    def _get_new_shipments_for_importing(self, order, shipment_datas):
        synced_shipments = order.picking_ids.mapped('id_on_channel')
        new_shipments = list(filter(lambda s: s['id_on_channel'] not in synced_shipments, shipment_datas))
        return new_shipments

    @api.model
    def process_shipment_data_from_channel(self, order, shipment_datas, channel):
        """
        Processing response from channel for shipment
        :param order: Odoo sale.order object, the order created the shipments
        :param shipment_datas: a list of order shipments on channel for that order
                Each element in list has to be included
                'id_on_channel'
                'shipping_address'
                'carrier_tracking_ref'
                'merchant_shipping_carrier'
                'merchant_shipping_cost'
                'requested_carrier'
                'tracking_url'
                'note'
                'items': A list of items with 'order_line_id_on_channel' and 'quantity',
                'shipping_date'
        :return:
        """
        new_shipments = self._get_new_shipments_for_importing(order, shipment_datas) if shipment_datas else []
        if new_shipments and order.warehouse_id.delivery_steps != 'ship_only':
            raise ValidationError(_('Cannot import shipment. Multiple steps delivery is not supported.'))
        if new_shipments:
            order.with_context(for_synching=True).action_unlock()
            order.re_create_physical_transfer()
        context = self.env.context
        for shipment in new_shipments:
            picking = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            if picking:
                picking = picking[0].with_context(**{**context, **dict(for_synching=True)})
            else:
                raise ValidationError(_('Cannot create shipment in Odoo.'))
            update_move_lines = []
            move_lines = picking.move_lines
            if not move_lines:
                break
            for item in shipment['items']:
                # Seek stock move lines for order line
                order_line = picking._get_matching_order_line_for_importing(item)
                lines = move_lines.filtered(lambda l: l.product_id.id == order_line.product_id.id).sorted(
                    'product_qty')
                # In some cases, we have some stock move lines with the same product.
                # Allocate quantity of that product on shipment to all lines contains that product
                remaining_qty = item['quantity']
                for index, move_line in enumerate(lines):
                    if remaining_qty == 0:
                        break
                    if move_line.product_qty < remaining_qty:
                        qty_done = move_line.product_qty
                        if index == len(lines) - 1:
                            qty_done = remaining_qty
                        remaining_qty = remaining_qty - qty_done
                    else:
                        qty_done = remaining_qty
                        remaining_qty = 0
                    update_move_lines.append((1, move_line.id, {'quantity_done': qty_done}))

            shipping_address = shipment.get('shipping_address', {})
            shipping_address_id = picking.sale_id.partner_shipping_id.id
            if shipping_address:
                # Update shipping address
                country = self.env['res.country'].sudo().search([('code', '=ilike', shipping_address['country_iso2'])],
                                                                limit=1)
                country_id = country.id

                state_id = self.env['res.country.state'].sudo().search(
                    [('country_id.code', '=ilike', shipping_address['country_iso2']),
                     '|', ('name', '=', shipping_address['state']), ('code', '=', shipping_address['state'])], limit=1).id

                name = '%s %s' % (shipping_address['first_name'], shipping_address['last_name']) if 'first_name' in shipping_address else shipping_address['name']

                shipping_address_record = picking.sale_id.partner_id.child_ids.filtered(
                    lambda r: (r.type == 'delivery' and compare_address(
                        r, {**shipping_address, **dict(name=name, country_id=country_id, state_id=state_id)},
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

            picking.update_shipment_info(shipping_address_id, update_move_lines, shipment)

    def _action_done(self):
        res = super(Picking, self)._action_done()

        for picking in self.filtered(lambda r: r.picking_type_code == 'outgoing'):
            if picking.sale_id.channel_id and picking.sale_id.channel_id.platform \
                    and 'for_synching' not in self.env.context:
                # Check whether this order was fully shipping or not
                picking.filtered(lambda sp: not sp.sale_id.has_been_shipped()).\
                    with_delay(eta=5)._post_shipment_to_channel()

            # Automatically action done on order when that order is fully shipped
            if picking.sale_id.shipping_status == 'shipped':
                picking.sale_id.action_done()
        return res

    @api.model
    def _prepare_exported_shipment_items(self, moves):
        shipment_items = []
        exported_items = {}
        for move in moves:
            if move.sale_line_id.id_on_channel:
                shipment_items.append({
                    'order_item_id': move.sale_line_id.id_on_channel,
                    'quantity': move.product_qty
                })
                exported_items[move.product_id] = exported_items.get(move.product_id, 0) + move.product_qty
        return shipment_items, exported_items

    def _log_exported_shipment_items(self, exported_items):
        not_sync_products = []

        # Track unexported items
        for product, lines in groupby(self.move_line_ids.sorted(key=lambda r: r.product_id.id), key=lambda r: r.product_id):
            move_lines = self.env['stock.move.line'].concat(*list(lines))
            total_qty_done = sum(move_lines.mapped('qty_done'))
            if product not in exported_items:
                not_sync_products.append((product, total_qty_done))
            elif total_qty_done > exported_items[product]:
                not_sync_products.append((product, total_qty_done - exported_items[product]))

        # Log products which cannot be synced to the channel
        if not_sync_products:
            not_sync_product_lis = ''.join([f'<li>{e[0].name}</li>' for e in not_sync_products])
            self.message_post(body=f'<div>WARNING: Extra line(s) found:</div><ul>{not_sync_product_lis}</ul>'
                                f'<div>The syncing process will continue without the mentioned product(s).</div>')
                

    def _post_shipment_to_channel(self):
        self = self.sudo()
        for record in self.filtered(lambda r: r.sale_id.channel_id.auto_export_shipment_to_store):
            cust_method_name = '%s_post_record' % record.sale_id.channel_id.platform
            if hasattr(self, cust_method_name):
                shipment_items, exported_items = self._prepare_exported_shipment_items(self.move_lines)
                getattr(record, cust_method_name)(shipment_items)
                self._log_exported_shipment_items(exported_items)

    def _put_shipment_to_channel(self, update_items=False):
        self = self.sudo()
        for record in self.filtered(lambda r: r.sale_id.channel_id.auto_export_shipment_to_store):
            cust_method_name = '%s_put_record' % record.sale_id.channel_id.platform
            if hasattr(self, cust_method_name):
                shipment_items, exported_items = self._prepare_exported_shipment_items(self.move_lines)
                getattr(record, cust_method_name)(shipment_items, update_items=update_items)
                self._log_exported_shipment_items(exported_items)

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

    def mark_line_changed(self):
        self.update({'move_line_changed_at': fields.Datetime.now()})

    def do_update_shipment_to_channel(self):
        records_to_update = self.sudo().filtered(lambda r: r.is_update_to_channel_needed)
        for picking in records_to_update:
            if not picking.sale_id.channel_id.auto_export_shipment_to_store:
                raise ValidationError(_("You cannot update to store. Please check your settings in store settings and try again."))
            picking._put_shipment_to_channel(picking._is_move_line_changed())

    def mark_synced_with_channel(self, message=None):
        if message:
            self.message_post(body=_(message))
        self.update({'channel_synching_at': fields.Datetime.now()})
