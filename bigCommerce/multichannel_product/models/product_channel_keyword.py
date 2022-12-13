# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ProductChannelKeyword(models.Model):
    _name = 'product.channel.keyword'
    _description = "Product Channel Keywords "

    name = fields.Char(string='Name', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = self.env['product.channel.keyword']
        if 'check_duplicated' in self.env.context:
            records += self.search([('name', 'in', list(map(lambda e: e['name'], vals_list)))])

        new_vals = vals_list
        if records:
            existed_names = records.mapped('name')
            new_vals = list(filter(lambda e: e['name'] not in existed_names, vals_list))

        records += super(ProductChannelKeyword, self).create(new_vals)

        return records

