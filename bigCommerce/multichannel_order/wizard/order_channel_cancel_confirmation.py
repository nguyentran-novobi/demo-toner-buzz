# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OrderChannelCancelConfirmation(models.TransientModel):
    _name = 'order.channel.cancel.confirmation'
    _description = 'Online Order Cancellation Confirmation'

    @api.model
    def _default_notification_email_template_id(self):
        return self.env.ref('multichannel_order.mail_template_order_cancellation')

    sale_order_id = fields.Many2one('sale.order', required=True)

    is_credit_note_creation_enabled = fields.Boolean(default=False)
    credit_note_reason = fields.Char()
    credit_note_date = fields.Date(default=fields.Date.context_today)

    is_notification_email_enabled = fields.Boolean(default=False)
    notification_email_template_id = fields.Many2one('mail.template', default=_default_notification_email_template_id)

    def button_confirm(self):
        self.ensure_one()
        success = self.do_cancel_order_on_channel()
        if success:
            self.do_create_credit_note()
            self.do_send_notification_email()

    def get_order_posted_deposits(self):
        return self.sale_order_id.deposit_ids.filtered(lambda inv: inv.state == 'posted')

    def get_order_posted_invoices(self):
        return self.sale_order_id.invoice_ids.filtered(lambda inv: inv.state == 'posted')

    def do_cancel_order_on_channel(self):
        return self.sale_order_id.cancel_order_on_channel()

    def do_create_credit_note(self):
        if self.is_credit_note_creation_enabled:
            self.create_credit_note()

    def create_credit_note(self):
        """
        Create credit notes for invoices and deposits
        Once create for invoices, this will not create for deposits
        There should be at least a suitable invoice or deposit
        """
        posted_invoices = self.get_order_posted_invoices()
        if posted_invoices:
            self.create_credit_note_for_invoices(posted_invoices)
        else:
            self.create_credit_note_for_order()

    def create_credit_note_for_invoices(self, invoices):
        ctx = dict(active_model=invoices._name, active_ids=invoices.ids)
        vals = self._generate_reversal_invoice_vals(invoices)
        reversal = self.env['account.move.reversal'].with_context(**ctx).create(vals)
        reversal.reverse_moves()
        return reversal.new_move_ids

    def _generate_reversal_invoice_vals(self, invoices):
        return {
            'refund_method': 'refund',
            'reason': self.credit_note_reason,
            'date': self.credit_note_date,
            'journal_id': invoices.journal_id[:1].id,
        }

    def create_credit_note_for_order(self):
        order = self.sale_order_id
        rule = self.env['order.process.rule']._search_rule(order.channel_id, order)
        payment_gateways_info = rule._get_payment_gateway_mapping(order.payment_gateway_code)
        reversal_move = self.env['account.move'].create([{
            'move_type': 'out_refund',
            'partner_id': order.partner_id.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': False,
                'name': 'Refund',
                'account_id': payment_gateways_info['property_account_customer_deposit_id'],
                'quantity': 1,
                'price_unit': order.amount_total,
                'tax_ids': [(5, 0, 0)],
            })]
        }])
        return reversal_move

    def do_send_notification_email(self):
        if self.is_notification_email_enabled:
            self.send_notification_email()

    def send_notification_email(self):
        self.notification_email_template_id.send_mail(self.sale_order_id.id)
