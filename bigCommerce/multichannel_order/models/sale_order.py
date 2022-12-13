# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import itertools
import psycopg2

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.queue_job.exception import RetryableJobError

from odoo.addons.omni_manage_channel.utils.common import AddressUtils
from odoo.addons.omni_manage_channel.utils.common import ImageUtils

from ..utils.order_processing_helper import OrderProcessingBuilder
from odoo.addons.multichannel_product.utils.unit_converter import UnitConverter

_logger = logging.getLogger(__name__)


NON_PRODUCT_FLAGS = [
    'is_discount',
    'is_coupon',
    'is_tax',
    'is_handling',
    'is_wrapping',
    'is_other_fees',
    'is_delivery',
]

class MissingOrderProduct(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ShipmentImportError(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    id_on_channel = fields.Char(
        string='ID on Store', index=True, readonly=True)
    channel_id = fields.Many2one(
        'ecommerce.channel', related='order_id.channel_id')
    is_discount = fields.Boolean(
        readonly=True, help='To detect that line is for discount')
    is_coupon = fields.Boolean(
        readonly=True, help='To detect that line is for coupon')
    is_tax = fields.Boolean(
        readonly=True, help='To detect that line is for tax')
    is_handling = fields.Boolean(
        string='Is handling cost line', readonly=True, default=False)
    is_wrapping = fields.Boolean(
        string='Is wrapping cost line', readonly=True, default=False)
    is_other_fees = fields.Boolean(
        string='Is other fees cost line', readonly=True, default=False)
    sku = fields.Char(related='product_id.default_code')
    qty_delivered_on_channel = fields.Float(
        'Channel Delivered',
        copy=False,
        digits='Product Unit of Measure',
        default=0.0,
        help='Technical field for storing qty delivered from order line on channel.',
    )
    quantity_on_channel = fields.Float(string='Quantity on Channel', readonly=True,
                                       help='Need to track quantity of product on Channel for updating')
    price_unit = fields.Float(digits=False)
    price_subtotal = fields.Monetary()
    discount_amount = fields.Monetary()

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'order_id.state')
    def _get_to_invoice_qty(self):
        """
        If the order is from an online store, it should follow the configured processing rules
        Otherwise, it will have to follow Odoo's rules
        """
        def get_rule_and_following_lines():
            lines_from_channel = self.filtered(lambda ln: ln.order_id.channel_id)
            for order, lines in itertools.groupby(lines_from_channel.sorted('order_id'), key=lambda ln: ln.order_id):
                rule = self.env['order.process.rule'].search_rule(order)
                if rule and rule.is_invoice_created and rule.create_invoice_trigger:
                    yield rule, self.browse().concat(*(
                        line for line in lines
                        if not any(line[flag] for flag in NON_PRODUCT_FLAGS)
                    ))

        def set_qty_to_invoice(line, rule):
            if rule.create_invoice_trigger == 'order_confirmed':
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = line.qty_delivered - line.qty_invoiced

        lines_following_rule = self.browse()
        for order_rule, order_lines in get_rule_and_following_lines():
            lines_following_rule |= order_lines
            for order_line in order_lines:
                set_qty_to_invoice(order_line, order_rule)

        lines_not_following_rule = self - lines_following_rule
        super(SaleOrderLine, lines_not_following_rule)._get_to_invoice_qty()

    def _get_protected_fields(self):
        if self.env.context.get('ignore_done_protected_fields'):
            return []
        return super(SaleOrderLine, self)._get_protected_fields()

    def _generate_service_move_values(self):
        StockServiceMove = self.env['stock.service.move']
        lines = self.filtered(
            lambda r: r.product_id.is_deliverable_service and r._get_assigned_service_qty() < r.product_qty)
        move_vals = [StockServiceMove._get_stock_move_values(line) for line in lines]
        return move_vals

    def _action_generate_service_move(self):
        StockServiceMove = self.env['stock.service.move']
        moves = self.env['stock.service.move']
        lines = self.filtered(
            lambda r: r.product_id.is_deliverable_service and r._get_assigned_service_qty() < r.product_qty)
        moves |= StockServiceMove.search(
            [('sale_line_id', 'in', lines.ids), ('state', '=', 'draft')])
        lines = lines.filtered(
            lambda r: r not in moves.mapped('sale_line_id'))
        val_list = lines._generate_service_move_values()
        for vals in val_list:
            moves |= StockServiceMove.create(vals)
        return moves

    def _check_line_unlink(self):
        res = super(SaleOrderLine, self)._check_line_unlink()
        return res.filtered(lambda line: line.display_type != 'line_note')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    channel_id = fields.Many2one(
        'ecommerce.channel',
        string='Store',
        index=True,
        readonly=True
    )
    platform = fields.Selection(related='channel_id.platform')
    id_on_channel = fields.Char(
        string='ID on Channel', index=True, readonly=True)
    channel_order_ref = fields.Char(
        string='Channel Ref', help='Order Ref on Channel', readonly=True, copy=False)
    channel_transaction_ids = fields.One2many('order.channel.transaction', 'order_id',
                                              string='Transactions', help='Order Transactions on Channel')
    order_status_channel_id = fields.Many2one(
        'order.status.channel', string='Status on Store', copy=False, readonly=False)
    payment_status_channel_id = fields.Many2one('order.status.channel', string='Payment Status on Store',
                                                copy=False, readonly=False)

    display_status_on_channel = fields.Char(compute='_compute_status_on_channel')

    staff_notes = fields.Text(string='Staff Notes')
    customer_message = fields.Text(string='Customer Message')
    channel_date_created = fields.Datetime(
        string='Created Date on Channel', readonly=True, copy=False)

    shipping_status = fields.Selection([
        ('unshipped', 'Unshipped'),
        ('partially_shipped', 'Partially Shipped'),
        ('shipped', 'Fully Shipped')
    ], string='Shipping Status', compute='_compute_shipping_status', store=True)

    is_from_channel = fields.Boolean(compute='_compute_is_from_channel', search='_search_is_from_channel')
    service_picking_ids = fields.One2many(
        'stock.service.picking', 'sale_id', string='Service Pickings')
    service_delivery_count = fields.Integer(
        string='Service Delivery Orders', compute='_compute_service_picking_ids')
    is_done_physical_shipping = fields.Boolean(
        'Done Physical Shipping', compute='_compute_is_done_physical_shipping')

    requested_shipping_method = fields.Char(
        string='Requested Shipping Method', readonly=1)

    customer_channel_id = fields.Many2one(
        'customer.channel', string='Customer Account', readonly=True)
    updated_shipping_address_id = fields.Many2one(
        'res.partner', string='Updated Shipping Address', readonly=True)

    is_cancelled_on_channel = fields.Boolean('Cancelled on online store?', default=False)

    is_replacement = fields.Boolean(string='Is Replacement Order', default=False, copy=False)
    replaced_id_on_channel = fields.Char(string='Replacement',
                                         readonly=True,
                                         inverse='_set_replaced_order_id', store=True)
    replaced_order_id = fields.Many2one('sale.order', string='Replaced Order ID')

    payment_gateway_code = fields.Char(string='Payment Gateway Code', readonly=True)
    payment_gateway_name = fields.Char(string='Payment Gateway Name', compute='_compute_payment_gateway_name')

    _sql_constraints = [
        ('id_channel_uniq', 'unique(id_on_channel, channel_id)',
         'ID must be unique per channel!')
    ]

    @api.depends('payment_gateway_code')
    def _compute_payment_gateway_name(self):
        for record in self:
            payment_gateway = self.env['channel.payment.gateway'].search([('channel_id', '=', record.channel_id.id),
                                                                          '|', ('code', '=', record.payment_gateway_code),
                                                                          ('name', '=', record.payment_gateway_code)],
                                                                         limit=1)
            if payment_gateway:
                record.payment_gateway_name = payment_gateway.name
            else:
                record.payment_gateway_name = record.payment_gateway_code

    @api.depends('order_line.is_discount', 'order_line.is_coupon', 'order_line.is_tax', 'order_line.is_other_fees',
                 'order_line.is_handling', 'order_line.is_wrapping')
    def _get_invoice_status(self):
        super()._get_invoice_status()
        for order in self:
            if order.invoice_status in ['no', 'invoiced']:
                continue
            order_lines = order.order_line.filtered(lambda x: not x.is_discount and not x.is_coupon and not x.is_tax
                                                    and not x.is_other_fees and not x.is_handling
                                                    and not x.is_wrapping and not x.is_delivery
                                                    and not x.is_downpayment and not x.display_type)
            if all(line.product_id.invoice_policy == 'delivery' and line.invoice_status == 'no' for line in order_lines):
                order.invoice_status = 'no'

    def _set_replaced_order_id(self):
        for record in self:
            order = self.search([('id_on_channel', '=', record.replaced_id_on_channel),
                                 ('channel_id.id', '=', record.channel_id.id)], limit=1)
            record.replaced_order_id = order.id

    def _compute_invoice_date(self):
        self.ensure_one()
        # Invoice Date should be the date done of last shipment
        picking = self.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing' and p.state == 'done')
        if picking:
            picking = picking[-1]
            return picking.date_done.date()
        return None

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                if line.is_tax:
                    amount_tax += line.price_subtotal
                else:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    def _compute_status_on_channel(self):
        state_name_mapping = dict(self._fields['state'].selection)
        for record in self:
            if record.order_status_channel_id:
                record.display_status_on_channel = record.order_status_channel_id.display_name
            else:
                record.display_status_on_channel = state_name_mapping[record.state]

    @api.depends('channel_id')
    def _compute_is_from_channel(self):
        from_channel = self.filtered(lambda r: r.channel_id and r.channel_id.platform)
        not_from_channel = self - from_channel
        from_channel.update({'is_from_channel': True})
        not_from_channel.update({'is_from_channel': False})

    @api.model
    def _search_is_from_channel(self, operator, operand):
        if operator == '=' and operand:
            return [('channel_id.platform', 'not in', (False, ))]
        return [('channel_id.platform', 'in', (False, ))]

    @api.depends('order_line', 'order_line.product_id', 'order_line.product_uom_qty', 'order_line.qty_delivered')
    def _compute_shipping_status(self):
        self.mapped('order_line')  # Caching
        self.mapped('order_line.product_id')  # Caching
        for record in self:
            deliverable_lines = record.order_line.filtered(
                lambda l: l.product_id.type != 'service' or l.product_id.is_deliverable_service)
            if deliverable_lines:
                if all(line.qty_delivered == 0 for line in deliverable_lines):
                    res = 'unshipped'
                elif any(line.qty_delivered < line.product_uom_qty for line in deliverable_lines):
                    res = 'partially_shipped'
                else:
                    res = 'shipped'
            else:
                res = 'unshipped'
            record.shipping_status = res

    @api.depends('service_picking_ids')
    def _compute_service_picking_ids(self):
        for order in self:
            order.service_delivery_count = len(order.service_picking_ids)

    def _compute_is_done_physical_shipping(self):
        for record in self:
            order_lines = record.order_line.filtered(
                lambda l: l.product_id.type != 'service')
            record.is_done_physical_shipping = all(
                line.qty_delivered == line.product_uom_qty for line in order_lines)

    @api.model
    def _import_missing_products(self, channel, not_exists_products):
        uuids = []
        cust_method_name = '%s_get_data' % channel.platform
        if hasattr(self.env['product.template'], cust_method_name):
            method = getattr(self.env['product.template'].with_context(
                auto_merge_variant=True, master_type='product'), cust_method_name)

            # Create job for synching products

            product_ids = list(set([line['product_id']
                               for line in not_exists_products]))
            for product_id in product_ids:
                datas = method(channel_id=channel.id, id_on_channel=product_id)
                if datas:
                    uuids.extend(datas[1])
        return uuids

    @api.model
    def create_waiting_job(self, channel, not_exists_products, order_data):
        uuids = self._import_missing_products(channel, not_exists_products)
        self.with_delay(priority=20, max_retries=15).waiting_product(uuids=uuids,
                                                                     channel=channel,
                                                                     order_data=order_data)

    @api.model
    def _prepare_order_line(self, channel, line_data):
        return {
            'id_on_channel': line_data['id_on_channel'],
            'product_id': line_data['product_id'],
            'product_uom_qty': float(line_data.get('quantity')),
            'quantity_on_channel': line_data.get('quantity'),
            'qty_delivered_on_channel': line_data.get('quantity_delivered', 0),
            'name': line_data.get('name'),
            'price_unit': line_data.get('price'),
            'tax_id': [(5, 0, 0)],
            'discount_amount': line_data.get('discount_amount', 0.0),
            'sequence': 1,
        }

    @api.model
    def _create_missing_attribute_and_value(self, missing_lines):
        new_options_name = {}
        update_options = {}

        options_name = [option['name'] for line in missing_lines for option in line['options']]
        existed_options_name = self.env['product.attribute'].search([('name', 'in', options_name)])
        for line in missing_lines:
            options = line['options']
            for option in options:
                record = existed_options_name.filtered(lambda o: o.name == option['name'])
                if not record:
                    new_options_name.setdefault(option['name'], {'name': option['name'], 'value_ids': []})
                    new_options_name[option['name']]['value_ids'] += [(0, 0, {'name': option['value']})]
                else:
                    attribute_value = record.value_ids.filtered(lambda v: v.name == option['value'])
                    if not attribute_value:
                        update_options.setdefault(record.id, [])
                        update_options[record.id].append(option['value'])

        new_options = new_options_name.values()
        new_attributes = self.env['product.attribute'].create(new_options)

        attribute_to_update = [{'attribute_id': attribute, 'name': value} for attribute, values in
                               update_options.items() for value in set(values)]
        self.env['product.attribute.value'].create(attribute_to_update)
        existed_options_name |= new_attributes
        attributes = self.env['product.attribute'].browse(existed_options_name.ids)

        return attributes

    @api.model
    def _create_missing_product(self, missing_lines):
        try:
            attributes = self._create_missing_attribute_and_value(missing_lines)
        except Exception as e:
            _logger.exception("Something went wrong when create missing product attribute and value!")
            attributes = self.env['product.attribute'].browse()

        vals = [self._parse_product_data_from_order_line(line, attributes) for line in missing_lines]
        return self.env['product.template'].with_context(for_synching=True).create(vals)

    @api.model
    def _get_image_from_order_item(self, url):
        try:
            image = ImageUtils.get_safe_image_b64(url) if url else False
        except Exception as e:
            _logger.exception("Something went wrong when get image from order item url!")
            image = False
        return image

    @api.model
    def _parse_product_data_from_order_line(self, line, attributes):
        vals_list = []
        for option in line['options']:
            attribute = attributes.filtered(lambda a: a.name == option['name'])
            values = attribute.value_ids.filtered(lambda v: v.name == option['value'])
            vals_list.append({
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, values.ids)]
            })

        convert = UnitConverter(self).convert_weight
        if line['weight']:
            weight_in_oz = convert(line['weight'].get('value', 0.0), from_unit=line['weight'].get('units', 'ounces'), to_unit='ounce')
        else:
            weight_in_oz = 0

        return {
            'name': line['name'],
            'default_code': line['sku'],
            'upc': line['upc'] or False,
            'weight_in_oz': weight_in_oz or 0.0,
            'lst_price': line['price'] or 0,
            'image_1920': self._get_image_from_order_item(line['image_url']),
            'attribute_line_ids': [(0, 0, val) for val in vals_list] or False
        }

    @api.model
    def _search_master_product(self, order_data, channel):
        """
        Search all master products for all order lines
        """
        lines = order_data.get('lines')
        skus = [line['sku'] for line in lines if line['sku'] not in ['', 'None', None]]
        master_products = self.env['product.product'].sudo().search([('default_code', 'in', skus)])
        if channel.auto_create_master_product and len(set(skus)) != len(master_products):
            existed_skus = master_products.mapped('default_code')
            missing_lines = list(filter(lambda l: l['sku'] not in existed_skus, lines))
            master_products |= self._create_missing_product(missing_lines).mapped('product_variant_ids')
        return master_products

    @api.model
    def _ensure_all_product_are_matching(self, not_exists_products):
        skus = list(set(line['sku'] for line in not_exists_products))
        master_product = self.env['product.product'].search([
            '|',
            '&', ('default_code', 'in', skus), ('default_code', 'not in', [False, '']),
            ('product_alternate_sku_ids.name', 'in', skus),
        ])
        available_skus = master_product.mapped('default_code') + master_product.product_alternate_sku_ids.mapped('name')
        not_available_skus = set(skus) - set(available_skus)
        if not_available_skus:
            message = ("SKU not found: %s  " % ','.join(not_available_skus)).rstrip(': ')
            raise MissingOrderProduct(message)

    @api.model
    def _search_mapping_product(self, order_data, channel, no_waiting_product, auto_create_master):
        """
        Search all listings product for all order lines
        """
        lines = order_data.get('lines')
        no_custom_lines = list(filter(lambda ln: ln['product_id'] not in [
                               '', 'None', None, 0, '0'] and 'master_product_id' not in ln, lines))
        skus = []
        variant_ids = []
        product_channel_ids = []
        for line in no_custom_lines:
            if 'variant_id' in line and line['variant_id'] not in ['', 'None', None, 0, '0']:
                variant_ids.append(str(line['variant_id']))
            elif 'sku' in line:
                if line['sku'] in ['None', None]:
                    sku = ''
                else:
                    sku = line['sku']
                skus.append(sku)
            if 'product_id' in line and line['product_id'] not in ['', 'None', None, 0, '0']:
                product_channel_ids.append(str(line['product_id']))

        ProductChannelVariant = self.env['product.channel.variant']
        domain = [('channel_id.id', '=', channel.id),
                  ('product_product_id', '!=', False)]
        sub_domain = []
        if skus:
            sub_domain.append([('default_code', 'in', skus)])
        if variant_ids:
            sub_domain.append([('id_on_channel', 'in', variant_ids)])
        if sub_domain:
            domain += expression.OR(sub_domain)
        if product_channel_ids:
            domain += [('product_channel_tmpl_id.id_on_channel',
                        'in', product_channel_ids)]
        list_product_channel_variant = ProductChannelVariant.sudo().search(domain)

        #
        # Some products haven't been synched yet. Synching products before synching orders
        #
        channel_variants_len = len(list_product_channel_variant)
        no_enough_lines = False
        if channel_variants_len != 0:
            for line in no_custom_lines:
                product_channel_variant = False
                if 'variant_id' in line and line['variant_id'] not in ['', 'None']:
                    if line['variant_id'] in ['0', 0] and 'product_id' in line \
                            and line['product_id'] not in ['', 'None', 0, '0']:
                        product_channel_variant = list_product_channel_variant.filtered(
                            lambda p: p.product_channel_tmpl_id.id_on_channel == str(line['product_id']))
                        if product_channel_variant:
                            product_channel_variant = product_channel_variant[0]
                    else:
                        product_channel_variant = list_product_channel_variant.filtered(
                            lambda p: p.id_on_channel == line['variant_id'])
                elif 'sku' in line and line['sku'] not in ['', 'None']:
                    product_channel_variant = list_product_channel_variant.filtered(
                        lambda p: p.default_code == line['sku'])
                if not product_channel_variant:
                    no_enough_lines = True
                    break
        elif no_custom_lines:
            no_enough_lines = True
        if no_enough_lines:
            not_exists_products = no_custom_lines
            if list_product_channel_variant:
                existed_skus = []
                for v in list_product_channel_variant:
                    existed_skus.append(
                        '%s-%s' % (v.product_channel_tmpl_id.id_on_channel, v.default_code))

                not_exists_products = list(
                    filter(lambda l: str(str(l['product_id']) + '-' + l['sku']) not in existed_skus,
                           no_custom_lines))
            if not no_waiting_product:
                if not auto_create_master:
                    self._ensure_all_product_are_matching(not_exists_products)
                self.create_waiting_job(
                    channel, not_exists_products, order_data)
                return True, self.env['product.channel.variant']

        return False, list_product_channel_variant

    @api.model
    def get_customer_info(self, channel_id, order_data):
        """
        These keys need to be in order_data
        'customer_id': '',
        'billing_address': {
            'name': billing_address.get('name', ''),
            'street': billing_address.get('street', ''),
            'street2': billing_address.get('street2', ''),
            'city': billing_address.get('city', ''),
            'state_code': billing_address.get('region_code', ''),
            'country_code': billing_address.get('country_id', '').strip(),
            'email': billing_address.get('email', ''),
            'phone': billing_address.get('telephone', ''),
            'zip': billing_address.get('postcode', '')
        },
        'shipping_address': {
            'name': shipping_address.get('name', ''),
            'street': shipping_address.get('street', ''),
            'street2': shipping_address.get('street2', ''),
            'city': shipping_address.get('city', ''),
            'state_code': shipping_address.get('region_code', ''),
            'country_code': shipping_address.get('country_id', '').strip(),
            'email': shipping_address.get('email', ''),
            'phone': shipping_address.get('telephone', ''),
            'zip': shipping_address.get('postcode', '')
        },
        """
        customer_channel = self._get_customer_channel_from_order_data(channel_id, order_data)
        addresses = self._get_customer_addresses_from_order_data(order_data)
        return (customer_channel, None) + addresses

    @api.model
    def _get_customer_channel_from_order_data(self, channel_id, order_data):
        """
        Get and create customer profile if needed based on `order_data`
        `order_data` can have key `customer_data` for the info of customer profile for the order.
        Customer Data should have this format
        {
            'name': str Name of the customer,
            'phone': str Phone number,
            'email': str Email address,
            'id': str ID of the customer on channel,
            'street': str A part of the customer's address,
            'street2': str A part of the customer's address,
            'city': str A part of the customer's address,
            'zip': str Zip Code A part of the customer's address,
            'country_id': int Odoo Id of res.country of the address country,
            'state_id': int Odoo Id of res.country.state the address country,
        }
        """
        customer_id = order_data.get('customer_id', 0)
        customer_channel = self.env['customer.channel'].sudo()
        if str(customer_id) != '0':
            customer_channel_ids = customer_channel.get_data_from_channel(
                channel_id=channel_id,
                id_on_channel=customer_id,
                customer_data=order_data.get('customer_data', {})
            )
            customer_channel = customer_channel.browse(customer_channel_ids[:1])
        return customer_channel

    @api.model
    def _get_customer_addresses_from_order_data(self, order_data) -> tuple:
        address_types = ('billing_address', 'shipping_address')
        contact_types = ('invoice', 'delivery')
        addresses = ()
        for address_type, contact_type in zip(address_types, contact_types):
            address = order_data.get(address_type)
            if address:
                address = {k: v or False for k, v in address.items()}
                country = AddressUtils.get_country_record(self.env, address['country_code'])
                state = AddressUtils.get_state_record_by_code_or_name(
                    self.env,
                    country=country,
                    state_code=address.get('state_code', ''),
                    state_name=address.get('state_name', ''),
                )
                addresses += ({
                    'name': address['name'],
                    'company': address.get('company', ''),
                    'phone': address['phone'],
                    'email': address['email'],
                    'street': address['street'],
                    'street2': address['street2'],
                    'city': address['city'],
                    'zip': address['zip'],
                    'country_id': country.id,
                    'state_id': state.id,
                    'type': contact_type
                },)
            else:
                addresses += (None,)
        return addresses

    @api.model
    def _get_imported_order_domain(self, channel, order_key):
        return [('id_on_channel', '=', order_key), ('channel_id', '=', channel.id)]

    @api.model
    def _check_imported_order_data(self, channel, order_data):
        res = self._check_imported_order_data_channel_date(channel, order_data)
        res = res and self._check_imported_order_data_channel_status(channel, order_data)
        res = res and self._check_imported_order_data_master_status(channel, order_data)
        return res

    @api.model
    def _check_imported_order_data_channel_date(self, channel, order_data):
        channel_date = order_data.get('channel_date_created')
        min_order_date = channel.min_order_date_to_import
        is_manual = self.env.context.get('manual_import')
        res = is_manual or not (channel_date and min_order_date) or channel_date.date() >= min_order_date
        return res

    @api.model
    def _check_imported_order_data_channel_status(self, channel, order_data):
        order_configuration = channel.get_setting('order_configuration')
        fulfillment_status = self._get_order_status_channel(status=order_data.get('status_id'), channel=channel, type='fulfillment')
        if not self._check_imported_status(fulfillment_status, order_configuration['imported_fulfillment_status_ids']):
            return False
        payment_status = self._get_order_status_channel(status=order_data.get('payment_status_id'), channel=channel, type='payment')
        if payment_status and order_configuration['imported_payment_status_ids'] and not self._check_imported_status(payment_status, order_configuration['imported_payment_status_ids']):
            return False
        return True

    @api.model
    def _check_imported_order_data_master_status(self, channel, order_data):
        domain = self._get_imported_order_domain(channel, order_data['id'])
        order = self.env['sale.order'].search(domain, limit=1)
        # No process order if it was cancelled in Odoo
        if order.state == 'cancel':
            return False
        return True

    @api.model
    def create_jobs_for_synching(self, vals_list,
                                 channel_id,
                                 update=None,
                                 no_waiting_product=None):
        """
        Spit values list to smaller list and add to Queue Job
        :param vals_list: The following is keys for each element in vals_list
        {
            'lines': [{
                'product_id': use for searching product_channel_tmpl
                'sku': sku for product_channel_variant
                'variant_id': id on channel for product_channel_variant (optional)
                'id_on_channel': id on channel of order line
                'quantity': number of ordered quantity
                'quantity_delivered': number of delivered quantity (optional)
                'name': description for order line,
                'price': price unit,
                'discount_amount': 0.0
            }],
            'discounts': [{
                'product_id': product_product_id assigned to discount line,
                'name" description for discount line,
                'amount': price unit for discount line
            }],
            'discount_notes: the list of discount notes (optional),
            'taxes': [{
                'name': description for tax line,
                'amount': price unit for tax line,
                'associated_account_tax_id': if we can create a tax record to assign to tax line
            }],
            'tax_notes: the list of tax notes (optional),
            'services': [{
                'product_id': product_product_id assigned to service line,
                'name': description for service line,
                'quantity': 1,
                'price_unit': price unit,
                'is_wrapping': True if this is wrapping cost,
                'is_handling': True if this is handling cost,
                'is_delivery': True if this is shipping cost
            }],
            'id': id on channel of order,
            'channel_date_created': created date of order on channel,
            'status_id': status of order on channel. Will be used in mapping status with Odoo status
        }
        :param channel_id: Odoo ID of the ecommerce.channel of the order
        :param update: Whether this is to update or create
        :param no_waiting_product: A flag telling the system not to wait for product to sync later
        In addition, we should include all information of order from channel for creating customer info
        """

        uuids = []
        channel = self.env['ecommerce.channel'].browse(int(channel_id))
        auto_create_master = channel.get_setting('auto_create_master_product')
        search_on_mapping = channel.get_setting('manage_mapping')

        if not update or (update and channel.allow_update_order):
            for vals in vals_list:
                try:
                    if not self._check_imported_order_data(channel, vals):
                        continue
                    order_data = self._prepare_imported_order(
                        order_data=vals,
                        channel_id=channel_id,
                        no_waiting_product=no_waiting_product,
                        auto_create_master=auto_create_master,
                        search_on_mapping=search_on_mapping
                    )
                    if order_data:
                        log = self.env['omni.log'].create({
                            'datas': vals,
                            'channel_id': channel_id,
                            'operation_type': 'import_order',
                            'entity_name': vals['channel_order_ref'],
                            'res_model': 'sale.order',
                            'channel_record_id': str(vals['id'])
                        })

                        job_uuid = self.with_context(log_id=log.id).with_delay(eta=5, max_retries=15)\
                            ._sync_in_queue_job(order_data, channel_id, update).uuid
                        log.update({'job_uuid': job_uuid})
                        uuids.append(job_uuid)
                except MissingOrderProduct as e:
                    self.env['omni.log'].create({
                        'datas': vals,
                        'channel_id': channel_id,
                        'entity_name': vals['channel_order_ref'],
                        'operation_type': 'import_order',
                        'res_model': 'sale.order',
                        'status': 'failed',
                        'message': str(e),
                        'channel_record_id': str(vals['id'])
                    })
                    continue
                except Exception as e:
                    _logger.exception(e)
                    self.env['omni.log'].create({
                        'datas': vals,
                        'channel_id': channel_id,
                        'entity_name': vals['channel_order_ref'],
                        'operation_type': 'import_order',
                        'res_model': 'sale.order',
                        'status': 'failed',
                        'message': str(e),
                        'channel_record_id': str(vals['id'])
                    })

        return uuids

    @api.model
    def _sync_in_queue_job(self, order_data, channel_id, update):

        try:
            if update:
                self._update_in_queue_job(order_data, channel_id)
            else:
                self.with_context(for_synching=True).create(self.flatten_order_data(order_data))
        except MissingOrderProduct as e:
            raise e
        except (psycopg2.InternalError, psycopg2.OperationalError) as e:
            raise RetryableJobError(e)
        except Exception as e:
            raise e

    @api.model
    def flatten_order_data(self, data):
        """
        Lazy functions is forced being calculated here
        """
        for line_data in data.get('order_line', []):
            try:
                _, _, vals = line_data
                obj = vals['product_id']
                rec = self.env[obj['_m']].browse(obj['_i'])
                res = getattr(rec, obj['_f'])(*obj['_a'], **obj['_k'])
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            else:
                vals['product_id'] = res
        return data

    @api.model
    def _get_order_status_channel(self, status, channel, type='fulfillment'):
        domain = [('platform', '=', channel.platform), ('type', '=', type)]
        if isinstance(status, int):
            domain += [('id_on_channel', '=', str(status))]
            status = self.env['order.status.channel'].sudo().search(domain, limit=1)
        else:
            domain += [('name', '=', status)]
            status = self.env['order.status.channel'].sudo().search(domain, limit=1)
        return status

    @api.model
    def _find_order_items(self, order_data, channel, no_waiting_product, auto_create_master, search_on_mapping):
        """
        Search on Master or Product Mappings for order items
        """
        waiting_job, products = None, []
        if not search_on_mapping:
            products = self._search_master_product(order_data, channel)
        else:
            waiting_job, products = self._search_mapping_product(order_data, channel,
                                                                 no_waiting_product, auto_create_master)
        return waiting_job, products

    @api.model
    def _prepare_imported_order_lines(self, channel, lines, products, search_on_mapping):
        ln_vals = []
        for line in lines:
            if not search_on_mapping:
                product = products.filtered(lambda p: p.default_code == line['sku'])
                if not product:
                    raise ValidationError(_('Missing SKU %s', line['sku']))
                line['product_id'] = product[0].id
            else:
                if line['product_id'] in ['0', 'None']:
                    line_dup = dict(line)
                    line['product_id'] = {
                        '_m': 'sale.order',
                        '_i': (),
                        '_f': '_prepare_imported_order_lines_generate_custom_product_id',
                        '_a': (line_dup,),
                        '_k': {},
                    }
                else:
                    listing = self._prepare_imported_order_lines_get_listing_mapping(line, products, channel)
                    if listing:
                        mapping_quantity = listing.mapping_quantity
                        line.update({
                            'product_id': listing.product_product_id.id,
                            'quantity': line['quantity'] * mapping_quantity,
                            'price': float_round(float(line['price']) / mapping_quantity, precision_digits=2)
                        })
            ln_vals.append((0, 0, self._prepare_order_line(channel, line)))
        return ln_vals

    @api.model
    def _prepare_imported_order_lines_generate_custom_product_id(self, line):
        product = self._prepare_imported_order_lines_generate_custom_product(line)
        return product.id

    @api.model
    def _prepare_imported_order_lines_generate_custom_product(self, line):
        default_code = line.get('sku', '') if line.get('sku') != 'None' else ''

        if default_code:
            existing_product = self.env['product.product'].search([('default_code', '=', default_code)], limit=1)
            if existing_product:
                return existing_product

        template = self.env['product.template'].create({
            'name': line['name'],
            'type': line.get('type', False) or 'consu',
            'sale_ok': True,
            'active': True,
            'default_code': default_code,
            'lst_price': line.get('price'),
            'invoice_policy': 'delivery',
        })
        product = template.product_variant_id
        product.write({
            'is_custom_product': True,
        })
        return product

    @api.model
    def _prepare_imported_order_lines_get_listing_mapping(self, line, listings, channel):
        def _check_listing_mapping(lm):
            if lm:
                if not lm.product_product_id:
                    raise ValidationError(_('%s does not have any link to master product', lm.name))
            else:
                raise ValidationError(_('SKU not found'))

        if line.get('variant_id', False):
            if line['variant_id'] == '0' and 'product_id' in line:
                listing = listings.filtered(
                    lambda r: r.product_channel_tmpl_id.id_on_channel == str(line['product_id']))[0]
            else:
                listing = listings.filtered(lambda r: r.id_on_channel == str(line['variant_id']))
        elif line.get('sku', False):
            listing = listings.filtered(
                lambda r: r.default_code == line['sku'] and r.channel_id == channel)
        else:
            listing = None
        _check_listing_mapping(listing)
        return listing

    @api.model
    def _check_imported_status(self, status, imported_status_ids):
        if not imported_status_ids or (imported_status_ids and (not status or status.id not in imported_status_ids)):
            return False
        return True

    @api.model
    def _set_store_warehouse(self, order_data, order_configuration):
        return order_configuration['warehouse_id']

    @api.model
    def _get_pricelist(self, order_data, partner, company_id):
        pricelist = partner.property_product_pricelist
        if 'currency_code' in order_data:
            currency_pricelist = self.env['product.pricelist'].search([('currency_id.name', '=', order_data['currency_code']),
                                                                       ('company_id', 'in', [company_id, False])], limit=1)
            pricelist = currency_pricelist or pricelist
        return pricelist.id

    @api.model
    def _prepare_imported_order(
            self, order_data, channel_id,
            no_waiting_product=None, auto_create_master=True, search_on_mapping=True):

        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)

        order_configuration = channel.get_setting('order_configuration')

        fulfillment_status = self._get_order_status_channel(status=order_data.get('status_id'), channel=channel, type='fulfillment')
        payment_status = self._get_order_status_channel(status=order_data.get('payment_status_id'), channel=channel, type='payment')

        customer_channel, partner, invoice_info, shipping_info = self.get_customer_info(
            channel_id, order_data)

        order_number = f"{order_configuration['order_prefix']}{order_data['channel_order_ref']}" if order_configuration['order_prefix'] else order_data['channel_order_ref']

        customer_channel, partner, partner_invoice, partner_shipping =\
            customer_channel.determine_customer(
                channel, invoice_info, shipping_info, order_number)

        order_data.update({
            'name': order_number,
            'partner_id': partner.id,
            'partner_invoice_id': partner_invoice.id,
            'partner_shipping_id': partner_shipping.id,
            'updated_shipping_address_id': partner_shipping.id,
            'customer_channel_id': customer_channel.id if customer_channel else False,
            'picking_policy': order_configuration['shipping_policy'],
            'team_id': order_configuration['sales_team_id'],
            'order_status_channel_id': fulfillment_status.id,
            'payment_status_channel_id': payment_status.id,
            'warehouse_id': self._set_store_warehouse(order_data, order_configuration),
            'company_id': order_configuration['company_id'],
            'pricelist_id': self._get_pricelist(order_data, partner, order_configuration['company_id'])
        })

        waiting_job, products = self._find_order_items(
            order_data, channel, no_waiting_product, auto_create_master, search_on_mapping)

        if waiting_job:
            # Waiting for importing product firstly
            return None

        return self._process_order_data(order_data, order_configuration, channel, products, search_on_mapping)

    @api.model
    def _process_order_data(self, order_data, order_configuration, channel, products, search_on_mapping):
        def prepare_builder(order_data, channel_id):
            res = OrderProcessingBuilder()
            res.order_data = order_data
            res.channel_id = channel_id
            res.default_product_ids = order_configuration['default_product_ids']
            return res

        builder = prepare_builder(order_data, channel.id)
        gen = builder.prepare_order_data()
        content = next(gen)
        order_vals = gen.send(self._prepare_imported_order_lines(channel, content, products, search_on_mapping))
        order_vals = self.assign_requested_shipping_method(order_vals)
        order_vals.update(self._extend_ecommerce_order_vals(channel, order_data))

        return order_vals

    @api.model
    def assign_requested_shipping_method(self, order_vals):
        requested = order_vals.get('requested_shipping_method')
        if requested:
            shipping_method = self.env['shipping.method.channel'].sudo().search([
                ('channel_id', '=', order_vals['channel_id']),
                ('name', '=', requested)
            ], limit=1)
            order_vals['carrier_id'] = shipping_method.delivery_carrier_id.id
        else:
            order_vals['requested_shipping_method'] = 'None'
        return order_vals

    def _process_update_order_line(self, order_line_datas):
        def is_non_product_line(ln_vals):
            return any(ln_vals.get(val_type) for val_type in NON_PRODUCT_FLAGS)

        self.ensure_one()
        values = []
        # Remove the first tuple in list (5,0,0)
        order_line_datas = order_line_datas[1:]
        updated_product_lines = self.env['sale.order.line']

        product_lines_data = list(filter(lambda l: 'product_id' in l[2], order_line_datas))
        non_product_lines_data = list(filter(lambda l: 'product_id' not in l[2], order_line_datas))

        for line_data in product_lines_data:
            line_vals = line_data[2]
            ioc = str(line_vals.get('id_on_channel', '')) if line_vals.get('id_on_channel', '') else False
            if ioc:
                order_line = self.order_line.filtered(lambda line: line.id_on_channel == ioc)
            elif is_non_product_line(line_vals):
                order_line = self.order_line.filtered(lambda line: line.product_id.id == line_vals.get('product_id', 0))
            else:
                order_line = self.order_line.browse()
            if line_vals.get('is_coupon', False) and order_line:
                order_line = order_line.filtered(lambda l: l.name == line_vals['name'])
                if order_line:
                    updated_product_lines += order_line
                    del line_vals['product_id']
                    if line_vals.get('price_unit', 0.0) is not None:
                        values.append((1, order_line.id, line_vals))
                else:
                    values.append(line_data)
            elif order_line:
                updated_product_lines += order_line
                del line_vals['product_id']
                if line_vals.get('price_unit', 0.0) is not None:
                    values.append((1, order_line.id, line_vals))
            else:
                values.append(line_data)

        removed_product_lines = self.order_line.filtered(lambda ln: ln.product_id and ln not in updated_product_lines)
        values += [(1, line.id, {'product_uom_qty': 0}) for line in removed_product_lines]

        ex_non_product_line_names = self.order_line.filtered(lambda ln: not ln.product_id).mapped('name')
        values += list(filter(lambda ln: ln[2]['name'] not in ex_non_product_line_names, non_product_lines_data))
        return values

    @api.model
    def _extend_ecommerce_order_vals(self, channel, order_data):
        """Use to extend specific data for eCommerce store

        Args:
            channel (ecommerce.channel): store
            order_data (dict): order data was imported

        Returns:
            dict: extended data will be addedd to order vals
        """
        return {}

    @api.model
    def _update_in_queue_job(self, order_data, channel_id):
        # Only update existed orders if they haven't been confirmed yet
        existed_order = self.sudo().search([('id_on_channel', '=', order_data['id_on_channel']),
                                            ('channel_id.id', '=', channel_id)])

        existed_order = existed_order.with_context(for_synching=True)
        # Check order status will be updated later.
        # If current status is done or cancel and later it will be others,
        # should unlock or set to draft for that order
        # Because done and cancel order cannot be updated
        if existed_order.state in ['sale', 'done']:
            order_data['order_line'] = existed_order._process_update_order_line(
                order_data['order_line'])

        # Don't need to update delivery address if don't having changes

        if 'partner_shipping_id' in order_data:
            # Compare shipping address to know whether or not to have any changes on shipping address
            if existed_order.updated_shipping_address_id.id != order_data['updated_shipping_address_id']:
                new_shipping_address = self.env['res.partner'].sudo().browse(
                    order_data['updated_shipping_address_id'])
                existed_order._log_exception_shipping_address_changes(current=existed_order.updated_shipping_address_id,
                                                                      new=new_shipping_address)

        # No update these fields
        for key in ['name', 'team_id', 'picking_policy',
                    'warehouse_id', 'requested_shipping_method', 'partner_shipping_id']:
            if key in order_data:
                del order_data[key]

        existed_order.sudo().with_context(
            ignore_done_protected_fields=True).write(self.flatten_order_data(order_data))
        # Get other data and then update status
        existed_order._sync_other_data()
        self.env['order.process.rule'].run(existed_order)
        return True

    def get_channel_transactions(self):
        self.ensure_one()
        if self.channel_id:
            cust_method_name = '%s_get_order_transactions' % self.channel_id.platform
            if hasattr(self, cust_method_name):
                method = getattr(self, cust_method_name)
                return method()
        return []

    def _import_shipments(self, shipment_id):
        cust_method_name = '%s_get_order_shipments' % self.channel_id.platform
        shipments, error_message = [], None
        if hasattr(self, cust_method_name):
            method = getattr(self.with_context(for_synching=True), cust_method_name)
            shipments, error_message = method(shipment_id=shipment_id)

        return shipments, error_message

    def _prepare_shipment_import_log_vals(self, res_model, shipment):
        return {
            'datas': shipment,
            'parent_res_id': self.id,
            'parent_res_model': self._name,
            'parent_ref': self.channel_order_ref,
            'channel_id': self.channel_id.id,
            'operation_type': 'import_shipment',
            'res_model': res_model,
            'channel_record_id': shipment['id_on_channel']
        }

    def import_shipments(self, shipment_id=None):
        """
        This is used for synching shipment data
        :return:
        """
        self.ensure_one()
        shipments, error_message = self._import_shipments(shipment_id)
        if shipments:
            for shipment in shipments:
                res_model = 'stock.picking'
                if 'is_physical_shipment' in shipment and not shipment['is_physical_shipment']:
                    res_model = 'stock.service.picking'
                log = self.env['omni.log'].create(self._prepare_shipment_import_log_vals(res_model, shipment))

                status = 'done' if not error_message else 'failed'
                log.update_status(status, error_message)
        if error_message:
            shipment = {'id_on_channel': ''}
            log_vals = self._prepare_shipment_import_log_vals('stock.picking', shipment)
            log_vals['datas'] = {'data': []}
            log = self.env['omni.log'].create(log_vals)
            log.update_status('failed', error_message)

    def _sync_other_data(self):
        """
        This is used for synching other data of order such as payment info, etc...
        :return:
        """
        #
        # Get Order Shipments and Create Delivery order
        #
        for record in self:
            try:
                record.import_shipments()
            except Exception as e:
                # Already have a omni.log for this
                _logger.error(e)

    def _post_order_to_channel(self):
        for record in self:
            cust_method_name = '%s_post_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    def _put_order_to_channel(self):
        for record in self:
            cust_method_name = '%s_put_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    @api.model
    def create(self, vals):
        if 'channel_order_ref' not in vals and 'id_on_channel' in vals:
            vals['channel_order_ref'] = vals['id_on_channel']
        if 'channel_order_ref' not in vals:
            vals['channel_order_ref'] = vals.get('name', '')
        if 'channel_date_created' not in vals:
            vals['channel_date_created'] = fields.Datetime.to_string(
                fields.Datetime.now())
        record = super(SaleOrder, self).create(vals)
        if 'for_synching' in self.env.context:
            record = record.with_context(for_synching=True)
            self.env['order.process.rule'].run(record)
            record._sync_other_data()
        return record

    def write(self, vals):
        """
        Override this method to prevent updating order date for online orders
        """
        if 'date_order' in vals:
            online_orders = self.filtered(lambda o: o.channel_id)
            res = super(SaleOrder, self - online_orders).write(vals)
            new_vals = dict(vals)
            new_vals.pop('date_order')
            res &= super(SaleOrder, online_orders).write(new_vals)
        else:
            res = super(SaleOrder, self).write(vals)
        return res

    @api.model
    def waiting_product(self, uuids, channel, order_data):
        """
        Used when products on orders haven't been synched yet
        """
        records = self.env['queue.job'].sudo().search([('uuid', 'in', uuids)])

        existed_order = self.sudo().search(
            [('id_on_channel', '=', str(order_data['id'])), ('channel_id.id', '=', channel.id)])

        update = True if existed_order else None
        no_waiting_product = True
        # Some cases, we are missing job queue
        if len(records) != len(uuids):
            no_waiting_product = False
        elif any(r.state not in ['done', 'failed'] for r in records):
            raise RetryableJobError('Waiting for other jobs set to done')

        self.create_jobs_for_synching(vals_list=[order_data],
                                      channel_id=channel.id,
                                      update=update,
                                      no_waiting_product=no_waiting_product)
        return True

    @api.model
    def waiting_order(self, id_on_channel, channel_id):
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        order_obj = self.env['sale.order'].search(
            [('id_on_channel', '=', id_on_channel), ('channel_id.id', '=', channel_id)], limit=1)
        if not order_obj:
            raise RetryableJobError(_('Order has not synced yet'))

        cust_method_name = '%s_get_data' % channel.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            method(channel_id=channel_id,
                   id_on_channel=id_on_channel, update=True)

    @api.model
    def get_status_on_channel(self):
        """
        Get current status on channel
        :return:
        """
        cust_method_name = '%s_get_order_status' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            getattr(self, cust_method_name)()

    @api.model
    def has_been_shipped(self):
        cust_method_name = '%s_has_been_shipped' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            return getattr(self, cust_method_name)()
        return False

    def re_create_physical_transfer(self):
        """
        Allow user to create another delivery orders for physical
        :return:
        """
        self.ensure_one()
        self.with_context(generate_service_move=False)._action_confirm()
        return self.action_view_open_delivery()

    def re_create_service_transfer(self):
        """
        Allow user to create another delivery orders for services
        :return:
        """
        self.ensure_one()
        self._action_confirm()

    def _cancel_single_order_on_channel(self):
        self.ensure_one()
        cust_method_name = '%s_cancel_on_channel' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            success = getattr(self, cust_method_name)()
            if success:
                self.is_cancelled_on_channel = True
            return success
        return False

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        self.mapped('service_picking_ids').with_context(
            skip_done_service_transfers=True).action_cancel()
        return res

    def cancel_order_on_channel(self):
        self.ensure_one()
        return self._cancel_single_order_on_channel()

    def _log_exceptions_on_order(self, title, exceptions):
        self.ensure_one()
        render_context = {
            'origin_order': self,
            'exceptions': exceptions,
            'title': title
        }
        _logger.error("Order Exception: %s" % render_context)
        self._activity_schedule_with_view(
            'mail.mail_activity_data_warning',
            user_id=self.env.user.id,
            views_or_xmlid='multichannel_order.exception_on_order',
            render_context=render_context
        )

    def _log_exception_shipping_address_changes(self, current, new):
        self.ensure_one()
        FIELDS = ['city', 'state_id', 'zip', 'country_id']
        differs = []

        current_street = ('%s, %s' % (current['street'], current['street2'])) \
            if current['street2'] else current['street']
        new_street = ('%s, %s' % (new['street'], new['street2'])) \
            if new['street2'] else new['street']

        if current_street != new_street:
            differs.append({'from': current_street,
                            'to': new_street,
                            'field': 'Address'})

        for field in FIELDS:
            if current[field] != new[field]:
                if '_id' in field:
                    differs.append({'from': current[field].name,
                                    'to': new[field].name,
                                    'field': field.replace('_id', '').title()})
                else:
                    differs.append({'from': current[field],
                                    'to': new[field],
                                    'field': field.title()})

        if differs:
            render_context = {
                'origin_order': self,
                'differs': differs,
                'title': 'Shipping Address is changed on %s' % self.channel_id.platform.title()
            }
            self._activity_schedule_with_view(
                'mail.mail_activity_data_warning',
                user_id=self.env.user.id,
                views_or_xmlid='multichannel_order.exception_shipping_address_changes',
                render_context=render_context
            )

    def _action_confirm(self):
        super(SaleOrder, self)._action_confirm()
        if self.env.context.get('generate_service_move', True):
            for order in self:
                moves = order.order_line._action_generate_service_move()
                moves._action_confirm()

    def action_view_service_delivery(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            'multichannel_fulfillment.action_service_picking_tree_all')

        pickings = self.mapped('service_picking_ids')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            action['views'] = [
                (self.env.ref('multichannel_fulfillment.view_service_picking_form').id, 'form')]
            action['res_id'] = pickings.id
        return action

    def action_view_open_delivery(self):
        """
        This function returns an action that display existing delivery orders (draft, waiting, ready)
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            'stock.action_picking_tree_all')

        pickings = self.mapped('picking_ids').filtered(
            lambda p: p.state not in ('done', 'cancel'))
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            action['views'] = [
                (self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = pickings.id
        return action

    def channel_receive_payment(self):
        payment_vals = self._channel_create_payment_vals()
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        return payment

    def channel_import_order(self, channel, ids=None, from_date=None, to_date=None):
        method = '{}_get_data'.format(channel.platform)
        if hasattr(self, method):
            now = fields.Datetime.to_string(fields.Datetime.now())
            from_date = from_date or channel.last_sync_order
            getattr(self.with_delay(), method)(channel_id=channel.id,
                                               ids=ids or [],
                                               from_date=from_date,
                                               to_date=to_date)

            # For manually import, we don't need to update
            if 'manually_import' not in self.env.context:
                self.env.cr.execute("UPDATE ecommerce_channel SET last_sync_order = '%s' WHERE id = %d"
                                    % (now, channel.id))
                self._cr.commit()

    @api.model
    def channel_export_orders(self, channel, ids=[]):
        method = '{}_export_orders'.format(channel.platform)
        if hasattr(self, method):
            getattr(self, method)(channel, ids=ids)
