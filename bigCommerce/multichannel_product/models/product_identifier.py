# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductIdentifierType(models.Model):
    _name = 'product.identifier.type'
    _description = 'Type for Product Identifier in Channel'

    product_identifier_ids = fields.One2many('product.identifier', 'type_id', string="Product Identifier")
    name = fields.Char(string="Type", help="Value for type of product identifier type")


class ProductIdentifier(models.Model):
    _name = 'product.identifier'
    _description = 'Product Identifiers in channel: UPC, EAN, GTIN, ISBN'

    product_tmpl_id = fields.Many2one('product.template', 'Product Template', readonly=True)
    product_product_id = fields.Many2one('product.product', 'Product Variant', readonly=True)
    type_id = fields.Many2one('product.identifier.type', "Type", required=True)
    value = fields.Char("Value")

    @api.constrains('value')
    def check_upc_ean(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.value and record.value != '' and record.type_id.name == 'UPC' and (not record.value.isdigit() or len(record.value) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12 or 13 numbers.'))
                if record.value and record.value != '' and record.type_id.name == 'EAN' and (not record.value.isdigit() or len(record.value) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12, or 13 numbers.'))
                if record.value and record.value != '' and record.type_id.name == 'GTIN' and (not record.value.isdigit() or len(record.value) not in [8, 12, 13, 14]):
                    raise ValidationError(
                        _('Global Trade Number must be numeric and have a length of 8, 12, 13 or 14 numbers.'))
