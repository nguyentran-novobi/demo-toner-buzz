from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ImportResourceOperation(models.TransientModel):
    """
    This wizard is used to import orders manually
    """
    _name = 'import.resource.operation'
    _description = 'Import Resource Manually'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    platform = fields.Selection(related='channel_id.platform')
    operation_type_id = fields.Many2one(
        'resource.import.operation.type',
        domain="[('platform', '=', platform)]",
    )
    operation_type = fields.Selection(related='operation_type_id.type')
    resource_type = fields.Selection(related='operation_type_id.resource')

    from_date = fields.Datetime(compute='_compute_time_range', store=True, readonly=False)
    to_date = fields.Datetime(compute='_compute_time_range', store=True, readonly=False)
    resource_ids_text = fields.Text('Resource IDs')
    resource_sku_text = fields.Text('Resource SKUs')

    is_auto_create_master = fields.Boolean(compute='_compute_auto_create_master', store=True, readonly=False)
    last_sync_product = fields.Datetime(related='channel_id.last_sync_product')

    @api.depends('channel_id')
    def _compute_auto_create_master(self):
        for record in self:
            record.is_auto_create_master = record.channel_id.auto_create_master_product

    @api.depends('operation_type_id')
    def _compute_time_range(self):
        if self.operation_type_id.type == 'time_range':
            self.from_date = self.channel_id.last_sync_product
            self.to_date = fields.Datetime.now()

    @api.constrains('operation_type_id')
    def _check_operation_type(self):
        if not all(record.operation_type_id for record in self):
            raise ValidationError(_('Operation is required'))

    @api.constrains('from_date', 'to_date')
    def _check_time_range(self):
        for record in self.filtered(lambda r: r.operation_type_id.type == 'time_range'):
            if record.from_date > record.to_date:
                raise ValidationError(_('To Date must be after From Date'))

    def run(self):
        self.ensure_one()

        self._initiate_importing_operation()
        return self._notify_operation()

    def _initiate_importing_operation(self):
        if self.resource_type == 'product':
            self._initiate_importing_product_operation()

    def _initiate_importing_product_operation(self):
        self.ensure_one()
        channel = self.channel_id.sudo()
        channel.ensure_operating()
        channel.with_delay()._run_import_product(
            channel_id=channel.id,
            auto_create_master=self.is_auto_create_master,
            update_last_sync_product=self.operation_type_id.is_update_last_sync,
            **self._build_product_import_criteria(),
        )
        channel.update({
            'is_in_syncing': True,
        })

    def _build_product_import_criteria(self):
        if self.operation_type == 'from_last_sync':
            if self.last_sync_product:
                criteria = {
                    'date_modified': self.last_sync_product,
                }
            else:
                criteria = {
                    'all_records': True,
                }
        elif self.operation_type == 'visible_or_active':
            criteria = {
                'is_visible': True,
            }
        elif self.operation_type == 'all':
            criteria = {
                'all_records': True,
            }
        elif self.operation_type == 'time_range':
            criteria = {
                'date_modified': self.from_date,
                'to_date': self.to_date,
            }
        elif self.operation_type == 'ids':
            criteria = {
                'ids_csv': self.resource_ids_text,
            }
        elif self.operation_type == 'sku':
            criteria = {
                'skus_csv': self.resource_sku_text,
            }
        else:
            raise UserError(_('Unsupported importing type: %s', self.operation_type))
        return criteria

    def _notify_operation(self):
        labels = {'product': 'Products'}
        resource_name = labels.get(self.resource_type)
        message = f'{resource_name} are importing....'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification!'),
                'message': _(message),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
