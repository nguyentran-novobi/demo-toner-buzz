# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, SUPERUSER_ID, _

_logger = logging.getLogger(__name__)


class ProductVendorChannel(models.Model):
    _name = 'product.channel.vendor'
    _description = 'Vendor'

    name = fields.Char(string='Name', required=True)

    _sql_constraints = [
        ('uniq_name', 'unique (name)',
         'This vendor already exists !')
    ]

    @api.model
    def create(self, vals):
        try:
            return super(ProductVendorChannel, self).create(vals)
        except Exception as e:
            if self.env.uid == SUPERUSER_ID:
                _logger.exception(str(e))
                self.env.cr.rollback()
                record = self.sudo().search([('name', '=', vals['name'])], limit=1)
                return record
            else:
                raise e

    @api.model
    def get_vendor(self, vendor_name):
        if vendor_name != '' and vendor_name:
            vendor = self.sudo().search([('name', '=', vendor_name)], limit=1)
            if not vendor:
                vendor = self.sudo().create({'name': vendor_name})
                self.env.cr.commit()
            return vendor
        return self