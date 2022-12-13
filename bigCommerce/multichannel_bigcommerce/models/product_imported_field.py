# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductImportedField(models.Model):
    _inherit = 'product.imported.field'

    platform = fields.Selection(selection_add=[('bigcommerce', 'BigCommerce')],
                                ondelete={'bigcommerce': 'set default'})
