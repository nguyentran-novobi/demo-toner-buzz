# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def create_account_tax_in_sale_order(self, tax_values):
        """
        Create Account Tax for order
        :param tax_values: a dict has
        key: tax_name:
        value: a dict has key 'rate' and 'amount'
        :return:
        """

        names = list(tax_values.keys())
        records = self.sudo().search([('name', 'in', names),
                                      ('amount_type', '=', 'percent'),
                                      ('type_tax_use', '=', 'sale')])

        new_records = list(filter(lambda e: e not in records.mapped('name'), names))
        if new_records:
            vals = []
            for e in new_records:
                if tax_values[e]['rate'] > 0:
                    vals.append({'name': e,
                                  'amount_type': 'percent',
                                  'type_tax_use': 'sale',
                                  'amount': tax_values[e]['rate']})
                else:
                    vals.append({'name': e,
                                 'amount_type': 'fixed',
                                 'type_tax_use': 'sale',
                                 'amount': tax_values[e]['amount']})
            records += self.sudo().with_context(check_duplicated=True).create(vals)
            self.env.cr.commit()
        vals_list = []
        for record in records:
            vals_list.append({
                'associated_account_tax_id': record.id,
                'name': record.name,
                'amount': tax_values[record.name]['amount']
            })
        return vals_list