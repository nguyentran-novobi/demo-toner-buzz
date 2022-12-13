# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

NOTIFICATION_MESSAGE = {
    'Category': 'Categories',
    'Customer Group': 'Customer Groups',
    'Price List': 'Price Lists',
}

class ImportOtherData(models.TransientModel):
    """
    This wizard is used to import other data manually
    """
    _name = 'import.other.data'
    _description = 'Import Other Data Manually'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    platform = fields.Selection(related='channel_id.platform', string="Platform")
    ids_on_channel = fields.Text(string='IDs')
    data_type_id = fields.Many2one('channel.data.type', string='Data Type', required=True)
    operation_type = fields.Selection([
        ('by_ids', 'Import by IDs'),
        ('all', 'Import all'),
    ], string='Operation', default='by_ids')
    help_text = fields.Text(compute='_compute_help_text')

    @api.depends('channel_id', 'data_type_id')
    def _compute_help_text(self):
        self.help_text = self._get_help_text()

    def _get_help_text(self):
        data_type = self.data_type_id.name or ''
        return f'Please enter {data_type} IDs on the online store,' \
               f' using commas to separate between values. E.g. 100,101'

    def _is_all_records(self):
        return True if self.operation_type == 'all' else False

    def run(self):
        self.ensure_one()
        ids = self.ids_on_channel.split(',') if self.ids_on_channel else []
        all_records = self._is_all_records()
        self.data_type_id.channel_import_others(self.channel_id, ids=ids, all_records=all_records)

        message = f"{NOTIFICATION_MESSAGE[self.data_type_id.name]} are importing...."
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification!'),
                'message': _(message),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
