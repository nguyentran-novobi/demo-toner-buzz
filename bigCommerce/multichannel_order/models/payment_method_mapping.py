from odoo import fields, models, api, _


class PaymentMethodMapping(models.Model):
    _name = 'payment.method.mapping'
    _description = 'Payment Method Mapping'

    sequence = fields.Integer(string='Sequence')
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True, ondelete='cascade', change_default=True)
    payment_gateway_id = fields.Many2one('channel.payment.gateway', string='Payment Gateway', ondelete='cascade', required=True,
                                         domain=[('channel_id', '=', channel_id)])

    payment_journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True,
                                         domain="[('type', 'in', ['bank', 'cash'])]")
    payment_method_id = fields.Many2one('account.payment.method',
                                        string='Payment Method',
                                        readonly=False,
                                        store=True,
                                        required=True,
                                        compute='_compute_payment_method_id',
                                        domain="[('id', 'in', available_payment_method_ids)]")

    deposit_account_id = fields.Many2one(
        'account.account',
        string='Deposit Account',
        required=True,
        domain=lambda self: [
            ('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
            ('deprecated', '=', False),
            ('reconcile', '=', True),
        ])

    available_payment_method_ids = fields.Many2many(
        'account.payment.method', compute='_compute_payment_method_fields')

    @api.depends('payment_journal_id')
    def _compute_payment_method_fields(self):
        for record in self:
            available_payment_methods = record.payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            record.available_payment_method_ids = available_payment_methods

    @api.depends('payment_journal_id')
    def _compute_payment_method_id(self):
        for record in self:
            available_payment_method_ids = record.payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            if available_payment_method_ids:
                record.payment_method_id = available_payment_method_ids[0]._origin
            else:
                record.payment_method_id = False

    @api.onchange('payment_journal_id')
    def onchange_payment_journal(self):
        if self.payment_journal_id:
            inbound_payment_methods = self.payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            return {
                'domain': {'payment_method_id': [('id', 'in', inbound_payment_methods.ids)]},
                'value': {'payment_method_id': inbound_payment_methods[:1].id},
            }
        else:
            self.payment_method_id = False
