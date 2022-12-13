# Copyright © 2020 - 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.multichannel_order.tests.common import ChannelOrderTestCommon, ignore_delay, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class BigCommerceTestCommon(ChannelOrderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def _add_channels(cls):
        super()._add_channels()
        test_data = cls.test_data
        ecommerce_channel_model = cls.env['ecommerce.channel']
        currencies = cls.env.ref('base.USD') | cls.env.ref('base.EUR')

        bigcommerce_get_store_settings_return_value = {
            'secure_url': 'https://auto-test.mybigcommerce.com',
            'admin_email': 'bigcommerce.admin@auto-test.test',
            'weight_unit': 'lb',
            'dimension_unit': 'in',
        }
        bigcommerce_get_store_currency_return_vals = {
            'currency_id': currencies[:1].id,
            'currency_ids': [(6, 0, currencies.ids)],
        }
        
        with patch.object(type(ecommerce_channel_model), 'bigcommerce_get_store_settings',
                          return_value=bigcommerce_get_store_settings_return_value), \
                patch.object(type(ecommerce_channel_model), '_bigcommerce_get_store_currency_vals',
                             return_value=bigcommerce_get_store_currency_return_vals), \
                patch.object(type(ecommerce_channel_model), '_bigcommerce_get_listing_value'), \
                patch.object(type(ecommerce_channel_model), 'action_refresh_payment_gateway_list'):
            bigcommerce_channel_1 = ecommerce_channel_model.create({
                'name': 'BigCommerce 1',
                'platform': 'bigcommerce',
                'active': True,
                'bc_access_token': 'auto-test-1.mybigcommerce.test',
                'bc_store_hash': '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',
                'company_id': test_data['company_1'].id,
                'default_warehouse_id': test_data['company_1_warehouse_1'].id,
                'app_client_id': 'ADHHĐHDHHDHD'
            })

            bigcommerce_channel_2 = ecommerce_channel_model.create({
                'name': 'BigCommerce 2',
                'platform': 'bigcommerce',
                'active': True,
                'bc_access_token': 'auto-test-1.mybigcommerce.test',
                'bc_store_hash': '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',
                'company_id': test_data['company_1'].id,
                'default_warehouse_id': test_data['company_1_warehouse_1'].id,
                'app_client_id': 'ADHHĐHDHHDHD',
                'auto_create_master_product': False,
            })

        test_data.update({
            'bigcommerce_channel_1': bigcommerce_channel_1,
            'bigcommerce_channel_2': bigcommerce_channel_2
        })

        category = cls.env['product.channel.category'].with_context(for_synching=True).create([{
            'name': 'Tmp',
            'channel_id': bigcommerce_channel_1.id
        }, {
            'name': 'Tmp',
            'channel_id': bigcommerce_channel_2.id
        }])
        bigcommerce_channel_1.write({'default_categ_id': category[0].id})
        bigcommerce_channel_2.write({'default_categ_id': category[1].id})
        cls.bigcommerce_channel_1 = bigcommerce_channel_1
        cls.bigcommerce_channel_2 = bigcommerce_channel_2

    @classmethod
    def _add_customers(cls):
        super()._add_customers()
        test_data = cls.test_data
        customer_channel_model = cls.env['customer.channel']

        customer_bigcommerce_us_1 = customer_channel_model.create({**cls.shared_data['partner_us_1_data'], **{
            'channel_id': test_data['bigcommerce_channel_1'].id,
            'id_on_channel': '457509920',
        }})
        customer_bigcommerce_us_2 = customer_channel_model.create({**cls.shared_data['partner_us_2_data_1'], **{
            'channel_id': test_data['bigcommerce_channel_1'].id,
            'id_on_channel': '457509935',
        }})

        test_data.update({
            'customer_bigcommerce_us_1': customer_bigcommerce_us_1,
            'customer_bigcommerce_us_2': customer_bigcommerce_us_2,
        })
