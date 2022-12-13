# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.addons.queue_job.exception import RetryableJobError


from .ftps_helper import FTPSHelper

import csv, io
import math
import datetime
import logging

_logger = logging.getLogger(__name__)


ERROR_MESSAGES = {
    'invalid_percentage': 'Please enter a percentage between 0.01% and 100.00%.',
    'invalid_maximum': 'Maximum must be greater than 0.',
    'invalid_minimum': 'Minimum must be at least 0.',
    'invalid_warehouses': 'There must be at least one active warehouse selected.',
}


class EcommerceChannel(models.Model):
    _inherit = 'ecommerce.channel'

    is_enable_inventory_sync = fields.Boolean(string='Enable Inventory Sync')
    is_allow_manual_bulk_inventory_sync = fields.Boolean(string='Allow Bulk Sync Manually')
    last_all_inventory_sync = fields.Datetime(string='Last all inventory updated')
    default_warehouse_id = fields.Many2one('stock.warehouse', string='Default Warehouse',
                                           help='This warehouse is used in doing fulfillment')
    active_warehouse_ids = fields.Many2many('stock.warehouse', string='Active Warehouses',
                                            domain="[('company_id', '=', company_id)]")
    percentage_inventory_sync = fields.Float(string='Percentage', default=100.0)
    is_enable_maximum_inventory_sync = fields.Boolean(string='Enable Maximum Quantity')
    is_enable_minimum_inventory_sync = fields.Boolean(string='Enable Minimum Quantity')
    maximum_inventory_sync = fields.Integer(string='Maximum Quantity')
    minimum_inventory_sync = fields.Integer(string='Minimum Quantity', default=0)
    is_running_bulk_inventory_sync = fields.Boolean(string='Running bulk inventory sync')
    exclude_inventory_sync_ids = fields.One2many('exclude.inventory.sync', 'channel_id', 'Exclude Products to Sync Inventory')

    # FTP Settings
    is_sync_by_ftp = fields.Boolean("Syncing by FTP Server")
    inventory_ftp_host = fields.Char('FTP Host')
    inventory_ftp_username = fields.Char('FTP Username')
    inventory_ftp_password = fields.Char('FTP Password')
    inventory_ftp_dir = fields.Char('FTP Directory')

    inventory_help_text = fields.Char(string='Inventory Help Text', compute='_compute_inventory_help_text')

    auto_export_shipment_to_store = fields.Boolean(string='Auto export shipment to store', default=True, 
                                                   help='Shipment will be updated automatically when it validated in Odoo')

    def _compute_inventory_help_text(self):
        for record in self:
            record.inventory_help_text = """Automatically update your available inventory quantities for products in this store"""

    def open_log_export_inventory(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'export_inventory')],
            'display_name': f'{self.name} - Logs - Inventory Export',
            'views': [
                (self.env.ref('omni_log.export_inventory_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.export_inventory_log_view_form').id, 'form')
            ]
        })
        return action

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        warehouses = self.env['stock.warehouse'].sudo().search([('company_id.id', '=', self.company_id.id)])
        default.update({
            'active_warehouse_ids': [(4, wh_id) for wh_id in warehouses.ids],
            'percentage_inventory_sync': 100.0,
            'default_warehouse_id': warehouses[0].id
        })
        return super(EcommerceChannel, self).copy(default)

    @api.onchange('company_id')
    def onchange_company(self):
        warehouses = self.env['stock.warehouse'].sudo().search([('company_id.id', '=', self.company_id.id)])
        return {
            'value': {
                'active_warehouse_ids': [(6, 0, warehouses.ids)],
                'default_warehouse_id': False
            },
            'domain': {'default_warehouse_id': [('id', 'in', self.active_warehouse_ids.ids)]}
        }

    @api.onchange('active_warehouse_ids')
    def onchange_active_warehouse(self):
        res = {'domain': {'default_warehouse_id': [('id', 'in', self.active_warehouse_ids.ids)]}}
        if self.default_warehouse_id.id not in self.active_warehouse_ids.ids:
            res.update({'value': {'default_warehouse_id': False}})
        return res

    @api.onchange('percentage_inventory_sync')
    def onchange_percentage_inventory_sync(self):
        if not (0.01 <= self.percentage_inventory_sync <= 100.0):
            return dict(warning=dict(title=_('Invalid Quantity Sync'), message=_(ERROR_MESSAGES['invalid_percentage'])))

    @api.onchange('maximum_inventory_sync', 'is_enable_maximum_inventory_sync')
    def onchange_maximum_inventory_sync(self):
        if not self.is_enable_maximum_inventory_sync:
            self.maximum_inventory_sync = False
        else:
            if self.maximum_inventory_sync and self.maximum_inventory_sync < 1:
                return dict(warning=dict(title=_('Invalid Maximum Quantity'), message=_(ERROR_MESSAGES['invalid_maximum'])))

    @api.onchange('minimum_inventory_sync', 'is_enable_minimum_inventory_sync')
    def onchange_minimum_inventory_sync(self):
        if not self.is_enable_minimum_inventory_sync:
            self.minimum_inventory_sync = False
        else:
            if self.minimum_inventory_sync and self.minimum_inventory_sync < 0:
                return dict(warning=dict(title=_('Invalid Minimum Quantity'), message=_(ERROR_MESSAGES['invalid_minimum'])))

    @api.constrains('percentage_inventory_sync')
    def check_percentage_inventory_sync(self):
        if not all(0.01 <= r.percentage_inventory_sync <= 100.0 for r in self):
            raise ValidationError(_(ERROR_MESSAGES['invalid_percentage']))

    @api.constrains('is_enable_maximum_inventory_sync', 'maximum_inventory_sync')
    def check_maximum_inventory_sync(self):
        if any(r.is_enable_maximum_inventory_sync and r.maximum_inventory_sync < 1 for r in self):
            raise ValidationError(_(ERROR_MESSAGES['invalid_maximum']))

    @api.constrains('is_enable_minimum_inventory_sync', 'minimum_inventory_sync')
    def check_minimum_inventory_sync(self):
        if any(r.is_enable_minimum_inventory_sync and r.minimum_inventory_sync < 0 for r in self):
            raise ValidationError(_(ERROR_MESSAGES['invalid_minimum']))

    @api.constrains('is_enable_inventory_sync', 'active_warehouse_ids')
    def check_active_warehouses(self):
        if any(r.is_enable_inventory_sync and len(r.active_warehouse_ids) < 1 and r.is_enable_inventory_sync for r in self):
            raise ValidationError(_(ERROR_MESSAGES['invalid_warehouses']))

    @api.constrains('maximum_inventory_sync', 'minimum_inventory_sync')
    def check_maximumn_minimum_inventory_sync(self):
        if any(r.minimum_inventory_sync >= r.maximum_inventory_sync
               and r.maximum_inventory_sync and r.minimum_inventory_sync for r in self):
            raise ValidationError(_('Minimum must be less than maximum.'))

    def _get_syncing_warehouses(self):
        self.ensure_one()
        return self.active_warehouse_ids

    def _compute_available_qty(self, available, mapping_quantity=1):
        percentage_inventory_sync = self.percentage_inventory_sync
        maximum_inventory_sync = self.maximum_inventory_sync
        minimum_inventory_sync = self.minimum_inventory_sync

        available = (available / mapping_quantity) * (percentage_inventory_sync/100.0)

        #
        # Comparing maximum and minimum will depend on setting
        #
        if available > maximum_inventory_sync and self.is_enable_maximum_inventory_sync:
            available = maximum_inventory_sync
        elif available < minimum_inventory_sync and self.is_enable_minimum_inventory_sync:
            available = minimum_inventory_sync
        available = math.floor(available)

        return available

    def write_error_inventory_sync(self, id_on_channel, error):
        self.ensure_one()
        product = self.env['product.channel'].sudo().search([('id_on_channel', '=', id_on_channel),
                                                             ('channel_id.id', '=', self.id)])
        if product:
            product.message_post(body=_('Having errors in inventory sync: <br/>%s') % error)

    def done_inventory_sync(self, uuids):
        """
        Data Inventory Sync is completed.
        This is used for pushing notification
        :param uuids:
        :return:
        """
        self.ensure_one()
        records = self.env['queue.job'].sudo().search([('uuid', 'in', uuids), ('state', 'in', ['done', 'failed'])])
        if len(records) != len(uuids):
            raise RetryableJobError('Must be retried later')

        self.sudo().write({'is_running_bulk_inventory_sync': False})

    def _generate_exclude_domain(self):
        self.ensure_one()
        domain = []
        for rule in self.exclude_inventory_sync_ids:
            if rule.applied_on == '2_product_category':
                domain = expression.AND([domain, [
                    '!', ('categ_id.id', 'child_of', rule.categ_ids.ids)
                ]])
            elif rule.applied_on == '1_product':
                domain = expression.AND([domain, [
                    ('product_tmpl_id.id', 'not in', rule.product_tmpl_ids.ids)
                ]])
            elif rule.applied_on == '0_product_variant':
                domain = expression.AND([domain, [
                    ('id', 'not in', rule.product_product_ids.ids)
                ]])
        return domain

    def update_inventory(self, exported_products, bulk_sync=False):
        """
        Update available qty to channel
        """
        self.ensure_one()
        self = self.sudo()
        custom_method_name = '_%s_update_inventory' % self.platform
        uuids = []
        if hasattr(self, custom_method_name):
            if bulk_sync:
                product_channel_variants = self.env['product.channel.variant'].\
                    sudo().search([('channel_id.id', '=', self.id),
                                   ('id_on_channel', '!=', False),
                                   ('inventory_tracking', '=', True),
                                   ('product_product_id', 'not in', exported_products.ids),
                                   ('product_product_id', '!=', False)])
                exported_products |= product_channel_variants.mapped('product_product_id')

            exclude_domain = self._generate_exclude_domain()
            if exclude_domain:
                exported_products = exported_products.filtered_domain(exclude_domain)
            context = self.env.context
            uuids = getattr(self.with_context(**context), custom_method_name)(exported_products=exported_products)

            if bulk_sync and not self.env.context.get('no_delay'):
                if uuids:
                    self.with_delay(priority=12, max_retries=100).done_inventory_sync(uuids=uuids)
                else:
                    self.write({'is_running_bulk_inventory_sync': False})
            else:
                self.write({'is_running_bulk_inventory_sync': False})
        return uuids

    @api.model
    def _bulk_sync(self, channel_id):
        self.env['stock.move'].inventory_sync(channel_id=channel_id, all_records=True)

    def bulk_inventory_sync(self):
        self.ensure_one()
        self = self.sudo()
        if not self.active:
            raise UserError(_('Your channel has been disconnected. Please contact your administrator.'))

        if self.is_running_bulk_inventory_sync:
            raise UserError(_('Inventory Syncing is running.'))

        if not self.is_enable_inventory_sync:
            raise UserError(_('Bulk inventory sync cannot do now, please make sure the inventory sync is enabled.'))

        self.write({
            'last_all_inventory_sync': fields.Datetime.now(),
            'is_running_bulk_inventory_sync': True,
            'warning_message': False
        })
        try:
            self.with_delay(eta=5)._bulk_sync(self.id)
        except Exception as e:
            raise ValidationError(e)

    def sync_inventory_ftp(self, data):
        self.ensure_one()
        if data:
            credentials = {
                'host': self.inventory_ftp_host or '',
                'username': self.inventory_ftp_username or '',
                'password': self.inventory_ftp_password or '',
                'base_path': self.inventory_ftp_dir or '',
            }

            headers = data[0].keys()
            with FTPSHelper(**credentials) as ftps_helper:
                with io.StringIO() as w_file:
                    writer = csv.writer(w_file, dialect='excel', delimiter=',')
                    writer.writerow(headers)
                    writer.writerows([d.values() for d in data])
                    content = w_file.getvalue()
                    content = content.encode('utf-8')

                    today = datetime.datetime.now().strftime("%Y%m%d%H%M")
                    file_name = f"inventory{today}.csv"
                    ftps_helper.send_file('', io.BytesIO(content), file_name)

    def write(self, vals):
        for record in self:
            if any(field in vals for field in ['percentage_inventory_sync', 'maximum_inventory_sync',
                                               'minimum_inventory_sync', 'active_warehouse_ids']) \
                    and record.is_enable_inventory_sync:

                vals['warning_message'] = 'Changes will be applied in the next inventory sync. ' \
                                          'You can sync manually to update immediately.'

        return super(EcommerceChannel, self).write(vals)

    def open_shipping_method_channel_list(self):
        self.ensure_one()
        self.ensure_operating()

        xml_id = 'multichannel_fulfillment.action_shipping_method_channel'
        action = self.env["ir.actions.actions"]._for_xml_id(xml_id)
        context = self.env.context.copy()
        context['default_channel_id'] = self.id
        context['active_test'] = True
        if self.platform:
            context.update(include_platform=True)
        action.update({
            'name': _('%s - Shipping Carrier Mappings', self.name),
            'display_name': _('%s - Shipping Carrier Mappings', self.name),
            'domain': [('channel_id', '=', self.id)],
            'context': context
        })
        return action
