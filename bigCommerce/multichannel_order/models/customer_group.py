import psycopg2

from odoo import fields, models, api, _
from odoo.addons.queue_job.exception import RetryableJobError


class CustomerGroup(models.Model):
    _name = 'channel.customer.group'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Customer Group'

    name = fields.Char(string='Name', required=True)
    platform = fields.Selection(related='channel_id.platform')
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True, ondelete='cascade')
    id_on_channel = fields.Char(string='Id on Channel')
    is_exported_to_store = fields.Boolean(string='Exported to Store', compute='_compute_exported_to_store')
    need_to_export = fields.Boolean(string='Need to Export', readonly=True, copy=False)
    need_to_export_display = fields.Boolean(compute='_compute_need_to_export_display')

    _sql_constraints = [
        ('id_channel_uniq', 'unique(id_on_channel, channel_id)',
         'ID must be unique per channel!')
    ]

    @api.depends('id_on_channel', 'need_to_export')
    def _compute_need_to_export_display(self):
        enabled = self.filtered(lambda r: r.is_exported_to_store and r.need_to_export)
        enabled.update({'need_to_export_display': True})
        (self - enabled).update({'need_to_export_display': False})

    @api.depends('id_on_channel')
    def _compute_exported_to_store(self):
        for record in self:
            record.is_exported_to_store = True if record.id_on_channel else False

    @api.model
    def channel_import_data(self, channel, ids, all_records):
        method = '{}_get_data'.format(channel.platform)
        if hasattr(self, method):
            getattr(self, method)(channel.id, ids=ids, all_records=all_records)

    @api.model
    def create_jobs_for_synching(self, vals, update=False, record=False):
        """
        :param vals_list:
        :param channel_id:
        :return:
        """
        return self.with_delay()._sync_in_queue_job(vals, update, record).uuid

    @api.model
    def _sync_in_queue_job(self, vals, update, record):
        try:
            if update:
                record.with_context(for_synching=True).write(vals)
            else:
                self.with_context(for_synching=True).create(vals)
        except Exception as e:
            raise e

    def write(self, vals):
        if 'for_synching' not in self.env.context and 'need_to_export' not in vals:
            vals['need_to_export'] = True
        return super().write(vals)

    @api.model
    def channel_export_data(self, ids=[]):
        ids = ids or self.env.context.get('active_ids', [])
        customer_groups = self.env['channel.customer.group'].browse(ids)
        channel = customer_groups.mapped('channel_id')
        method = '{}_export_customer_groups'.format(channel.platform)
        if hasattr(customer_groups, method):
            getattr(customer_groups, method)()
