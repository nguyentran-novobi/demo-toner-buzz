# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import uuid
import copy
import functools

from unittest.mock import patch, MagicMock

from odoo import fields
from odoo.tools import mute_logger

from odoo.addons.omni_manage_channel.utils.common import ImageUtils
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_product.models.product_template import MappingImportError
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import BigCommerceHelper
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged

from .common import ignore_delay, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceImportProduct(BigCommerceTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._set_up_responses()

    @classmethod
    def _set_up_responses(cls):
        with open(get_data_path(__file__, 'data/bigcommerce_get_products.json'), 'r') as fp:
            res_json = json.load(fp)
        cls.transformed_products = res_json['data']
    
    @ignore_delay
    @no_commit
    @mute_logger('odoo.models.unlink', 'odoo.addons.multichannel_product.models.product_channel_variant')
    @patch.object(ImageUtils, 'get_safe_image_b64', return_value=b'')
    @patch('odoo.addons.multichannel_bigcommerce.models.product_brand.BrandChannel.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.tax_class.TaxClass.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.product_channel_category.ProductChannelCategory.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_product_helper.ProductImporter.do_import', autospec=True)
    def test_import_auto_create_master(self, mock_do_import_product, mock_category, mock_tax, mock_brand, mock_image):
        """
        Make sure that product mapping and product master will be created correctly
        """

        channel = self.bigcommerce_channel_1
        mock_brand.return_value = self.env['brand.channel']  
        mock_tax.return_value = self.env['tax.class']
        api = BigCommerceHelper.connect_with_channel(channel)
        mock_do_import_product.return_value = [api.orders.create_collection_with(self.transformed_products)]
        product_tmpl_model = self.env['product.template']

        product_tmpl_model.bigcommerce_get_data(channel.id, auto_create_master=channel.auto_create_master_product)
        product_mappings = self.env['product.channel'].search([
            ('id_on_channel', 'in', ['180', '181', '30957']),
            ('channel_id', '=', channel.id),
        ])
        
        self.assertEqual(len(product_mappings), 3, 'Mappings created were not enough!')
        self.assertTrue(all([p.product_tmpl_id for p in product_mappings]), 'Mappings created were not linked to master!')
        
        mock_brand.assert_called()
        mock_tax.assert_called()
        mock_category.assert_called()
        mock_image.assert_called()

    @ignore_delay
    @no_commit    
    @mute_logger('odoo.addons.multichannel_product.models.product_channel_variant')  
    @patch('odoo.addons.multichannel_bigcommerce.models.product_brand.BrandChannel.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.tax_class.TaxClass.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.product_channel_category.ProductChannelCategory.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_product_helper.ProductImporter.do_import', autospec=True)
    def test_import_no_auto_create_master(self, mock_do_import_product, mock_category, mock_tax, mock_brand):
        """
        Make sure that product mapping and product master will be created correctly
        """

        master = {
            'name': 'BigCommerce 1',
            'type': 'product',
            'default_code': 'BigCommerce 1',
            'lst_price': 10,
            'retail_price': 20,
            'width': 20,
            'depth': 10,
            'height': 30,
            'weight_in_oz': 18,
            'upc': '123456',
            'mpn': '12334234',
            'gtin': '12345678'
        }
        
        self.env['product.template'].create(master)
        
        mock_brand.return_value = self.env['brand.channel']  
        mock_tax.return_value = self.env['tax.class']

        channel = self.bigcommerce_channel_2
        api = BigCommerceHelper.connect_with_channel(channel)
        mock_do_import_product.return_value = [api.orders.create_collection_with(self.transformed_products)]
        
        product_tmpl_model = self.env['product.template']

        with self.assertRaises(MappingImportError):
            product_tmpl_model.bigcommerce_get_data(channel.id, auto_create_master=channel.auto_create_master_product)

        product_mappings = self.env['product.channel'].search([
            ('id_on_channel', 'in', ['180', '181', '30957']),
            ('channel_id', '=', channel.id),
        ])
        
        self.assertEqual(len(product_mappings), 1, 'Mappings created are not correctly. Expected: Only one mapping is created!')
        self.assertTrue(all([p.product_tmpl_id for p in product_mappings]), 'Mappings created were not linked to master!')
        
        mock_brand.assert_called()
        mock_tax.assert_called()
        mock_category.assert_called()

    @ignore_delay
    @no_commit   
    @mute_logger('odoo.models.unlink', 'odoo.addons.multichannel_product.models.product_channel_variant')
    @patch.object(ImageUtils, 'get_safe_image_b64', return_value=b'')
    @patch('odoo.addons.multichannel_bigcommerce.models.product_brand.BrandChannel.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.tax_class.TaxClass.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.models.product_channel_category.ProductChannelCategory.bigcommerce_get_data', autospec=True)
    @patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_product_helper.ProductImporter.do_import', autospec=True)
    def test_update_and_create_mapping_with_auto_merge(self, mock_do_import_product, mock_category, mock_tax, mock_brand, mock_image):
        """
        Make sure that product mapping and product master will be created correctly
        """
        
        mock_brand.return_value = self.env['brand.channel']  
        mock_tax.return_value = self.env['tax.class']

        channel = self.bigcommerce_channel_1
        api = BigCommerceHelper.connect_with_channel(channel)
        transformed_products = copy.deepcopy(self.transformed_products)
        mock_do_import_product.return_value = [api.orders.create_collection_with(transformed_products)]
        
        product_tmpl_model = self.env['product.template']

        product_tmpl_model.bigcommerce_get_data(channel.id, auto_create_master=channel.auto_create_master_product)

        product_mappings = self.env['product.channel'].search([
            ('id_on_channel', 'in', ['180', '181', '30957']),
            ('channel_id', '=', channel.id),
        ])
                
        for product_mapping in product_mappings:
            if product_mapping.product_tmpl_id.attribute_line_ids:
                product_mapping.product_tmpl_id.product_variant_ids.write({
                    'lst_price': 20,
                    'weight': 10,
                    'width': 2
                })
                product_mapping.product_tmpl_id.product_variant_ids[1].write({'active': False})
            else:
                product_mapping.product_tmpl_id.write({
                    'name': 'Test Merge',
                    'lst_price': 20,
                    'weight': 10,
                    'width': 2,
                    'default_code': uuid.uuid4(),
                    'description': 'Test Description',
                    'description_sale': 'Test Description Sale',
                })

        transformed_products = copy.deepcopy(self.transformed_products)
        mock_do_import_product.return_value = [api.orders.create_collection_with(transformed_products)]
        with patch.object(type(self.env['product.template']), 'create_from_mapping') as mock_create_product:
            product_tmpl_model.bigcommerce_get_data(channel.id, auto_create_master=channel.auto_create_master_product)
            mock_create_product.assert_not_called()
            
        merged_fields = channel.get_setting('product_merged_fields')
        for mpt in product_mappings:
            for mapping_field, master_field in merged_fields['template']:
                if mapping_field and master_field:
                    msg = f'{mapping_field} on Template of Mapping and Master are different'
                    if isinstance(mpt._fields[mapping_field], fields.Float):
                        assert_func = functools.partial(self.assertAlmostEqual, places=2, msg=msg)
                    else:
                        assert_func = functools.partial(self.assertEqual, msg=msg)
                    assert_func(mpt[mapping_field], mpt.product_tmpl_id[master_field])

        for mpv in product_mappings.product_variant_ids:
            for mapping_field, master_field in merged_fields['variant']:
                if mapping_field and master_field:
                    msg = f'{mapping_field} on Variant of Mapping and Master are different'
                    if isinstance(mpv._fields[mapping_field], fields.Float):
                        assert_func = functools.partial(self.assertAlmostEqual, places=2, msg=msg)
                    else:
                        assert_func = functools.partial(self.assertEqual, msg=msg)
                    assert_func(mpv[mapping_field], mpv.product_product_id[master_field])
       
        mock_brand.assert_called()
        mock_tax.assert_called()
        mock_category.assert_called()
        mock_image.assert_called()
