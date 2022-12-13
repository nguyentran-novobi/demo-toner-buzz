from odoo import models


class DepositOrder(models.TransientModel):
    _inherit = 'deposit.order'

    def create_deposit(self):
        res = super().create_deposit()
        active_model = self._context.get('active_model', False)
        if res and active_model == 'sale.order':
            context = res.get('context', {})
            context.update({
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_sale_deposit_id': self._context.get('active_id')
            })
            res['context'] = context
        return res
