# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class ImportOrderOperation(models.TransientModel):
    """
    This wizard is used to import orders manually
    """
    _name = 'import.order.operation'
    _description = 'Import Order Manually'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    order_ids = fields.Text(string='Order IDs')
    operation_type = fields.Selection([
        ('by_time_range', 'Import orders by creation date'),
        ('by_ids', 'Import orders by IDs'),
    ], string='Operation')
    from_date = fields.Datetime(string='From Date', compute='_get_time_range', store=True, readonly=False)
    to_date = fields.Datetime(string='To Date', default=fields.Datetime.now,
                              compute='_get_time_range', store=True, readonly=False)
    help_text = fields.Text(compute='_compute_help_text')

    def _get_help_text(self):
        return ''

    @api.depends('channel_id')
    def _compute_help_text(self):
        self.help_text = self._get_help_text()

    @api.depends('operation_type')
    def _get_time_range(self):
        if self.operation_type == 'by_time_range':
            self.from_date = self.channel_id.last_sync_order
            self.to_date = fields.Datetime.now()
        else:
            self.from_date = False
            self.to_date = False

    @api.constrains('from_date', 'to_date')
    def _validate_time_range(self):
        for record in self:
            if record.operation_type == 'by_time_range' and record.from_date > record.to_date:
                raise ValidationError(_('To Date must be after From Date'))

    def run(self):
        self.ensure_one()
        method_name = '{}_get_data'.format(self.channel_id.platform)
        sale_order_model = self.env['sale.order'].sudo()
        if hasattr(sale_order_model, method_name):
            ids = self.order_ids.split(',') if self.order_ids else []
            obj = sale_order_model.with_context(manual_import=True).with_delay()
            method = getattr(obj, method_name)
            method(channel_id=self.channel_id.id, ids=ids, from_date=self.from_date, to_date=self.to_date)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification!'),
                'message': _('Orders are importing....'),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
