# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tools import mute_logger

from odoo.addons.omni_manage_channel.tests.common import patch_request
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceExportProduct(BigCommerceTestCommon):
    REQUIRED_TEMPLATE_KEYS = [
        'is_visible', 'categories', 'fixed_cost_shipping_price', 'is_free_shipping', 'order_quantity_minimum',
        'order_quantity_maximum', 'bin_picking_number', 'sale_price', 'tax_class_id', 'product_tax_code',
        'is_featured', 'sort_order', 'custom_url', 'is_preorder_only', 'page_title', 'search_keywords',
        'bulk_pricing_rules', 'open_graph_type', 'inventory_warning_level', 'warranty', 'is_condition_shown',
        'meta_description', 'availability', 'condition', 'custom_fields', 'preorder_message',
        'open_graph_use_product_name', 'open_graph_use_image', 'preorder_release_date', 'open_graph_description',
        'open_graph_use_meta_description', 'availability_description', 'open_graph_title', 'related_products',
    ]
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create master product without variants
        master_product_without_variant_vals = {
            'name': 'Master Product without Variants',
            'type': 'product',
            'default_code': 'test-master-product',
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
        
        cls.master_product_without_variant = cls.env['product.template'].create(master_product_without_variant_vals)
        
        # Create master product with variants
        att1_vals = {
            'name': 'Attribute 1',
            'value_ids': [(0, 0, {'name': 'Value 1'}), (0, 0, {'name': 'Value 2'})]
            
        }
        
        att2_vals = {
            'name': 'Attribute 2',
            'value_ids': [(0, 0, {'name': 'Value 3'})]
            
        }
        
        attributes = cls.env['product.attribute'].create([att1_vals, att2_vals])
        
        master_product_variant_vals = {
            'name': 'Master Product with Variants',
            'type': 'product',
            'default_code': 'test-master-product-2',
            'lst_price': 10,
            'retail_price': 20,
            'width': 20,
            'depth': 10,
            'height': 30,
            'weight_in_oz': 18,
            'upc': '123456',
            'mpn': '12334234',
            'gtin': '12345678',
            'attribute_line_ids': [(0, 0, {'attribute_id': attributes[0].id,
                                           'value_ids': [(6, 0, attributes[0].value_ids.ids)]}),
                                   (0, 0, {'attribute_id': attributes[1].id,
                                           'value_ids': [(6, 0, attributes[1].value_ids.ids)]})]
        }
        
        cls.master_product_with_variant = cls.env['product.template'].create(master_product_variant_vals)
                                     
    def test_export_from_master_no_variants(self):
        """
        Make sure that we have enough information to export product (no variants) to BigCommerce from master
        """
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.master_product_without_variant.id,
            'channel_id': self.bigcommerce_channel_1.id
        })
        with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._push_to_channel', autospec=True) as mock_push_action:
            with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._put_to_channel', autospec=True) as mock_put_action:
                action = wizard.export()
                self.assertTrue(action.get('res_id', False))
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                fields = product_mapping.channel_id.get_setting('product_exported_fields')
                exported_fields = {
                    'template': fields['master_template'],
                    'variant': fields['master_variant']
                }
                data = product_mapping._bigcommerce_prepare_data(exported_fields=exported_fields)
                required_keys = [
                    'name', 'type', 'sku', 'description',
                    'weight', 'width', 'depth', 'height', 'upc', 'mpn', 'gtin',
                    'price', 'retail_price', 'inventory_tracking', 'variants', 'brand_id',
                    'categories', 'is_visible'
                ]
                self.assertEqual(set(required_keys), set(data.keys()))
            
    def test_export_from_master_with_variants(self):
        """
        Make sure that we have enough information to export product (with variants) to BigCommerce from master
        """
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.master_product_with_variant.id,
            'channel_id': self.bigcommerce_channel_1.id
        })
        with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._push_to_channel', autospec=True) as mock_push_action:
            with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._put_to_channel', autospec=True) as mock_put_action:
                action = wizard.export()
                self.assertTrue(action.get('res_id', False))
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                fields = product_mapping.channel_id.get_setting('product_exported_fields')
                exported_fields = {
                    'template': fields['master_template'],
                    'variant': fields['master_variant']
                }
                data = product_mapping._bigcommerce_prepare_data(exported_fields=exported_fields)
                required_template_keys = [
                    'name', 'type', 'description',
                    'weight', 'width', 'depth', 'height', 'mpn',
                    'price', 'retail_price', 'inventory_tracking', 'variants', 'brand_id', 'categories', 'is_visible'
                ]
                required_variant_keys = [
                    'price', 'retail_price', 'upc', 'mpn',
                    'weight', 'width', 'depth', 'height', 'sku', 'option_values'
                ]
                self.assertEqual(set(required_template_keys), set(data.keys()))
                for variant in data['variants']:
                    self.assertEqual(set(required_variant_keys), set(variant.keys()))

    def test_export_from_mapping_without_variants(self):
        """
        Make sure that we have enough information to export product (no variants) to BigCommerce from mapping
        """
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.master_product_without_variant.id,
            'channel_id': self.bigcommerce_channel_1.id
        })
        with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._push_to_channel', autospec=True) as mock_push_action:
            with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._put_to_channel', autospec=True) as mock_put_action:
                action = wizard.export()
                self.assertTrue(action.get('res_id', False))
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                fields = product_mapping.channel_id.get_setting('product_exported_fields')
                exported_fields = {
                    'template': fields['mapping_template'],
                    'variant': fields['mapping_variant']
                }
                self.assertEqual(len(product_mapping.product_variant_ids), 1)
                data = product_mapping._bigcommerce_prepare_data(exported_fields=exported_fields, update=True)
                self.assertEqual(set(self.REQUIRED_TEMPLATE_KEYS), set(data.keys()))

    @mute_logger('odoo.models.unlink')
    def test_export_from_mapping_with_variants(self):
        """
        Make sure that we have enough information to export product (no variants) to BigCommerce from mapping
        """
        export_res = {
            'data': {
                'id': 9734,
                'custom_url': {'url': "/product-with-variants/", 'is_customized': False},
                'variants': [{
                    'id': 24541,
                    'option_values': [
                        {'label': 'Value 1', 'option_display_name': 'Attribute 1'},
                        {'label': 'Value 3', 'option_display_name': 'Attribute 2'},
                    ],
                }, {
                    'id': 24542,
                    'option_values': [
                        {'label': 'Value 2', 'option_display_name': 'Attribute 1'},
                        {'label': 'Value 3', 'option_display_name': 'Attribute 2'},
                    ],
                }]
            }
        }
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.master_product_with_variant.id,
            'channel_id': self.bigcommerce_channel_1.id
        })
        with patch_request(url=r'.*/catalog/products', jsn=export_res) as mock_request:
            action = wizard.export()

        mock_request.assert_called()
        self.assertTrue(action.get('res_id', False))
        product_mapping = self.env['product.channel'].browse(action['res_id'])
        self.assertEqual(len(product_mapping.product_variant_ids), 2)

        fields = product_mapping.channel_id.get_setting('product_exported_fields')
        exported_fields = {
            'template': fields['mapping_template'],
            'variant': fields['mapping_variant'],
        }
        data = product_mapping._bigcommerce_prepare_data(exported_fields=exported_fields, update=True)
        self.assertEqual(set(self.REQUIRED_TEMPLATE_KEYS), set(data.keys()))
