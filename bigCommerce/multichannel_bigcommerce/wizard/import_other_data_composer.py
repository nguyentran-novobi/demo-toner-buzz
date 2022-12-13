# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class ImportOtherData(models.TransientModel):
    """
    This wizard is used to import other data manually
    """
    _inherit = 'import.other.data'

    bc_category_operation_type = fields.Selection([
        ('all', 'Import all'),
    ], string='Operation', default='all')
    is_bc_category = fields.Boolean('Data Type ID', compute='_compute_is_bc_category')

    @api.depends('data_type_id')
    def _compute_is_bc_category(self):
        for record in self:
            if record.data_type_id.id == self.env.ref('multichannel_bigcommerce.channel_category_data_type').id:
                record.is_bc_category = True
            else:
                record.is_bc_category = False

    def _is_all_records(self):
        res = super()._is_all_records()
        if self.data_type_id.id == self.env.ref('multichannel_bigcommerce.channel_category_data_type').id:
            res = True
        return res
