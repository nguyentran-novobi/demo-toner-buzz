import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class OrderProcessRule(models.Model):
    _name = 'order.process.rule'
    _description = 'Order Process Rule'
    _order = 'sequence, id desc'

    sequence = fields.Integer(string='Sequence')
    name = fields.Char(string='Name', required=True)
    channel_id = fields.Many2one('ecommerce.channel', string='Store', ondelete='cascade')
    platform = fields.Selection(related='channel_id.platform')
    order_status_channel_ids = fields.Many2many(
        'order.status.channel',
        'fulfillment_status_ref',
        'status_id',
        'rule_id',
        string='Order Status',
        domain="[('platform', '=', platform), ('type', '=', 'fulfillment')]",
        required=True,
    )
    payment_status_channel_ids = fields.Many2many(
        'order.status.channel',
        'payment_status_ref', 'status_id', 'rule_id', string='Payment Status',
        domain="[('platform', '=', platform), ('type', '=', 'payment')]",
        required=False,
    )
    has_payment_statuses = fields.Boolean(compute='_compute_has_payment_statuses')

    is_order_confirmed = fields.Boolean(string='Confirm Order')
    is_invoice_created = fields.Boolean(string='Create Invoice')
    is_payment_created = fields.Boolean(string='Create Payment')

    create_invoice_trigger = fields.Selection(selection=[
        ('order_confirmed', 'After confirming sales order'),
        ('fully_shipped', 'After fully shipped')
    ], default='order_confirmed')

    @api.constrains('order_status_channel_ids')
    def _check_order_status(self):
        for record in self:
            if not record.order_status_channel_ids:
                raise ValidationError(_('Status(es) to Import is required !'))

    def _compute_has_payment_statuses(self):
        for record in self:
            has_payment_statuses = self.env['order.status.channel'].search([
                ('platform', '=', record.platform),
                ('type', '=', 'payment'),
            ], limit=1)
            record.has_payment_statuses = bool(has_payment_statuses)

    @api.model
    def _generate_domain_search_rule(self, channel, order):
        domain = [('channel_id', '=', channel.id)]
        domain += expression.OR([
            [('order_status_channel_ids.id', '=', order.order_status_channel_id.id)],
            [
                ('order_status_channel_ids.id', '=', order.order_status_channel_id.id),
                ('payment_status_channel_ids.id', '=', order.payment_status_channel_id.id),
            ]
        ])
        return domain

    @api.model
    def _search_rule(self, channel, order):
        domain = self._generate_domain_search_rule(channel, order)
        rule = self.search(domain, limit=1)
        return rule

    @api.onchange('is_order_confirmed', 'is_payment_created')
    def onchange_options(self):
        if not self.is_order_confirmed:
            self.update({
                'is_invoice_created': False,
                'is_payment_created': False,
            })

    def _get_payment_gateway_mapping(self, payment_gateway_code):
        res = dict(
            journal_id=self.channel_id.default_payment_journal_id.id,
            payment_method_id=self.channel_id.default_payment_method_id.id,
            property_account_customer_deposit_id=self.channel_id.default_deposit_account_id.id,
        )
        payment_gateway = self.env['payment.method.mapping'].search([
            ('channel_id', '=', self.channel_id.id),
            '|', ('payment_gateway_id.code', '=', payment_gateway_code),
            ('payment_gateway_id.name', '=', payment_gateway_code)
        ], order='sequence desc', limit=1)
        if payment_gateway:
            res.update({
                'journal_id': payment_gateway.payment_journal_id.id,
                'payment_method_id': payment_gateway.payment_method_id.id,
                'property_account_customer_deposit_id': payment_gateway.deposit_account_id.id
            })
        return res

    def _deposit_payment_vals(self, order):
        payment_gateways_info = self._get_payment_gateway_mapping(order.payment_gateway_code)
        payment_vals = {
            'date': order.date_order,
            'amount': order.amount_total,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': payment_gateways_info['journal_id'],
            'currency_id': order.currency_id.id,
            'partner_id': order.partner_id.id,
            'payment_method_id': payment_gateways_info['payment_method_id'],
            'property_account_customer_deposit_id': payment_gateways_info['property_account_customer_deposit_id'],
            'sale_deposit_id': order.id,
            'is_deposit': True
        }
        return payment_vals

    @api.model
    def run(self, order):
        """
        After orders were imported in Odoo successfully, Import & Automation Settings will be run
        to get rule which is matching with some conditions:
            - Fulfillment Status
            - Payment Status

        Actions can be applied to order
            - Confirm Order
            - Create Invoice
            - Create Payment
        """
        rule = self.search_rule(order)
        if rule:
            rule._do_run_rule(order)
        return True

    @api.model
    def search_rule(self, order):
        if not order.channel_id:
            return self.browse()
        return self._search_rule(order.channel_id, order)

    def _do_run_rule(self, order):
        self._do_run_confirm_order(order)
        self._do_run_create_payment(order)
        self._do_run_create_invoice(order)

    def _do_run_confirm_order(self, order):
        if self.is_order_confirmed and order.state not in ['sale', 'done', 'cancel']:
            order.action_confirm()

    def _do_run_create_payment(self, order):
        if self.is_payment_created and not order.deposit_ids:
            payment = self.env['account.payment'].create(self._deposit_payment_vals(order))
            payment.action_post()

            # If Invoice is created before
            if order.invoice_ids:
                self.env['account.move']._reconcile_deposit(payment, order.invoice_ids[0])

    def _do_run_create_invoice(self, order):
        if self.is_invoice_created:
            if self.create_invoice_trigger == 'order_confirmed':
                order._force_lines_to_invoice_policy_order()
                self._create_posted_invoice_from_order_if_invoiceable(order)
            if self.create_invoice_trigger == 'fully_shipped' \
                    and order.invoice_status == 'to invoice' and order.shipping_status == 'shipped':
                self._create_posted_invoice_from_order_if_invoiceable(order)

    def _create_posted_invoice_from_order_if_invoiceable(self, order):
        invoiceable_lines = order._get_invoiceable_lines()
        is_order_invoiceable = any(not line.display_type for line in invoiceable_lines)
        if is_order_invoiceable:
            return self._create_posted_invoice_from_order(order)
        return self.env['account.move']

    def _create_posted_invoice_from_order(self, order):
        invoices = order._create_invoices()
        if self.create_invoice_trigger == 'fully_shipped':
            # Invoice Date should be the date done of the last of shipment
            date = order._compute_invoice_date() or fields.Date.today()
            invoices.update({'date': date})
        invoices.action_post()
        return invoices
