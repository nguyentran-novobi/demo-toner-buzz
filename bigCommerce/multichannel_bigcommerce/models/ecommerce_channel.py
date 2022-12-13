# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import requests
from itertools import groupby
from time import sleep
from operator import attrgetter, itemgetter

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..utils.bigcommerce_api_helper import BigCommerceHelper
from ..utils.bigcommerce_payment_gateway_helper import BigcommercePaymentGatewayHelper, BigCommercePaymentGatewayImporter, BigcommercePaymentGatewayImportBuilder

TYPE2MODEL = {
    'order': 'sale.order',
    'shipment': 'sale.order',
    'product': 'product.template',
    'customer': 'res.partner',
    'sku': 'product.product'
}

_logger = logging.getLogger(__name__)

BIGCOMMERCE_IMPORTED_FIELDS = [
    'Name',
    'Images',
    'Product Type',
    'Categories',
    'SKU',
    'Brand',
    'Default Price',
    'MSRP (Retail Price)',
    'Sale Price',
    'Manufacturer Part Number (MPN)',
    'Product UPC/EAN',
    'Global Trade Number (GTN)',
    'Bin Picking Number (BPN)',
    'Description',
    'Variants',
    'Variant Options',
    'Featured Product',
    'Sort Order',
    'Fixed Shipping Price',
    'Free Shipping',
    'Dimension & Weight',
    'Minimum Purchase Quantity',
    'Maximum Purchase Quantity',
    'Tax Class',
    'Tax Provider Tax Code',
    'Low Stock',
    'Bulk Pricing Rules',
    'Search Keywords',
    'Availability Text',
    'Warranty Information',
    'Condition',
    'Custom Fields',
    'Related Products',
    'Purchasability',
    'Preorder Message',
    'Preorder Release Date',
    'Search Engine Optimization',
    'Open Graph Sharing',
]


class BigCommerceChannel(models.Model):
    _inherit = "ecommerce.channel"
    _bigcommerce_managed_listing_level = 'template'

    platform = fields.Selection(selection_add=[('bigcommerce', 'BigCommerce')])

    bc_access_token = fields.Char(string='BigCommerce Access Token')
    bc_store_hash = fields.Char(string='BigCommerce Store Hash', index=True)

    manage_taxes_on_order_lines = fields.Boolean(default=False)

    @api.model
    def _bigcommerce_check_connection(self):
        bc_store_hash, headers = self.bigcommerce_generate_url_header()
        url = 'https://api.bigcommerce.com/stores/%s/v2/store' % bc_store_hash
        response = requests.get(url=url, headers=headers)
        if response.status_code == 200:
            return {
                'effect': {
                    'type': 'rainbow_man',
                    'message': _("Everything is correctly set up !"),
                }
            }
        return False

    def open_import_product(self):
        action = super(BigCommerceChannel, self).open_import_product()
        if self.platform == 'bigcommerce':
            product_ids_option_note = 'Please enter BigCommerce product IDs, using commas to separate between values.' \
                                      ' E.g. 314600,314611'
            action['context'].update({
                'options': ['last_sync', 'visible_products', 'all_products', 'time_range', 'product_ids'],
                'fields': BIGCOMMERCE_IMPORTED_FIELDS,
                'product_ids_option_note': product_ids_option_note,
            })
        return action

    @api.model
    def bigcommerce_get_mapping_views(self):
        parent = self.env.ref('multichannel_bigcommerce.menu_bigcommerce_listings')
        tree_view = self.env.ref('multichannel_product.view_product_channel_tree')
        form_view = self.env.ref('multichannel_bigcommerce.view_bigcommerce_product_channel_form')
        view_ids = [
            (5, 0, 0),
            (0, 0, {'view_mode': 'tree', 'view_id': tree_view.id}),
            (0, 0, {'view_mode': 'form', 'view_id': form_view.id}),
        ]
        return parent, view_ids

    @api.model
    def bigcommerce_get_order_views(self):
        parent = self.env.ref('multichannel_bigcommerce.menu_bigcommerce_orders')
        tree_view = self.env.ref('multichannel_order.view_all_store_orders_tree')
        form_view = self.env.ref('multichannel_order.view_store_order_form_omni_manage_channel_inherit')
        view_ids = [
            (5, 0, 0),
            (0, 0, {'view_mode': 'tree', 'view_id': tree_view.id}),
            (0, 0, {'view_mode': 'form', 'view_id': form_view.id}),
        ]
        return parent, view_ids
    
    @api.model
    def bigcommerce_check_request_limit(self, response):
        _logger.info("Rate-Limit-Requests-Left: %s" % response.headers['X-Rate-Limit-Requests-Left'])
        remaining_request = int(response.headers['X-Rate-Limit-Requests-Left'])
        if remaining_request == 10:
            _logger.info("Sleep in %s" % response.headers['X-Rate-Limit-Time-Reset-Ms']/1000)
            time_reset = int(response.headers['X-Rate-Limit-Time-Reset-Ms'])
            sleep(time_reset / 1000)
        return True

    @api.model
    def bigcommerce_new_connection(self, params=None):
        client_action = {
            'type': 'ir.actions.act_url',
            'name': "Connect new store",
            'target': 'new',
            'url': 'https://apps.bigcommerce.com/details/17298',
        }
        return client_action

    def bigcommerce_credentials(self, params=None):
        self.ensure_one()
        return {
            'client_id': self.app_client_id,
            'client_secret': self.app_client_secret,
            'bc_access_token': self.bc_access_token,
            'bc_store_hash': self.bc_store_hash
        }
        
    def bigcommerce_generate_url_header(self):
        self.ensure_one()
        credentials = self.bigcommerce_credentials()
        client_id = credentials['client_id']
        bc_access_token = credentials['bc_access_token']
        bc_store_hash = credentials['bc_store_hash']

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Token': bc_access_token,
            'X-Auth-Client': client_id
        }

        return bc_store_hash, headers

    def _bigcommerce_prepare_exported_inventory_data(self, products):
        data_sync = []
        for product_tmpl, g in groupby(sorted(products, key=lambda p: p.product_channel_tmpl_id.id), key=lambda r: r.product_channel_tmpl_id):
            variants = self.env['product.channel.variant'].concat(*list(g))
            res = []
            for variant in variants.filtered(lambda r: r.id_on_channel):
                res.append({'id': int(variant.id_on_channel), 'inventory_level': int(variant.free_qty)})
            #
            # Products have to track inventory on variant level if using inventory management in OB
            #
            if res:
                if not product_tmpl.attribute_line_ids:
                    data_sync.append({
                        'id': int(product_tmpl.id_on_channel),
                        'inventory_tracking': 'product',
                        'inventory_level': int(res[0]['inventory_level']),
                        'res_id': product_tmpl.id
                    })
                else:
                    data_sync.append({
                        'id': int(product_tmpl.id_on_channel),
                        'inventory_tracking': 'variant',
                        'variants': res,
                        'res_id': product_tmpl.id
                    })
        return data_sync

    def _bigcommerce_update_inventory(self, exported_products):
        self.ensure_one()
        domain = [
            ('channel_id', '=', self.id),
            ('id_on_channel', '!=', False),
            ('inventory_tracking', '=', True),
            ('product_product_id', 'in', exported_products.ids)
        ]
        
        products = self.env['product.channel.variant'].sudo().search(domain)
        data_sync = self._bigcommerce_prepare_exported_inventory_data(products)

        uuids = []
        if data_sync:
            # BigCommerce only allows to sync 10 products per request
            def divide_chunks():
                for i in range(0, len(data_sync), 9):
                    yield data_sync[i:i + 9]

            for data in divide_chunks():
                res_ids = ','.join([str(e.pop('res_id')) for e in data])
                log = self.env['omni.log'].create({
                    'datas': {'data': data},
                    'res_ids': res_ids,
                    'res_model': 'product.channel',
                    'channel_id': self.id,
                    'operation_type': 'export_inventory'
                })
                job_uuid = self.with_context(log_id=log.id).with_delay(max_retries=15)\
                    ._bigcommerce_sync_inventory(data).uuid
                uuids.append(job_uuid)
                log.update({'job_uuid': job_uuid})
        return uuids

    def _bigcommerce_sync_inventory(self, data_sync):
        self.ensure_one()
        helper = BigCommerceHelper.connect_with_channel(channel=self)
        res = helper.products.put_batch(data_sync)
        errors = []

        def _update_inventory_variant():
            for variant in row['variants']:
                variant_obj = helper.product_variants.acknowledge(variant['id'], product_id=row['id'])
                variant_obj.data = {'inventory_level': variant['inventory_level']}
                variant_obj.put_one()

        if res.last_response.ok():
            for row in list(filter(lambda r: r['inventory_tracking'] == 'variant', data_sync)):
                _update_inventory_variant()

        elif res.last_response.status_code in [404, 422]:
            for row in data_sync:
                data = {'inventory_tracking': 'variant'}
                if row['inventory_tracking'] == 'product':
                    data = {'inventory_tracking': 'product', 'inventory_level': row['inventory_level']}
                product_obj = helper.products.acknowledge(row['id'])
                product_obj.data = data
                res = product_obj.put_one()
                if res.last_response.ok():
                    if row['inventory_tracking'] == 'variant':
                        _update_inventory_variant()
                else:
                    errors.append(res.last_response.content)
        else:
            errors.append(res.last_response.content)

        if errors:
            raise ValidationError(" - ".join(str(e) for e in errors))

    def open_product_brands(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_product.action_channel_brand_name')
        action.update({
            'context': {'include_platform': True},
            'target': 'main',
            'display_name': '%s - Brands' % self.name
        })
        return action

    def open_tax_classes(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_bigcommerce.action_tax_class')
        action.update({
            'context': {'include_platform': True},
            'target': 'main',
            'domain': [('channel_id.id', '=', self.id)],
            'display_name': '%s - Tax Classes' % self.name
        })
        return action

    def open_channel_pricelist(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_bigcommerce.action_channel_pricelist')
        action.update({
            'context': {
                'include_platform': True,
                'default_channel_id': self.id,
            },
            'target': 'main',
            'domain': [('channel_id', '=', self.id)],
            'display_name': '%s - Price Lists' % self.name
        })
        return action
    
    @api.model
    def bigcommerce_get_store_settings(self, bc_store_hash, headers):
        try:
            url = 'https://api.bigcommerce.com/stores/%s/v2/store' % bc_store_hash
            response = requests.get(url=url, headers=headers)
            if response.status_code != 200:
                raise ValidationError(_('Invalid credentials, please verify that you type the correct info and try again.'))
            json_response = response.json()
            weight_units = json_response['weight_units']
            dimension_units = json_response['dimension_units']

            weight_unit = 'oz'
            dimension_unit = 'in'

            if weight_units == 'Pounds':
                weight_unit = 'lb'
            elif weight_units == 'Kilograms':
                weight_unit = 'kg'
            elif weight_units == 'Grams':
                weight_unit = 'g'
            elif weight_units == 'Tonnes':
                weight_unit = 't'

            if dimension_units == 'Centimeters':
                dimension_unit = 'cm'

            json_response.update({
                'weight_unit': weight_unit,
                'dimension_unit': dimension_unit
            })
        except Exception:
            raise ValidationError(_('Invalid credentials, please verify that you type the correct info and try again.'))
        return json_response

    def _bigcommerce_get_listing_value(self):
        self.ensure_one()
        # Get brand
        self.env['brand.channel'].with_context(for_synching=True).bigcommerce_get_data(self.id)

        # Get Tax
        self.env['tax.class'].with_context(for_synching=True).bigcommerce_get_data(self.id)

        # Get categories on BigCommerce
        self.env['product.channel.category'].with_context(for_synching=True).bigcommerce_get_data(self.id)
        
        # Set Default Category
        default_categ = self.env['product.channel.category'].search([('channel_id.id', '=', self.id), 
                                                                     ('parent_id', '=', False)], limit=1)
        self.write({'default_categ_id': default_categ.id})
        
    @api.model
    def create(self, vals):
        if vals['platform'] == 'bigcommerce':
            settings = self._bigcommerce_get_default_settings(vals)
            settings.update(self._bigcommerce_get_store_currency_vals(vals))
            vals.update(settings)

        record = super(BigCommerceChannel, self).create(vals)

        if record.bc_access_token and record.platform == 'bigcommerce':
            record._bigcommerce_get_listing_value()
            record.action_refresh_payment_gateway_list()
        return record

    def _bigcommerce_get_default_settings(self, vals):
        access_token = vals.get('bc_access_token') or self.bc_access_token
        client_id = vals.get('app_client_id') or self.app_client_id
        store_hash = vals.get('bc_store_hash') or self.bc_store_hash
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Token': access_token,
            'X-Auth-Client': client_id,
        }
        json_response = self.bigcommerce_get_store_settings(store_hash, headers)
        return {
            'admin_email': json_response['admin_email'],
            'secure_url': json_response['secure_url'],
            'weight_unit': json_response['weight_unit'],
            'dimension_unit': json_response['dimension_unit'],
            'can_export_pricelist_from_master': True,
        }

    def _bigcommerce_get_store_currency_vals(self, vals=None):
        def prepare_helper():
            if vals is None:
                return BigCommerceHelper.connect_with_channel(self)
            return BigCommerceHelper.connect_with_dict({
                'store_hash': vals.get('bc_store_hash'),
                'access_token': vals.get('bc_access_token'),
            })

        def fetch_store_currencies():
            helper = prepare_helper()
            return helper.currencies.all()

        def extract_all_and_default_currency_code(currency_res):
            currency_data = list(map(attrgetter('data'), currency_res))
            get_code = itemgetter('currency_code')
            all_codes = list(map(get_code, currency_data))
            default_code = get_code(next(filter(lambda cd: cd['is_default'] is True, currency_data)))
            return all_codes, default_code

        res = fetch_store_currencies()
        if res:
            currency_codes, default_currency_code = extract_all_and_default_currency_code(res)
            currencies = self.env['res.currency'].search([('name', 'in', currency_codes)])
            default_currency = currencies.filtered(lambda c: c.name == default_currency_code)[:1]
            return {
                'currency_id': default_currency.id,
                'currency_ids': [(6, 0, currencies.ids)],
            }
        return {}

    def write(self, vals):
        credential_fields = ['app_client_id', 'bc_access_token', 'bc_store_hash']
        for record in self:
            if record.platform == 'bigcommerce' and any(field in credential_fields for field in vals):
                settings = record._bigcommerce_get_default_settings(vals)
                vals.update(settings)

        return super(BigCommerceChannel, self).write(vals)

    def bigcommerce_get_listing_form_view_action(self, res_id):

        return {
            'context': self._context,
            'res_model': 'product.channel',
            'target': 'current',
            'name': _('BigCommerce Listing'),
            'res_id': res_id,
            'type': 'ir.actions.act_window',
            'views': [[self.env.ref('multichannel_bigcommerce.view_bigcommerce_product_channel_form').id, 'form']],
        }
    
    @api.model
    def bigcommerce_get_default_order_statuses(self):
        return self.env.ref('multichannel_bigcommerce.bigcommerce_order_status_awaiting_fulfillment')

    def _create_or_update_payment_gateways(self, payment_gateways):
        existed_records = self.env['channel.payment.gateway'].sudo().search([('channel_id', '=', self.id)])

        if not payment_gateways:
            existed_records.sudo().filtered(lambda r: r.id_on_channel).unlink()
            return True

        new_payment_gateways = []
        for payment_gateway in payment_gateways:
            record = existed_records.filtered(lambda r: r.code == payment_gateway['code'])
            if record:
                record.update(payment_gateway)
            else:
                new_payment_gateways.append(payment_gateway)

        removed_payment_gateways = existed_records.filtered(lambda r: r.id_on_channel and r.code not in [p['code'] for p in payment_gateways])
        removed_payment_gateways.sudo().unlink()
        self.env['channel.payment.gateway'].create(new_payment_gateways)

        return True

    def action_refresh_payment_gateway_list(self):
        self.ensure_one()
        channel = self

        def prepare_importer():
            res = BigCommercePaymentGatewayImporter()
            res.channel = channel
            res.all_records = True
            return res

        def prepare_builder(payment_gateways):
            res = BigcommercePaymentGatewayImportBuilder()
            res.payment_gateways = payment_gateways
            res.channel_id = channel
            return res

        def fetch_payment_gateway(gen):
            while True:
                try:
                    payment_gateway = next(gen)
                    yield payment_gateway
                except StopIteration:
                    break

        datas = []
        importer = prepare_importer()

        for pulled in importer.do_import():
            if pulled.data:
                builder = prepare_builder(pulled.data)
                vals_list = list(fetch_payment_gateway(builder.prepare()))
                datas.extend(vals_list)

        if datas:
            for data in datas:
                data.update({'channel_id': channel.id})
            self._create_or_update_payment_gateways(datas)

        return True

    def _bigcommerce_refresh_currencies(self):
        vals = self._bigcommerce_get_store_currency_vals()
        self.update(vals)

    def is_bigcommerce_manage_taxes_on_order_lines(self):
        return self.platform == 'bigcommerce' and self.manage_taxes_on_order_lines
