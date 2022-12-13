import json

from odoo.tests.common import tagged, TransactionCase

from odoo.addons.omni_manage_channel.tests.utils import get_data_path

from .common import no_commit


@tagged('post_install', 'basic_test', '-at_install')
class ProductManagementTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.stores = dict()
        cls.single_variant_test = dict()
        cls.multi_variant_test = dict()
        cls.multi_variant_updated_attr_test = dict()

        cls._add_store()
        cls._prepare_single_variant_product_data()
        cls._prepare_multi_variant_product_data()
        cls._prepare_multi_variant_product_data_with_updated_attributes()

    @classmethod
    def _add_store(cls):
        with open(get_data_path(__file__, 'data/store_data.json'), 'r') as fp:
            cls.env['product.exported.field'].create({
                'platform': 'none',
                'api_ref': 'Attributes',
                'store_field_name': 'Attributes',
                'odoo_field_id': cls.env.ref('product.field_product_product__product_template_attribute_value_ids').id,
                'mapping_field_name': 'attribute_value_ids',
                'is_fixed': True
            })
            cls.stores['store_1'] = cls.env['ecommerce.channel'].create(json.load(fp))

    @classmethod
    def _prepare_single_variant_product_data(cls):
        with open(get_data_path(__file__, 'data/single_variant/product_data.json'), 'r') as fp:
            cls.single_variant_test['product_data'] = json.load(fp)
            cls.single_variant_test['product_data'][0].update({
                'channel_id': cls.stores['store_1'].id,
                'vendor_id': cls.env['product.channel.vendor'].get_vendor('Plant Therapy').id
            })

        with open(get_data_path(__file__, 'data/single_variant/product_template_check.json'), 'r') as fp:
            cls.single_variant_test['product_template_check'] = json.load(fp)

        with open(get_data_path(__file__, 'data/single_variant/product_channel_variant_check.json'), 'r') as fp:
            cls.single_variant_test['product_channel_variant_check'] = json.load(fp)

    @classmethod
    def _prepare_multi_variant_product_data(cls):
        with open(get_data_path(__file__, 'data/multi_variant/product_data.json'), 'r') as fp:
            cls.multi_variant_test['product_data'] = json.load(fp)

            attribute_data = cls.multi_variant_test['product_data'][0]['options']
            cls.multi_variant_test['product_data'][0].update({
                'channel_id': cls.stores['store_1'].id,
                'attribute_line_ids': [
                    cls.env['product.attribute'].create_attribute_line(attribute_line['name'], attribute_line['values'])
                    for attribute_line in attribute_data
                ],
                'vendor_id': cls.env['product.channel.vendor'].get_vendor('Apple').id
            })

        with open(get_data_path(__file__, 'data/multi_variant/product_template_check.json'), 'r') as fp:
            cls.multi_variant_test['product_template_check'] = json.load(fp)

        with open(get_data_path(__file__, 'data/multi_variant/product_channel_variant_check.json'), 'r') as fp:
            cls.multi_variant_test['product_channel_variant_check'] = json.load(fp)

    @classmethod
    def _prepare_multi_variant_product_data_with_updated_attributes(cls):
        with open(get_data_path(__file__, 'data/multi_variant/product_data_update_variant.json'), 'r') as fp:
            cls.multi_variant_updated_attr_test['product_data'] = json.load(fp)

            attribute_data = cls.multi_variant_updated_attr_test['product_data'][0]['options']
            cls.multi_variant_updated_attr_test['product_data'][0].update({
                'channel_id': cls.stores['store_1'].id,
                'attribute_line_ids': [
                    cls.env['product.attribute'].create_attribute_line(attribute_line['name'], attribute_line['values'])
                    for attribute_line in attribute_data
                ],
                'vendor_id': cls.env['product.channel.vendor'].get_vendor('Apple').id
            })

@tagged('post_install', 'basic_test', '-at_install')
class TestProcessProductData(ProductManagementTestCommon):

    @no_commit
    def test_process_single_variant_product_data(self):
        product_template_model = self.env['product.template']
        product_channel_model = self.env['product.channel']

        stores = self.stores
        single_variant_data = self.single_variant_test

        product_data = single_variant_data['product_data']
        product_channel_ids = product_template_model._sync_in_queue_job(
            products=product_data,
            channel_id=stores['store_1'].id,
            auto_create_master=True
        )

        # Check if create only 1 product mapping
        product_channel = product_channel_model.browse(product_channel_ids)
        self.assertEqual(len(product_channel), 1)

        # Check if create 1 product template and 1 product channel variant
        product_template = product_channel.product_tmpl_id
        product_channel_variant = product_channel.product_variant_ids
        self.assertEqual(len(product_template), 1)
        self.assertEqual(len(product_channel_variant), 1)

        # Check if product template and product channel variant data match
        self.assertRecordValues(product_template, single_variant_data['product_template_check'])
        self.assertRecordValues(product_channel_variant, single_variant_data['product_channel_variant_check'])

    @no_commit
    def test_process_multi_variant_product_data(self):
        product_template_model = self.env['product.template']
        product_channel_model = self.env['product.channel']

        stores = self.stores
        multi_variant_data = self.multi_variant_test
        product_data = multi_variant_data['product_data']
        product_channel_ids = product_template_model._sync_in_queue_job(
            products=product_data,
            channel_id=stores['store_1'].id,
            auto_create_master=True
        )

        # Check if create only 1 product mapping
        product_channel = product_channel_model.browse(product_channel_ids)
        self.assertEqual(len(product_channel), 1)

        product_template = product_channel.product_tmpl_id
        self.assertRecordValues(product_template, multi_variant_data['product_template_check'])
        # Check if product template has 1 attribute with 2 values
        product_attributes = product_template.attribute_line_ids
        self.assertEqual(len(product_attributes), 1)

        attribute = product_attributes.attribute_id
        attribute_values = product_attributes.product_template_value_ids
        self.assertRecordValues(attribute, [{'name': 'Color'}])
        self.assertRecordValues(attribute_values, [{'name': 'Red'}, {'name': 'Purple'}])

        # Check if create 1 product template, 2 product variant and 2 product channel variant
        product_variant = product_template.product_variant_ids
        product_channel_variant = product_channel.product_variant_ids
        product_channel_variant_product_product = product_channel_variant.mapped('product_product_id')
        self.assertEqual(len(product_template), 1)
        self.assertEqual(len(product_variant), 2)
        self.assertEqual(len(product_channel_variant), 2)
        self.assertEqual(product_variant, product_channel_variant_product_product)
        self.assertRecordValues(product_channel_variant, multi_variant_data['product_channel_variant_check'])

    @no_commit
    def test_modify_attributes_when_importing_product(self):
        product_template_model = self.env['product.template']
        product_channel_model = self.env['product.channel']

        stores = self.stores
        product_data = self.multi_variant_test['product_data']
        product_channel_ids = product_template_model._sync_in_queue_job(
            products=product_data,
            channel_id=stores['store_1'].id,
            auto_create_master=True
        )

        product_channel = product_channel_model.browse(product_channel_ids)
        product_template = product_channel.product_tmpl_id
        product_attributes = product_template.attribute_line_ids
        self.assertEqual(len(product_attributes), 1)
        attribute = product_attributes.attribute_id
        attribute_values = product_attributes.product_template_value_ids
        self.assertRecordValues(attribute, [{'name': 'Color'}])
        self.assertRecordValues(attribute_values, [{'name': 'Red'}, {'name': 'Purple'}])

        # Re-import product with new attribute (remove Purple, add Green)
        new_product_data = self.multi_variant_updated_attr_test['product_data']
        new_product_channel_ids = product_template_model._sync_in_queue_job(
            products=new_product_data,
            channel_id=stores['store_1'].id,
            auto_create_master=True
        )
        self.assertEqual(product_channel_ids, new_product_channel_ids)

        product_channel = product_channel_model.browse(new_product_channel_ids)
        product_template = product_channel.product_tmpl_id
        product_attributes = product_template.attribute_line_ids
        self.assertEqual(len(product_attributes), 1)
        attribute = product_attributes.attribute_id
        attribute_values = product_attributes.product_template_value_ids
        self.assertRecordValues(attribute, [{'name': 'Color'}])
        self.assertRecordValues(attribute_values, [{'name': 'Red'}, {'name': 'Green'}])
