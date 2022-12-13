# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model_create_multi
    def create(self, vals_list):
        if 'check_duplicated' in self.env.context:
            tax_names = [c['name'] for c in vals_list]
            existing_record_ids = self.sudo().search([('name', 'in', tax_names)])
            existing_names = existing_record_ids.mapped('name')
            new_records = list(filter(lambda x: x['name'] not in existing_names, vals_list))
            new_record_ids = super(AccountTax, self).create(new_records)
            return existing_record_ids + new_record_ids

        return super(AccountTax, self).create(vals_list)
