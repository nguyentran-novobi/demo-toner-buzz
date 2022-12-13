from odoo import api, fields, models, _
from odoo.addons.queue_job.fields import JobSerialized
from odoo.exceptions import ValidationError
import json
import ast
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

FIELD_RECORD_IN_ODOO_BY_TYPE = {
    'import_product': 'product_mapping_id',
    'import_order': 'order_id',
    'import_shipment': 'shipment_id',
}

TYPE2METHOD = {
    'import_product': '_import_product',
    'import_order': '_import_order',
    'import_shipment': '_import_shipment',
    'import_others': '_import_others',
    'export_master': '_export_master',
    'export_mapping': '_export_mapping',
    'export_order': '_export_order',
    'export_inventory': '_export_inventory',
    'export_others': '_export_others',
}

TYPE2OBJ = {
    'import_product': ('Product', 'importing'),
    'import_order': ('Order', 'importing'),
    'import_shipment': ('Shipment', 'importing'),
    'import_others': ('Other Data', 'importing'),
    'export_master': ('Product', 'exporting'),
    'export_mapping': ('Product', 'exporting'),
    'export_order': ('Order', 'exporting'),
    'export_inventory': ('Inventory', 'exporting'),
    'export_others': ('Other Data', 'exporting')
}
class OmniLog(models.Model):
    _name = 'omni.log'
    _description = 'Omni Log'
    _rec_name = 'display_name'
    _order = 'create_date desc'

    display_name = fields.Char(string='Display Name', invisible=True, 
                               compute='_compute_display_name')
    channel_id = fields.Many2one('ecommerce.channel', string='Channel', readonly=True)
    datas = JobSerialized(readonly=True, base_type=dict)
    parent_res_model = fields.Char(string='Parent Resource Model', invisible=True, readonly=True)
    parent_res_id = fields.Many2oneReference('Parent Resource ID', model_field='parent_res_model',
                                             readonly=True, help="The record id this is attached to.")
    parent_ref = fields.Char(string='Parent Resource Ref', readonly=True)
    res_model = fields.Char(string='Resource Model', readonly=True)
    res_ids = fields.Char(string='Res IDs', readonly=True)
    res_id = fields.Many2oneReference('Resource ID', model_field='res_model',
                                      readonly=True, help="The record id this is attached to.")
    operation_type = fields.Selection([('import_product', 'Product Import'),
                                       ('import_order', 'Order Import'),
                                       ('import_shipment', 'Shipment Import'),
                                       ('import_others', 'Import Others'),
                                       ('export_master', 'Master Export'),
                                       ('export_mapping', 'Mapping Export'),
                                       ('export_order', 'Order Export'),
                                       ('export_inventory', 'Inventory Export'),
                                       ('export_others', 'Export Others')], string='Operation Type')

    job_uuid = fields.Char(string='Job UUID', translate=False)
    message = fields.Text(string='Message')
    message_display = fields.Text(compute='_compute_message_display')
    channel_record_id = fields.Char(string='ID on Store')
    status = fields.Selection([('draft', 'Draft'),
                               ('done', 'Success'),
                               ('failed', 'Failed')], string='Status', default='draft')

    datas_string = fields.Text(string='Datas', compute='_compute_datas_string')
    product_sku = fields.Char(string='Product SKU', readonly=True)
    product_mapping_id = fields.Many2one('product.channel', string='Product Mapping', readonly=True)
    order_id = fields.Many2one('sale.order', string='Order', readonly=True)
    shipment_id = fields.Many2one('stock.picking', string='Shipment', readonly=True)
    shipment_service_id = fields.Many2one('stock.service.picking', string='Service Shipment', readonly=True)
    entity_name = fields.Char(string='Entity Name', readonly=True)
    data_type_id = fields.Many2one('channel.data.type', string='Data Type')
    data_operation = fields.Selection([
        ('by_ids', 'Import by IDs'),
        ('all', 'Import All'),
    ], string='Operation', default='by_ids')

    is_resolved = fields.Boolean(string='Is Resolved', invisible=True, readonly=True, default=False)

    def _compute_display_name(self):
        res, res_lang_id = [], self.env['res.lang']._lang_get(self.env.user.lang)
        operations = dict(self._fields['operation_type'].selection)
        for record in self:
            operation = operations[record.operation_type]
            formatted_dt = record.create_date.strftime("%s %s" % (res_lang_id.date_format, res_lang_id.time_format))
            display_name = _('%s - %s (UTC)') % (operation, formatted_dt)
            record.display_name = display_name

    def _compute_message_display(self):
        for record in self:
            if record.message:
                record.message_display = f"...{record.message[-100:]}" if len(record.message) > 100 else record.message
            else:
                record.message_display = False

    @api.depends('datas')
    def _compute_datas_string(self):
        for record in self:
            datas = {}
            if record.datas:
                for key, val in record.datas.items():
                    val = '{!r}'.format(val)
                    try:
                        val = ast.literal_eval(val)
                    except (ValueError, SyntaxError):
                        pass
                    datas[key] = val
            record.datas_string = json.dumps(datas, indent=2)

    def update_status(self, status, message):
        self.ensure_one()
        vals = {}
        if self.channel_record_id:
            record = self.env[self.res_model].search([('id_on_channel', '=', self.channel_record_id),
                                                      ('channel_id.id', '=', self.channel_id.id)], limit=1)
            field_name = FIELD_RECORD_IN_ODOO_BY_TYPE[self.operation_type]
            if self.operation_type == 'import_shipment' and self.res_model == 'stock.service.picking':
                field_name = 'shipment_service_id'
                
            if status == 'done' and not record:
                _logger.error(f"Cannot find record for {self.operation_type} on record {self.channel_record_id}. Maybe there is another log created.")
                self.unlink()
                return
                
            vals.update({
                field_name: record.id,
                'res_id': record.id
            })
        vals.update({
            'status': status,
            'message': message
        })
        self.update(vals)

    def _import_product(self):
        auto_create_master = self.channel_id.get_setting('auto_create_master_product')
        self.env['ecommerce.channel']._run_import_product(channel_id=self.channel_id.id, 
                                                          update_last_sync_product=False,
                                                          ids_csv=self.channel_record_id,
                                                          auto_create_master=auto_create_master)

    def _import_order(self):
        method = '{}_get_data'.format(self.channel_id.platform)
        SaleOrder = self.env['sale.order'].sudo()
        if hasattr(SaleOrder, method):
            getattr(SaleOrder.with_delay(), method)(channel_id=self.channel_id.id,
                                                    ids=[self.channel_record_id])
        return True

    def _import_shipment(self):
        order = self.env[self.parent_res_model].browse(int(self.parent_res_id))
        order.with_delay().import_shipments(self.channel_record_id)

    def _import_others(self):
        ids_csv = self.channel_record_id or ''
        ids = list(filter(None, ids_csv.split(',')))
        all_records = True if self.data_operation == 'all' else False
        self.data_type_id.channel_import_others(channel=self.channel_id, ids=ids, all_records=all_records)

    def _export_master(self):
        self.env['export.product.composer'].create({
            'channel_id': self.channel_id.id
        }).with_context(active_ids=[int(self.res_id)]).export()

    def _export_mapping(self):
        self.product_mapping_id.with_delay(channel='root.synching', max_retries=15).export_from_mapping()

    def _export_order(self):
        id = self.res_id
        if id:
            self.env[self.res_model].channel_export_orders(channel=self.channel_id, ids=[id])

    def _export_inventory(self):
        ids = list(map(int, self.res_ids.split(',')))
        if self.res_model != 'product.product':
            records = self.env[self.res_model].browse(ids)
            if self.res_model == 'product.channel':
                # For Woo
                # For BigCommerce
                ids = records.mapped('product_variant_ids.product_product_id').ids
            elif self.res_model == 'product.channel.variant':
                # For Shopify
                ids = records.mapped('product_product_id').ids
        if ids:
            self.env['stock.move'].inventory_sync(channel_id=self.channel_id.id, 
                                                  product_product_ids=ids)

    def _export_others(self):
        ids = [self.res_id]
        if ids:
            self.data_type_id.channel_export_others(ids=ids)

    def run(self):
        for record in self:
            getattr(record, TYPE2METHOD[record.operation_type])()
        self.update({'is_resolved': True})
        obj, action = TYPE2OBJ[self[0].operation_type]
        if len(self) == 1 and 'no_back_menu' not in self.env.context:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Notification!'),
                    'message': _(f'{obj} is {action}....'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def toogle_resolved(self):
        self.ensure_one()
        self.update({'is_resolved': not self.is_resolved})

    def multi_import(self):
        operations = set(self.mapped('operation_type'))
        if any(key in operations for key in ['export_master', 'export_mapping', 'export_inventory']):
            raise ValidationError(_('You cannot re-import any entry from export log view'))
        statuses = set(self.mapped('status'))
        if any(status in statuses for status in ['draft', 'success']) or self.filtered(lambda r: r.is_resolved):
            raise ValidationError(_('This action only applies for failed logs which have not been resolved'))
        self.with_context(no_back_menu=True).run()

    def multi_export(self):
        operations = set(self.mapped('operation_type'))
        if any(key in operations for key in ['import_product', 'import_order', 'import_shipment']):
            raise ValidationError(_('You cannot re-export any entry from import log view'))
        statuses = set(self.mapped('status'))
        if any(status in statuses for status in ['draft', 'success']) or self.filtered(lambda r: r.is_resolved):
            raise ValidationError(_('This action only applies for failed logs which have not been resolved'))
        self.with_context(no_back_menu=True).run()

    def multi_resolved(self):
        statuses = set(self.mapped('status'))
        if any(status in statuses for status in ['draft', 'success']):
            raise ValidationError(_('This action only applies for failed logs which have not been resolved'))
        self.update({'is_resolved': True})

    def multi_unresolved(self):
        statuses = set(self.mapped('status'))
        if any(status in statuses for status in ['draft', 'success']):
            raise ValidationError(_('This action only applies for failed logs which have been resolved'))
        self.update({'is_resolved': False})

    @api.model
    def create(self, vals):
        if 'status' in vals and vals['status'] == 'done':
            vals['is_resolved'] = True
        record = super().create(vals)
        return record

    def write(self, vals):
        if 'status' in vals and vals['status'] == 'done':
            vals['is_resolved'] = True
        res = super().write(vals)
        return res

    @api.model
    def clear_successful_log(self):
        ir_params_sudo = self.env['ir.config_parameter'].sudo()
        days = int(ir_params_sudo.get_param('keep_log_in_days')) or 30
        deadline = datetime.today() - timedelta(days=days)
        successful_logs = self.search([("write_date", "<=", deadline), ("status", "=", 'done')], limit=500)
        if successful_logs:
            successful_logs.sudo().unlink()
        return True
