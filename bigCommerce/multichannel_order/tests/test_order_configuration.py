# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from .common import ChannelOrderTestCommon, tagged
from unittest.mock import patch

@tagged('post_install', 'basic_test', '-at_install')
class TestOrderConfiguration(ChannelOrderTestCommon):
    
    def test_default_values(self):
        store = self.test_data['store_1']
        # Default Product
        fields = ['default_tax_product_id', 'default_discount_product_id', 'default_fee_product_id', 'default_shipping_cost_product_id',
                  'default_handling_cost_product_id', 'default_wrapping_cost_product_id']
        
        product_names = ['[Test Store] Tax', '[Test Store] Discount', '[Test Store] Fee', '[Test Store] Shipping Cost',
                        '[Test Store] Handling Cost', '[Test Store] Wrapping Cost']
        
        for field, product_name in zip(fields, product_names):
            self.assertEqual(store[field].name, product_name, f'{product_name} is not correctly !')
            self.assertFalse(store[field].sale_ok)
            self.assertEqual(store[field].invoice_policy, 'order')
            self.assertEqual(store[field].type, 'service')
            
        self.assertEqual(store.sales_team_id.name, store.name, 'Sales Team is not set correctly !')
        self.assertTrue(store.default_warehouse_id, 'Default Warehouse is not set correctly !')
        