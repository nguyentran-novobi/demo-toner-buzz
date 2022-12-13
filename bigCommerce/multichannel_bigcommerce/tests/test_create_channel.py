# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json

from unittest.mock import Mock, patch

from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import BigCommerceHelper
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceCreateChannel(BigCommerceTestCommon):
    
    def test_product_exported_fields(self):
        """
        Default all product exported fields will be checked after channel created
        """
        bigcommerce_channel = self.bigcommerce_channel_1
        input_vals = bigcommerce_channel.get_setting('product_exported_fields')
        output_vals = {
            'master_template': ['name', 'sku', 'weight', 'width', 'length', 'depth', 'height', 'mpn',
                                'price', 'retail_price', 'type', 'upc', 'gtin', 'brand_id', 'images',
                                'description', 'inventory_tracking'],
            'master_variant': ['price', 'sku', 'weight', 'width', 'length', 'depth', 'height', 'mpn', 'upc', 
                               'retail_price', 'image_url', 'option_values'],
            'mapping_template': ['id', 'categories', 'sale_price', 'bin_picking_number', 
                                 'tax_class_id', 'product_tax_code', 'is_featured', 'sort_order',
                                 'fixed_cost_shipping_price', 'is_free_shipping', 'order_quantity_minimum',
                                 'order_quantity_maximum', 'purchasing_disabled', 'is_visible'],
            'mapping_variant': ['id', 'sale_price', 'fixed_cost_shipping_price', 'is_free_shipping', 
                                'bin_picking_number', 'purchasing_disabled']
        }
        
        self.assertTrue(all(key in input_vals['master_template'] for key in output_vals['master_template']))
        self.assertTrue(all(key in input_vals['master_variant'] for key in output_vals['master_variant']))
        self.assertTrue(all(key in input_vals['mapping_template'] for key in output_vals['mapping_template']))
        self.assertTrue(all(key in input_vals['mapping_variant'] for key in output_vals['mapping_variant']))
        
    def test_default_order_process_rules(self):
        """
        Default order process rules
        """
        bigcommerce_channel = self.bigcommerce_channel_1
        
        journal = self.env['account.journal'].sudo().search([('type', 'in', ['bank', 'cash'])], limit=1)
        payment_method = journal.inbound_payment_method_ids[0] if journal.inbound_payment_method_ids else self.env.ref('account.account_payment_method_manual_in')
        
        deposit_account = self.env['account.account'].search([('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
                                                                ('deprecated', '=', False), 
                                                                ('code', '=', '111400'),
                                                                ('reconcile', '=', True)], limit=1)
        if not deposit_account:
            deposit_account = self.env['account.account'].search([('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
                                                                ('deprecated', '=', False), 
                                                                ('reconcile', '=', True)], limit=1)
            
        self.assertEqual(len(bigcommerce_channel.order_process_rule_ids), 1)
        default_setting = bigcommerce_channel.order_process_rule_ids[0]
        
        self.assertRecordValues(bigcommerce_channel.order_process_rule_ids, [{
            'name': 'Default',
            'is_order_confirmed': True,
            'is_invoice_created': True,
            'is_payment_created': True,
            'payment_journal_id': journal.id,
            'payment_method_id': payment_method.id,
            'deposit_account_id': deposit_account.id
        }])
        
        self.assertRecordValues(default_setting.order_status_channel_ids, [{
            'name': 'Awaiting Fulfillment'
        }])


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceSettings(BigCommerceTestCommon):
    def test_refresh_currencies(self):
        with open(get_data_path(__file__, 'data/bigcommerce_get_currencies.json'), 'r') as fp:
            res_json = json.load(fp)

        channel = self.bigcommerce_channel_1
        all_testing_currencies = self.env.ref('base.USD') | self.env.ref('base.EUR') | self.env.ref('base.CAD')
        all_testing_currencies.write({'active': True})

        default_currency = self.env.ref('base.CAD')
        channel.write({
            'currency_id': default_currency.id,
            'currency_ids': [(6, 0, default_currency.ids)],
        })

        api = BigCommerceHelper.connect_with_channel(channel)
        all_response = api.currencies.create_collection_with(res_json)
        mock_connect = Mock(return_value=Mock(currencies=Mock(all=Mock(return_value=all_response))))

        with patch.object(BigCommerceHelper, 'connect_with_channel', mock_connect):
            channel.refresh_currencies()

        self.assertEqual(channel.currency_id, self.env.ref('base.USD'))
        self.assertEqual(channel.currency_ids, self.env.ref('base.USD') | self.env.ref('base.EUR'))
