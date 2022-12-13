from odoo.tests import tagged

from odoo.addons.omni_manage_channel.tests.common import ListingTestCommon


@tagged('post_install', 'basic_test', '-at_install')
class TestProductChannelAvailability(ListingTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._set_up_products()

    def setUp(self):
        super().setUp()

        self.basic_settings = {
            'percentage_inventory_sync': 100.0,
            'is_enable_maximum_inventory_sync': False,
            'is_enable_minimum_inventory_sync': False,
        }
        self.percentage_settings = {**self.basic_settings, **{
            'percentage_inventory_sync': 25.0,
        }}
        self.enabled_maximum_settings = {**self.basic_settings, **{
            'is_enable_maximum_inventory_sync': True,
            'maximum_inventory_sync': 36,
        }}
        self.enabled_minimum_settings = {**self.basic_settings, **{
            'is_enable_minimum_inventory_sync': True,
            'minimum_inventory_sync': 4,
        }}
        self.mixed_1_settings = {**self.basic_settings, **{
            'percentage_inventory_sync': 45.0,
            'is_enable_maximum_inventory_sync': True,
            'maximum_inventory_sync': 28,
            'is_enable_minimum_inventory_sync': True,
            'minimum_inventory_sync': 3,
        }}
        self.mixed_2_settings = {**self.basic_settings, **{
            'percentage_inventory_sync': 25.0,
            'maximum_inventory_sync': 36,
            'is_enable_minimum_inventory_sync': True,
            'minimum_inventory_sync': 4,
        }}

    @classmethod
    def _add_warehouses(cls):
        super()._add_warehouses()
        company_1_warehouse_1 = cls.test_data['company_1_warehouse_1']
        company_1_warehouse_2 = company_1_warehouse_1.copy({
            'name': 'Test WH 2',
            'code': 'test-wh-2',
        })

        cls.test_data.update({
            'company_1_warehouse_2': company_1_warehouse_2,
        })

    @classmethod
    def _add_channels(cls):
        super()._add_channels()
        test_data = cls.test_data
        ecommerce_channel_model = cls.env['ecommerce.channel']

        general_channel_1 = ecommerce_channel_model.create({
            'name': 'General Channel 1',
            'platform': False,
            'active': True,
            'company_id': test_data['base_company'].id,
            'active_warehouse_ids': [(6, 0, test_data['base_warehouse'].ids)]
        })
        general_channel_2 = ecommerce_channel_model.create({
            'name': 'General Channel 2',
            'platform': False,
            'active': True,
            'company_id': test_data['company_1'].id,
            'active_warehouse_ids': [
                (6, 0, (test_data['company_1_warehouse_1'] | test_data['company_1_warehouse_2']).ids),
            ]
        })

        test_data.update({
            'general_channel_1': general_channel_1,
            'general_channel_2': general_channel_2,
        })

    @classmethod
    def _set_up_products(cls):
        test_data = cls.test_data
        cls.master_1 = cls.env['product.template'].create({
            'name': 'Master Product 1 without Variants',
            'type': 'product',
        })
        cls.master_1_variant_1 = cls.master_1.product_variant_id
        cls.mapping_1 = cls.env['product.channel'].create({
            'name': cls.master_1.name,
            'id_on_channel': 'mapping-1',
            'default_code': cls.master_1.default_code,
            'channel_id': test_data['general_channel_1'].id,
            'product_tmpl_id': cls.master_1.id,
            'product_variant_ids': [(0, 0, {
                'id_on_channel': 'mapping-variant-1',
                'product_product_id': cls.master_1_variant_1.id,
                'default_code': cls.master_1_variant_1.default_code
            })]
        })
        cls.mapping_1_variant_1 = cls.mapping_1.product_variant_id
        cls.mapping_2 = cls.env['product.channel'].create({
            'name': cls.master_1.name,
            'id_on_channel': 'mapping-2',
            'default_code': cls.master_1.default_code,
            'channel_id': test_data['general_channel_2'].id,
            'product_tmpl_id': cls.master_1.id,
            'product_variant_ids': [(0, 0, {
                'id_on_channel': 'mapping-variant-2',
                'product_product_id': cls.master_1_variant_1.id,
                'default_code': cls.master_1_variant_1.default_code
            })]
        })
        cls.mapping_2_variant_1 = cls.mapping_2.product_variant_id

    def test_compute_free_qty(self):
        cases = [
            (self.basic_settings, [(-1.0, 0.0), (0.0, 0.0), (2.0, 2.0)]),
            (self.percentage_settings, [(-1.0, 0.0), (0.0, 0.0), (2.0, 0.0), (14.0, 3.0), (24.0, 6.0)]),
            (self.enabled_maximum_settings, [(-1.0, 0.0), (0.0, 0.0), (9.0, 9.0), (36.0, 36.0), (75.0, 36.0)]),
            (self.enabled_minimum_settings, [(-1.0, 4.0), (0.0, 4.0), (2.0, 4.0), (4.0, 4.0), (25.0, 25.0)]),
            (self.mixed_1_settings, [(-1.0, 3.0), (0.0, 3.0), (2.0, 3.0), (7.0, 3.0), (50.0, 22.0), (62.0, 27.0), (85.0, 28.0)]),
            (self.mixed_2_settings, [(-1.0, 4.0), (0.0, 4.0), (2.0, 4.0), (16.0, 4.0), (50.0, 12.0), (144.0, 36.0), (256.0, 64.0)]),
        ]
        mapping_variant = self.mapping_1_variant_1
        channel = mapping_variant.channel_id
        for settings, qty_cases in cases:
            channel.write(settings)
            for qty_case in qty_cases:
                with self.subTest(settings=settings, qty_case=qty_case):
                    self._update_master_quantity_of(mapping_variant, qty_case[0])
                    mapping_variant._compute_free_qty()
                    self.assertEqual(mapping_variant.free_qty, qty_case[1])
                    self._update_master_quantity_of(mapping_variant, qty_case[0] * -1)

    def _update_master_quantity_of(self, mapping_variant, quantity, override_warehouse=None):
        """Increase/Decrease quantity of the master product of the provided mapping product"""
        master_variant = mapping_variant.product_product_id
        channel = mapping_variant.channel_id
        warehouse = override_warehouse or channel.active_warehouse_ids[:1]
        stock_location = warehouse.lot_stock_id
        self.env['stock.quant']._update_available_quantity(master_variant, stock_location, quantity)

    def test_compute_free_qty_multi_warehouses(self):
        test_data = self.test_data
        warehouses = (
            test_data['base_warehouse']
            | test_data['company_1_warehouse_1']
            | test_data['company_1_warehouse_2']
        )
        cases = [
            ((0.0, 0.0, 0.0), 3.0),
            ((7.0, 0.0, 0.0), 3.0),
            ((9.0, 0.0, 2.0), 3.0),
            ((35.0, 5.0, 2.0), 3.0),
            ((17.0, 8.0, 15.0), 10.0),
            ((3.0, 25.0, 7.0), 14.0),
            ((0.0, 41.0, 34.0), 28.0),
        ]
        mapping_variant = self.mapping_2_variant_1
        channel = mapping_variant.channel_id
        channel.write(self.mixed_1_settings)
        for wh_qty_list, out in cases:
            with self.subTest(wh_qty_list=wh_qty_list, out=wh_qty_list):
                for wh_qty, wh in zip(wh_qty_list, warehouses):
                    self._update_master_quantity_of(mapping_variant, wh_qty, wh)
                mapping_variant._compute_free_qty()
                self.assertEqual(mapping_variant.free_qty, out)
                for wh_qty, wh in zip(wh_qty_list, warehouses):
                    self._update_master_quantity_of(mapping_variant, wh_qty * -1, wh)
