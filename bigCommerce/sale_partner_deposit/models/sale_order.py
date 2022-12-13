# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DepositSalesOrder(models.Model):
    _inherit = 'sale.order'

    deposit_ids = fields.One2many('account.payment', 'sale_deposit_id', string='Deposits',
                                  domain=[('state', 'not in', ['draft', 'cancel'])])
    deposit_count = fields.Integer('Deposit Count', compute='_get_deposit_total', store=True)
    deposit_total = fields.Monetary(string='Total Deposit', compute='_get_deposit_total', store=True)
    remaining_total = fields.Monetary(string='Net Total', compute='_get_deposit_total', store=True)

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('amount_total', 'deposit_ids', 'deposit_ids.state')
    def _get_deposit_total(self):
        for order in self:
            deposit_total = sum(order.company_id.currency_id._convert(
                deposit.amount_total_signed,
                order.currency_id,
                order.company_id,
                deposit.date or fields.Date.today()
            ) for deposit in order.deposit_ids)

            order.update({
                'deposit_total': deposit_total,
                'deposit_count': len(order.deposit_ids),
                'remaining_total': order.amount_total - deposit_total,
            })

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def action_view_deposit(self):
        action = self.env['ir.actions.actions']._for_xml_id("account_partner_deposit.action_account_payment_customer_deposit")
        action['domain'] = [('id', 'in', self.deposit_ids.ids)]
        return action

    def action_cancel(self):
        """
        Override
        Unlink deposits when canceling SOs
        """
        res = super(DepositSalesOrder, self).action_cancel()
        for order in self.sudo().filtered(lambda x: x.state == 'cancel'):
            order.deposit_ids = [(5, 0, 0)]
        return res
