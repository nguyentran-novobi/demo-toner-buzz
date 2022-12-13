# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json

from unittest.mock import patch, Mock

from odoo.addons.channel_base_sdk.utils.bigcommerce_api.resources.order import DataInTrans
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_order_helper import BigCommerceOrderImporter, BigCommerceOrderImportBuilder
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import BigCommerceHelper


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceSaleOrderGetData(BigCommerceTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_data_path(__file__, 'data/bigcommerce_get_order.json'), 'r') as fp:
            res_order_json = json.load(fp)
            in_transform = DataInTrans()
            transformed_order_datas = []
            for order in res_order_json:
                transformed_order_datas.append(in_transform(order))
            
        with open(get_data_path(__file__, 'data/bigcommerce_get_customer.json'), 'r') as fp:
            res_customer_json = json.load(fp)
            
        with open(get_data_path(__file__, 'data/bigcommerce_get_order_products.json'), 'r') as fp:
            res_order_products_json = json.load(fp)
            
        with open(get_data_path(__file__, 'data/bigcommerce_get_order_coupons.json'), 'r') as fp:
            res_order_coupons_json = json.load(fp)
            
        with open(get_data_path(__file__, 'data/bigcommerce_get_order_shipping_address.json'), 'r') as fp:
            res_order_shippping_address_json = json.load(fp)
        
        for order in transformed_order_datas:
            order.update({'customer_data': res_customer_json,
                          'products_data': res_order_products_json,
                          'coupons_data': res_order_coupons_json,
                          'shipping_addresses_data': res_order_shippping_address_json})   
        cls.transformed_orders = transformed_order_datas
        
    @patch('odoo.sql_db.Cursor.commit', autospec=True)
    def test_get_some_order(self, mock_commit):
        sale_order_model = self.env['sale.order']

        bigcommerce_channel = self.bigcommerce_channel_1
        api = BigCommerceHelper.connect_with_channel(bigcommerce_channel)
        imported_orders = api.orders.create_collection_with(self.transformed_orders)
        imported_orders.last_response = Mock(ok=Mock(return_value=True))

        with patch.object(type(bigcommerce_channel), 'disconnect', autospec=True) as mock_disconnect, \
                patch.object(BigCommerceOrderImporter, 'do_import', autospec=True) as mock_do_import, \
                patch.object(type(sale_order_model), 'create_jobs_for_synching', autospec=True) as mock_create_jobs:
            mock_do_import.return_value = imported_orders
            sale_order_model.bigcommerce_import_orders(bigcommerce_channel.id)
            mock_disconnect.assert_not_called()
            mock_create_jobs.assert_called()

        mock_commit.assert_called()
        
    def test_parse_order_data(self):      
        """
        Make sure that all the below keys will need to have after transform
        """ 
        primary_keys = ['customer_id', 'billing_address', 'shipping_address', 'id', 'channel_date_created',
                        'channel_order_ref', 'status_id', 'lines']
                
        fees_keys = ['discount_amount', 'coupons', 'shipping_cost', 'handling_cost', 'wrapping_cost', 'taxes']
        
        res = BigCommerceOrderImportBuilder()
        res.orders = self.transformed_orders
        for vals in res.prepare():
            self.assertFalse(set(primary_keys + fees_keys) - set(vals))
