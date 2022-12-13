# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, _
from odoo.tools import float_is_zero, float_repr

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def get_bigcommerce_tax_by_amount(self, tax_amount, company_id):
        """
            Using in BigCommerce Import Order process.
            In case the tax_amount is 0, return None
            In the opposite case:
                if we can find a tax whose name match with tax_amount, return that tax
                else create a new tax

        :param float tax_amount: The tax amount with match with tax name
        :param int company_id: The company that the tax should belong to
        :return:
        :rtype:
        """
        tax = self.env['account.tax']
        tax_amount = float(tax_amount)
        tax_amount_str = float_repr(tax_amount, precision_digits=4)
        if not tax_amount == 0:
            tax = self.search([
                ('name', '=', tax_amount_str),
                ('company_id', '=', company_id),
                ('type_tax_use', '=', 'sale'),
                ('tax_scope', '=', 'consu'),
            ], limit=1) \
                  or \
                  self.create({
                    'name': tax_amount_str,
                    'type_tax_use': 'sale',
                    'amount_type': 'fixed',
                    'tax_scope': 'consu',
                    'company_id': company_id,
                    'amount': tax_amount
                })
        return tax
