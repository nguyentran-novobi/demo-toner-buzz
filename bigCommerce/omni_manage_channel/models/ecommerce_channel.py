# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import logging
import re

from operator import itemgetter
from itertools import groupby
from datetime import datetime, timedelta
from dateutil import parser

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import formatLang
from odoo.exceptions import ValidationError, UserError

from odoo.addons.queue_job.exception import RetryableJobError

_logger = logging.getLogger(__name__)

STEP = {
    1: 'credentials',
    2: 'sync_data',
    3: 'set_warehouse',
    4: 'completed'
}
SEQUENCE_STEP = {
    'credentials': 1,
    'sync_data': 2,
    'set_warehouse': 3,
    'completed': 4
}

MAX_RECORDS = {
    'product.template': 'ob.max_synched_products',
    'customer.channel': 'ob.max_synched_customers',
    'sale.order': 'ob.max_synched_orders'
}


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def format_value(self, value, currency=False):
        currency_id = currency or self.env.user.company_id.currency_id
        if self.env.context.get('no_format'):
            return currency_id.round(value)
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        res = formatLang(self.env, value, currency_obj=currency_id)
        return res

class EcommerceChannel(models.Model):
    _name = "ecommerce.channel"
    _description = "eCommerce Channel"
    
    @api.model
    def _default_measure_unit(self):
        return self.env['uom.uom'].search([('name', '=', 'inch(es)')], limit=1).id

    name = fields.Char(string='Name', required=True, copy=False)
    logo_and_name = fields.Char(compute='_get_logo_and_name')
    platform = fields.Selection(selection=[],
                                string='Platform',
                                readonly=False,
                                required=False)
    managed_listing_level = fields.Selection(selection=[
        ('none', 'None'),
        ('template', 'Template'),
        ('variant', 'Variant'),
    ], compute='_compute_managed_listing_level', search='_search_managed_listing_level')
    image_url = fields.Char(compute='_get_image_url', store=True)
    secure_url = fields.Char(string='URL', help='Store’s current HTTPS URL', readonly=False)
    oauth_version = fields.Selection([('1.0', 'OAuth 1.0'),
                                      ('2.0', 'OAuth 2.0')], default='2.0', string='OAuth Version')

    app_client_id = fields.Char(string='Client ID')
    app_client_secret = fields.Char(string='Client Secret')
    api_version = fields.Char(string='API Version')
    redirect_uri = fields.Char(string='Redirect URI')

    active = fields.Boolean(string='Active', default=True, copy=False)

    status = fields.Selection([('connected', 'Connected'), ('disconnected', 'Disconnected')],
                              help='Connection status with channel', default='connected', compute='_get_status',
                              inverse='_set_status')
    is_sync = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string='Sync Data')
    is_in_syncing = fields.Boolean(string='Is in syncing', default=False, readonly=False)
    measure_unit = fields.Many2one('uom.uom', default=_default_measure_unit)

    last_sync_product = fields.Datetime(string='Last Sync', readonly=True)
    last_option_sync_product = fields.Selection([
        ('last_sync', 'Last Sync'),
        ('visible_products', 'Visible Products'),
        ('all_products', 'All Products'),
        ('all_active_products', 'All Active Products'),
        ('time_range', 'Time Range'),
        ('product_ids', 'Product IDs'),
    ], readonly=True)
    done_job_uuid = fields.Char(readonly=True)
    last_sync_order = fields.Datetime(string='Last Order Sync', readonly=False, default=fields.Datetime.now)
    min_order_date_created = fields.Datetime(string='Minimum date the order was created',
                                             help='Only get order created after this time')
    admin_email = fields.Char(string='Username', readonly=False, copy=False)

    debug_logging = fields.Boolean('Debug logging', default=False, help='Log requests in order to ease debugging')

    image = fields.Binary(
        "Image", attachment=True,
        help="This field holds the image used for this provider, limited to 1024x1024px")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        help="Medium-sized image of this provider. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved. "
             "Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        help="Small-sized image of this provider. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    state = fields.Selection([('sync_data', 'Sync Data'),
                              ('set_warehouse', 'Set Warehouse'),
                              ('completed', 'Completed')], default='sync_data', string='State')

    show_order_states = fields.Boolean(string='Show Orders Mapping States', store=True)
    use_odoo_shipment = fields.Boolean(string='Use Odoo Shipment', default=True,
                                       help='True: Create shipments and process them in Odoo \nFalse: Will not create shipments in Odoo and sync shipments from eCommerce channel instead')

    menu_listing_id = fields.Many2one('ir.ui.menu', readonly=True)
    menu_order_id = fields.Many2one('ir.ui.menu', readonly=True)

    is_default_channel = fields.Boolean(string='Default Channel',
                                        default=False,
                                        help='This channel will be set as default when creating sales order')

    company_id = fields.Many2one('res.company', "Company",
                                 readonly=True,
                                 default=lambda self: self.env.company, required=False)

    kanban_dashboard = fields.Text(compute='_kanban_dashboard')
    show_on_dashboard = fields.Boolean(string='Show journal on dashboard',
                                       help="Whether this journal should be displayed on the dashboard or not",
                                       default=True)
    color = fields.Integer("Color Index", default=0)

    warning_message = fields.Text(string='Warning Message', readonly=True)

    weight_unit = fields.Selection([('oz', 'Ounce(s)'),
                                    ('lb', 'Pound(s)'),
                                    ('g', 'Gram(s)'),
                                    ('kg', 'Kilogram(s)'),
                                    ('t', 'Tonne(s)')], string='Weight Measurement', default='lb')

    dimension_unit = fields.Selection([('in', 'Inch(es)'),
                                       ('cm', 'Centimeter(s)'),
                                       ('m', 'Meter(s)'),
                                       ('mm', 'Millimeter(s)'),
                                       ('yd', 'Yard(s)')], string='Length Measurement', default='in')

    environment = fields.Selection([('sandbox', 'Sandbox'),
                                    ('production', 'Production')], string='Environment', default='production')

    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    currency_ids = fields.Many2many('res.currency', string='Currencies',
                                    help='All currencies supported by this store')

    def _get_logo_and_name(self):
        for record in self:
            if record.platform:
                record.logo_and_name = json.dumps({
                    'name': record.name,
                    'img_src': '/omni_manage_channel/static/src/img/%s.png' % record.platform
                })
            else:
                record.logo_and_name = json.dumps({'name': record.name})

    def _compute_managed_listing_level(self):
        for record in self:
            method_name = '_%s_managed_listing_level' % record.platform
            record.managed_listing_level = getattr(record, method_name, 'none')

    def _search_managed_listing_level(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise ValueError('Invalid operator: %s' % (operator,))
        op = 'in' if operator == '=' else 'not in'
        managed_listing_levels = list()
        for p in map(itemgetter(0), self._fields['platform'].selection):
            method_name = '_%s_managed_listing_level' % p
            managed_listing_levels.append((getattr(self, method_name, 'none'), p))

        leveled_platforms = dict()
        for level, plats in groupby(sorted(managed_listing_levels, key=itemgetter(0)), key=itemgetter(0)):
            leveled_platforms[level] = list(map(itemgetter(1), plats))

        return [('platform', op, leveled_platforms.get(value, []))]

    def check_connection(self):
        self.ensure_one()
        cust_method_name = '_%s_check_connection' % self.platform
        if hasattr(self, cust_method_name):
            return getattr(self, cust_method_name)()
        return True

    def button_check_connection(self):
        response = self.check_connection()
        if not response:
            raise ValidationError(_('Invalid credentials, please verify that you type the correct info and try again.'))
        return response

    def _get_status(self):
        for record in self:
            record.with_context(for_channel_creation=True).status = 'connected' if record.active else 'disconnected'

    def _set_status(self):
        for record in self:
            record.with_context(for_channel_creation=True).active = False if record.status == 'disconnected' else True

    def _get_menus(self):
        self.ensure_one()
        menus = self.with_context(active_test=False).menu_listing_id + self.with_context(active_test=False).menu_order_id
        return menus

    def reconnect(self):
        self.ensure_one()
        if self.check_connection():
            self._get_menus().sudo().write({'active': True})
            action = self.env["ir.actions.actions"]._for_xml_id('omni_manage_channel.action_channel_overview')
            action['target'] = 'main'
            # Update last sync order after re-connecting
            self.sudo().write({'active': True, 'last_sync_order': fields.Datetime.now()})
            # TODO Need to discuss about data of channel after reconnected
            return action
        else:
            raise ValidationError(_("Cannot reconnect. "
                                    "You can reach out to our support team by email at support_omniborder@novobi.com."))

    def disconnect(self):
        self.ensure_one()
        self._get_menus().sudo().write({'active': False})
        action = self.env["ir.actions.actions"]._for_xml_id('omni_manage_channel.action_channel_overview')
        action['target'] = 'main'
        self.sudo().write({'active': False})
        return action

    @api.depends('platform')
    def _get_image_url(self):
        for record in self:
            record.image_url = '/omni_manage_channel/static/src/img/%s.png' % record.platform

    @api.onchange('options_sync_data_ids')
    def _onchange_options_sync_data_ids(self):
        self.show_order_states = False
        options = self.options_sync_data_ids.filtered(lambda o: o.model == 'sale.order')
        if options:
            self.show_order_states = True

    def button_close(self):
        self.ensure_one()
        self = self.sudo()
        cron_job = self.env.ref('multichannel_order.check_new_orders')
        if (self.is_sync == 'No' or not self.is_sync) and not cron_job.active:
            nextcall = fields.Datetime.now() + timedelta(minutes=5)
            cron_job.sudo().write({'nextcall': nextcall, 'active': True})

        action = self.env["ir.actions.actions"]._for_xml_id('omni_manage_channel.action_channel_overview')
        action['target'] = 'main'
        return action

    def button_next(self):
        self.ensure_one()
        seq_current_step = SEQUENCE_STEP[self.state]
        next_step = STEP[seq_current_step + 1]
        self.state = next_step

    def button_back(self):
        self.ensure_one()
        seq_current_step = SEQUENCE_STEP[self.state]
        prev_step = STEP[seq_current_step - 1]
        self.state = prev_step

    def button_finish(self, models=None):
        self.ensure_one()
        self.state = 'completed'
        uuid = None
        if self.options_sync_data_ids:
            uuid = self.with_delay().run_sync_data(models=models)
            self.is_in_syncing = True
        else:
            cron_job = self.env.ref('multichannel_order.check_new_orders')
            if not cron_job.active:
                nextcall = fields.Datetime.now() + timedelta(minutes=1)
                cron_job.sudo().write({'nextcall': nextcall, 'active': True})
        return uuid

    def open_onboarding(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'action.onboarding',
            'target': 'fullscreen',
            'context': {
                'params': {
                    'id': self.id,
                }
            }
        }

    def open_settings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('omni_manage_channel.action_ecommerce_channel_setting')
        action['res_id'] = self.id
        if self.platform:
            action['context'] = {'include_platform': True,
                                 'only_active_menu': True,
                                 'default_channel_id': self.id}
            form_view = self.env.ref('omni_manage_channel.view_ecommerce_channel_form_settings')
            action.update({
                'views': [(form_view.id, 'form')],
                'view_id': form_view.id
            })
            action['display_name'] = self.name
        return action

    def close_import_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('omni_manage_channel.action_channel_overview')
        action['target'] = 'main'
        return action

    @api.model
    def _run_import_product(self, channel_id, update_last_sync_product=True, auto_create_master=True, **criteria):
        channel = self.sudo().browse(channel_id)
        cust_method_name = '%s_get_data' % channel.platform
        if hasattr(self.env['product.template'], cust_method_name):
            method = getattr(self.env['product.template'], cust_method_name)
            data, uuids = method(
                channel_id=channel.id,
                **criteria,
                auto_create_master=auto_create_master,
            )
            if uuids:
                uuid = self.with_delay(priority=12, max_retries=100).done_synching(
                    uuids=uuids,
                    update_last_sync_product=update_last_sync_product
                ).uuid
                channel.sudo().write({
                    'done_job_uuid': uuid
                })
                return uuid
        # When can not get data from channel
        channel.sudo().write({'is_in_syncing': False})
        return None

    def import_product(self, option, auto_create_master=None, criteria=None):
        def build_criteria(cri):
            if 'date_modified_str' in cri:
                cri['date_modified'] = parser.parse(cri['date_modified_str'])
                del cri['date_modified_str']
            if 'to_date_str' in cri:
                cri['to_date'] = parser.parse(cri['to_date_str'])
                del cri['to_date_str']
            if option in ['last_sync', 'last_published']:
                if self.last_sync_product:
                    cri['date_modified'] = self.last_sync_product
            elif option == 'visible_products':
                cri['is_visible'] = True
            return cri

        def check_update_last_sync_product_allowed():
            return option in ['last_sync', 'last_published', 'visible_products', 'all_products']

        self.ensure_one()
        self = self.sudo()
        if not self.check_operating():
            return False
        criteria = build_criteria(criteria or {})
        self.with_delay()._run_import_product(
            channel_id=self.id,
            auto_create_master=auto_create_master,
            update_last_sync_product=check_update_last_sync_product_allowed(),
            **criteria,
        )
        self.update({
            'is_in_syncing': True,
            'last_option_sync_product': option,
        })
        return True

    def is_importing_done(self):
        self.ensure_one()
        if not self.check_operating():
            return {'success': False, 'error': True}
        if self.done_job_uuid:
            record = self.env['queue.job'].sudo().search([('uuid', '=', self.done_job_uuid)], limit=1)
            if record.state == 'done':
                return {'success': True, 'error': False}
            elif record.state == 'failed':
                return {'success': False, 'error': True}
            else:
                return {'success': False, 'error': False}
        elif self.is_in_syncing:
            return {'success': False, 'error': False}
        else:
            return {'success': True, 'error': False}

    def open_notification(self):
        return {
            'context': self._context,
            'res_model': 'ecommerce.channel',
            'target': 'current',
            'name': 'Finish',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'views': [[self.env.ref('omni_manage_channel.view_ecommerce_channel_form_setting').id, 'form']],
        }

    def get_credentials(self):
        self.ensure_one()
        cust_method_name = '%s_credentials' % self.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            return method()
        return True

    def sync_data(self, args=None):
        self.ensure_one()
        cust_method_name = '%s_sync_data' % self.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            return method(args)
        return True

    def get_thumbnail(self):
        self.ensure_one()
        cust_method_name = '%s_get_thumbnail' % self.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            return method()
        return True

    @api.model
    def _done_synching(self, model, uuids):
        """
        Done Synchronization is completed on each model
        :param model:
        :param uuids:
        :return:
        """
        ids = []
        records = self.env['queue.job'].sudo().search([('uuid', 'in', uuids), ('state', 'in', ['done', 'failed'])])
        if len(records) != len(uuids):
            raise RetryableJobError('Must be retried later')
        for record in records:
            if ids:
                ids.extend(safe_eval(record.result))
        if ids:
            objects = self.env[model].sudo().browse(ids)
            _logger.info("Done")
            _logger.info(len(objects))

    def get_data(self, model, id_on_channel=None):
        self.ensure_one()
        cust_method_name = '%s_get_data' % self.platform
        if hasattr(self.env[model], cust_method_name):
            method = getattr(self.env[model], cust_method_name)
            if model == 'product.template':
                data, uuids = method(channel_id=self.id,
                                     id_on_channel=id_on_channel,
                                     sync_inventory=True,
                                     all_records=True)
            else:
                data, uuids = method(channel_id=self.id,
                                     id_on_channel=id_on_channel,
                                     all_records=True)

            if uuids:
                return self.with_delay(priority=30, max_retries=15)._done_synching(model, uuids).uuid
        return None

    def mapping_data(self, model, vals):
        self.ensure_one()
        cust_method_name = '%s_mapping_data' % self.platform
        if hasattr(self.env[model], cust_method_name):
            method = getattr(self.env[model], cust_method_name)
            return method(vals)
        return True

    @api.model
    def _check_dependence(self, uuids, update_last_sync_product=False):
        records = self.env['queue.job'].sudo().search([('uuid', 'in', uuids), ('state', 'in', ['done', 'failed'])])
        if len(records) != len(uuids):
            raise RetryableJobError('Must be retried later')
        uuids = []
        uuids.append(self.get_data("sale.order"))
        return self.with_delay(priority=50, max_retries=100)\
            .done_synching(uuids=uuids, update_last_sync_product=update_last_sync_product).uuid

    def run_sync_data(self, models=None):
        self.ensure_one()
        models = models or (self.options_sync_data_ids and self.options_sync_data_ids.mapped('model'))
        uuids = []
        update_last_sync_product = True if "product.template" in models else False
        if "sale.order" in models:
            for m in ["product.template", "customer.channel"]:
                uuid = self.get_data(m)
                if uuid is not None:
                    uuids.append(uuid)
            uuid = self.with_delay(priority=30, max_retries=100)._check_dependence(
                uuids=uuids,
                update_last_sync_product=update_last_sync_product,
            )
        else:
            for m in models:
                uuid = self.get_data(m)
                if uuid is not None:
                    uuids.append(uuid)
            uuid = self.with_delay(priority=50, max_retries=100).done_synching(
                uuids=uuids,
                update_last_sync_product=update_last_sync_product,
            ).uuid
        return uuid

    def done_synching(self, uuids, update_last_sync_product=False):
        """
        Data Synchronization is completed.
        This is used for pushing notification
        :param uuids:
        :return:
        """
        self.ensure_one()
        records = self.env['queue.job'].sudo().search([('uuid', 'in', uuids), ('state', 'in', ['done', 'failed'])])
        if len(records) != len(uuids):
            raise RetryableJobError('Retry job in done_syncing (omni_manage_channel) ')

        vals = {'is_in_syncing': False, 'done_job_uuid': False}

        if update_last_sync_product:
            vals['last_sync_product'] = records[0].date_created if records else fields.Datetime.now()

        self.update(vals)

        # Activate schedule action
        cron_job = self.env.ref('multichannel_order.check_new_orders')
        if not cron_job.active:
            nextcall = fields.Datetime.now() + timedelta(minutes=5)
            cron_job.sudo().write({'nextcall': nextcall, 'active': True})
        return True

    def name_get(self):
        res = []
        for ec in self:
            if ec.platform and 'include_platform' in self.env.context:
                res.append((ec.id, "[%s] %s" % (ec.platform.upper(), ec.name)))
            else:
                res.append((ec.id, ec.name))
        return res

    @api.model
    def check_new_orders(self, eta=None, channel_id=False):
        """
        Run schedule action for getting new orders on Channel
        :return:
        """
        channels = self.sudo().search([('platform', '!=', 'none')])
        if channel_id:
            channels = self.sudo().browse(channel_id)
        for channel in channels:
            self.env['sale.order'].channel_import_order(channel)

    @api.model
    def update_inventory_quantity(self):
        ir_params_sudo = self.env['ir.config_parameter'].sudo()
        last_sync_inventory = ir_params_sudo.get_param('ob.last_sync_inventory') or fields.Datetime.now()
        updated_stock_lines = self.env['stock.move.line'].sudo().search([('write_date', '>=', last_sync_inventory)])
        products = updated_stock_lines.mapped('product_id')
        self.env.cr.execute("UPDATE ir_config_parameter SET value = '%s' WHERE key = 'ob.last_sync_inventory'"
                            % fields.Datetime.to_string(fields.Datetime.now()))

        for product in products:
            product.product_channel_variant_ids.with_delay(priority=1)._update_inventory(product.qty_available)
            self._cr.commit()

    def _kanban_dashboard(self):
        for record in self:
            record.kanban_dashboard = json.dumps(record.get_dashboard_datas())

    def get_dashboard_datas(self):
        self.ensure_one()
        last_30_days = datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=30)

        query = """
            SELECT COALESCE(COUNT(o.id), 0) AS unit,
                  COALESCE(SUM(o.amount_total), 0) AS total
            FROM sale_order AS o
            WHERE o.date_order >= %s
              AND o.channel_id = %s
              AND o.state IN ('sale', 'done')
        """

        self.env.cr.execute(query, (last_30_days, self.id))
        query_result = self.env.cr.dictfetchall()
        result = {'sales_unit': 0, 'sales_total': 0}
        if query_result:
            result.update({'sales_unit': query_result[0]['unit'], 'sales_total': query_result[0]['total']})
        result['sales_total'] = self.company_id.currency_id.format_value(result['sales_total'])
        return result

    def unlink(self):
        if any(self.filtered(lambda c: c.check_operating())):
            raise UserError(_('You cannot delete channel when it is connected'))
        return super(EcommerceChannel, self).unlink()

    def toggle_debug_logging(self):
        for record in self:
            record.debug_logging = not record.debug_logging

    def check_operating(self):
        """
        Check the active status of this channel.
        Since the active is being checked. The caller may need to turn
        the active test context up in order to read this record.
        """
        self.ensure_one()
        return self.active

    def ensure_operating(self):
        """
        Check and raise error if the channel is disconnected
        This is for checking before starting connection to the channel
        """
        self.ensure_one()
        if not self.check_operating():
            raise UserError(_('Your channel has been disconnected. Please contact your administrator.'))

    @api.model
    def format_debug_json(self, message):
        def recursive_trim_list(array):
            for i, v in enumerate(array):
                if isinstance(v, str):
                    if len(v) > 75 and (len(re.findall(r"[\s.,]", v)) / len(v)) < 0.05:
                        array[i] = v[:72] + '...'
                    elif len(v) > 300:
                        array[i] = v[:297] + '...'
                else:
                    recursive_trim(v)

        def recursive_trim_dict(dictionary):
            for k, v in dictionary.items():
                if isinstance(v, str):
                    if len(v) > 75 and (len(re.findall(r"[\s.,]", v)) / len(v)) < 0.05:
                        dictionary[k] = v[:72] + '...'
                    elif len(v) > 300:
                        dictionary[k] = v[:297] + '...'
                else:
                    recursive_trim(v)

        def recursive_trim(data):
            if isinstance(data, dict):
                recursive_trim_dict(data)
            elif isinstance(data, list):
                recursive_trim_list(data)

        try:
            content = str(message, 'utf-8')
        except TypeError:
            content = message

        try:
            json_data = json.loads(content)
        except json.decoder.JSONDecodeError:
            json_data = dict(content=content)
        recursive_trim(json_data)
        content = json.dumps(json_data, indent=2)
        return content

    def _get_product_exported_fields(self):
        return None

    def _get_setting(self, setting):
        SETTINGS = {
            'manage_images': ('field', 'manage_images'),
            'product_exported_fields': ('function', '_get_product_exported_fields'),
            'product_merged_fields': ('function', '_get_product_merged_fields'),
            'auto_create_master_product': ('field', 'auto_create_master_product'),
            'order_configuration': ('function', '_get_order_configuration'),
            'manage_mapping': ('field', 'is_mapping_managed'),
        }
        setting_type, setting_attr = SETTINGS[setting]
        if setting_type == 'function':
            value = getattr(self, setting_attr)()
        else:
            value = getattr(self, setting_attr)
        return value

    def get_setting(self, setting):
        return self._get_setting(setting)

    def _get_base_log_action(self):
        action = self.env["ir.actions.actions"]._for_xml_id('omni_log.action_omni_log')
        action.update({
            'context': {
                'include_platform': True,
                'search_default_draft': 1,
                'search_default_failed': 1,
                'search_default_unresolved': 1,
            },
            'target': 'current',
        })
        return action

    def refresh_currencies(self):
        self.ensure_one()
        cust_method_name = '_%s_refresh_currencies' % self.platform
        if hasattr(self, cust_method_name):
            return getattr(self, cust_method_name)()
        return True
