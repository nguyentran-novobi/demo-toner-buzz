# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.tests.common import tagged
from odoo.addons.omni_manage_channel.tests.common import ListingTestCommon
import functools
import uuid
from unittest.mock import patch, Mock

class NonDelayableRecordset:
    def __init__(self, recordset):
        self.recordset = recordset

    def __getattr__(self, name):
        if name in self.recordset:
            raise AttributeError
        recordset_method = getattr(self.recordset, name)

        def exe(*args, **kwargs):
            recordset_method(*args, **kwargs)
            return Mock(uuid=str(uuid.uuid4()))

        return exe


def ignore_delay(func):
    def with_delay_side_effect(self, *_args, **_kwargs):
        return NonDelayableRecordset(self)

    @functools.wraps(func)
    def wrapper_ignore_delay(*args, **kwargs):
        with patch('odoo.addons.queue_job.models.base.Base.with_delay',
                   side_effect=with_delay_side_effect, autospec=True):
            res = func(*args, **kwargs)
        return res
    return wrapper_ignore_delay


def no_commit(func):
    @functools.wraps(func)
    def no_commit_wrapper(*args, **kwargs):
        with patch('odoo.sql_db.Cursor.commit', autospec=True):
            res = func(*args, **kwargs)
        return res
    return no_commit_wrapper

@tagged('post_install', 'basic_test', '-at_install')
class ChannelOrderTestCommon(ListingTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_channels()
        cls._add_mapping_data()
        cls._add_masters()
        
    @classmethod
    def _add_channels(cls):
        test_data = cls.test_data
        ecommerce_channel_model = cls.env['ecommerce.channel']

        shopify_get_store_settings_return_value = {
            'secure_url': 'https://auto-test.myshopify.test',
            'admin_email': 'shopify.admin@auto-test.test',
            'weight_unit': 'lb',
            'api_version': '2022-01',
        }
        with patch('odoo.addons.multichannel_shopify.models.ecommerce_channel.ShopifyChannel.shopify_get_store_settings',
                   return_value=shopify_get_store_settings_return_value):
            with patch('odoo.addons.multichannel_shopify.models.ecommerce_channel.ShopifyChannel.shopify_get_locations'):
                with patch('odoo.addons.multichannel_shopify.models.ecommerce_channel.ShopifyChannel._shopify_get_listing_value'):
                    shopify_channel_1 = ecommerce_channel_model.create({
                        'name': 'Test Store',
                        'platform': 'shopify',
                        'active': True,
                        'shopify_hostname': 'auto-test-1.myshopify.test',
                        'shopify_access_token': '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',
                        'fulfillment_location_id': False,  # TODO: Add a testing shopify location here
                    })
                    shopify_channel_2 = ecommerce_channel_model.create({
                        'name': 'Test Store',
                        'platform': 'shopify',
                        'active': True,
                        'shopify_hostname': 'auto-test-1.myshopify.test',
                        'shopify_access_token': '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',
                        'fulfillment_location_id': False,  # TODO: Add a testing shopify location here
                        'auto_create_master_product': False
                    })

        test_data.update({
            'store_1': shopify_channel_1,
            'store_2': shopify_channel_2,
        })
        
    @classmethod
    def _add_mapping_data(cls):
        mapping_data_1 = {
            'name': 'Listing 1',
            'id': '34543234',
            'channel_id': cls.test_data['store_1'].id
        }
        
        mapping_data_2 = {
            'name': 'Listing 2',
            'id': '5454545',
            'channel_id': cls.test_data['store_2'].id
        }

        cls.test_data.update({
            'mapping_data_1': mapping_data_1,
            'mapping_data_2': mapping_data_2,
        })
        
    @classmethod
    def _add_masters(cls):
        master_data_1 = {
            'name': 'Master Product without Variants',
            'type': 'product',
            'default_code': 'test-master-product',
            'lst_price': 10,
            'retail_price': 20,
            'width': 20,
            'depth': 10,
            'height': 30,
            'weight_in_oz': 18,
            'upc': '123456' ,
            'mpn': '12334234',
            'gtin': '12345678'
        }
        master_1 = cls.env['product.template'].create(master_data_1)
        cls.test_data.update({
            'master_1': master_1
        })
