# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json

from unittest.mock import Mock, patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.omni_manage_channel.tests.common import patch_model, patch_request
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import BigCommerceHelper
from odoo.addons.multichannel_bigcommerce.utils import bigcommerce_pricelist_helper as ph

from .common import BigCommerceTestCommon, ignore_delay


class TestMasterPricelistCommon(BigCommerceTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._wipe_out_mapping_products()
        cls._set_up_mapping_products()
        cls._set_up_pricelist()

    @classmethod
    @mute_logger('odoo.models.unlink')
    def _wipe_out_mapping_products(cls):
        """
        Ensure only products created in this test are considered
        """
        mappings = cls.env['product.channel'].search([('channel_id', '=', cls.bigcommerce_channel_1.id)])
        mappings.unlink()

    @classmethod
    def _set_up_mapping_products(cls):
        prod_1 = cls.test_data['prod_1']
        cls.mapping_1 = cls.env['product.channel'].create({
            'name': prod_1.product_tmpl_id.name,
            'id_on_channel': 'mapping-1',
            'default_code': prod_1.product_tmpl_id.default_code,
            'channel_id': cls.bigcommerce_channel_1.id,
            'product_tmpl_id': prod_1.product_tmpl_id.id,
            'lst_price': prod_1.product_tmpl_id.list_price,
            'product_variant_ids': [(0, 0, {
                'id_on_channel': 'mapping-variant-1',
                'product_product_id': prod_1.id,
                'default_code': prod_1.default_code
            })]
        })

    @classmethod
    def _set_up_pricelist(cls):
        categ_1 = cls.test_data['categ_1']
        prod_1 = cls.test_data['prod_1']
        cls.pricelist_1 = cls.env['product.pricelist'].create({
            'name': 'Customer Pricelist 1',
            'currency_id': cls.env.ref('base.USD').id,
            'item_ids': [(0, 0, {
                'name': '20% Discount on Assemble Computer',
                'applied_on': '1_product',
                'product_tmpl_id': prod_1.product_tmpl_id.id,
                'compute_price': 'formula',
                'base': 'list_price',
                'price_discount': 20.0,
                'price_round': 2,
                'price_surcharge': 25.0,
                'price_min_margin': -50.0,
                'price_max_margin': -5.0,
            })]
        })
        cls.pricelist_2 = cls.env['product.pricelist'].create({
            'name': 'Customer Pricelist 2',
            'currency_id': cls.env.ref('base.USD').id,
            'item_ids': [(0, 0, {
                'name': '15% Discount on Assemble Computer',
                'applied_on': '0_product_variant',
                'product_id': prod_1.id,
                'compute_price': 'percentage',
                'percent_price': 15,
            })]
        })
        cls.pricelist_3 = cls.env['product.pricelist'].create({
            'name': 'Customer Pricelist 3',
            'currency_id': cls.env.ref('base.USD').id,
            'item_ids': [(0, 0, {
                'name': 'Fixed 150 on Computer Category',
                'applied_on': '2_product_category',
                'categ_id': categ_1.id,
                'compute_price': 'fixed',
                'fixed_price': 150.0,
            })]
        })
        cls.pricelist_4 = cls.env['product.pricelist'].create({
            'name': 'Customer Pricelist 4',
            'currency_id': cls.env.ref('base.USD').id,
            'item_ids': [(0, 0, {
                'name': '5% on Global at least 3',
                'applied_on': '3_global',
                'min_quantity': 3.0,
                'compute_price': 'formula',
                'price_discount': 5.0,
            }), (0, 0, {
                'name': '50% Off on Global at least 20',
                'applied_on': '3_global',
                'min_quantity': 20.0,
                'compute_price': 'percentage',
                'percent_price': 50,
            })]
        })


@tagged('post_install', 'basic_test', '-at_install')
class TestExportMasterPricelist(TestMasterPricelistCommon):
    @patch_model('channel.pricelist', 'export_to_channel')
    def test_export_new_pricelist_1_product_formula(self, mock_export):
        master_pricelist = self.pricelist_1
        channel = self.bigcommerce_channel_1
        wiz = self.env['export.pricelist.composer'].create({
            'pricelist_id': master_pricelist.id,
            'channel_id': channel.id,
        })
        wiz.export()
        mock_export.assert_called_once()
        mapping_pricelist = self.env['channel.pricelist'].search([
            ('pricelist_id', '=', master_pricelist.id),
            ('channel_id', '=', channel.id),
        ])
        self.assertRecordValues(mapping_pricelist, [{
            'name': master_pricelist.name,
            'currency_id': master_pricelist.currency_id.id,
        }])
        self.assertRecordValues(mapping_pricelist.rule_ids, [{
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
            'is_override_lst_price': True,
            'override_lst_price': 169.0,
        }])

    @patch_model('channel.pricelist', 'export_to_channel')
    def test_export_new_pricelist_0_product_variant_percentage(self, mock_export):
        master_pricelist = self.pricelist_2
        channel = self.bigcommerce_channel_1
        wiz = self.env['export.pricelist.composer'].create({
            'pricelist_id': master_pricelist.id,
            'channel_id': channel.id,
        })
        wiz.export()
        mock_export.assert_called_once()
        mapping_pricelist = self.env['channel.pricelist'].search([
            ('pricelist_id', '=', master_pricelist.id),
            ('channel_id', '=', channel.id),
        ])
        self.assertRecordValues(mapping_pricelist, [{
            'name': master_pricelist.name,
            'currency_id': master_pricelist.currency_id.id,
        }])
        self.assertRecordValues(mapping_pricelist.rule_ids, [{
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
            'is_override_lst_price': True,
            'override_lst_price': 153.0,
        }])

    @patch_model('channel.pricelist', 'export_to_channel')
    def test_export_new_pricelist_2_product_category_fixed(self, mock_export):
        master_pricelist = self.pricelist_3
        channel = self.bigcommerce_channel_1
        wiz = self.env['export.pricelist.composer'].create({
            'pricelist_id': master_pricelist.id,
            'channel_id': channel.id,
        })
        wiz.export()
        mock_export.assert_called_once()
        mapping_pricelist = self.env['channel.pricelist'].search([
            ('pricelist_id', '=', master_pricelist.id),
            ('channel_id', '=', channel.id),
        ])
        self.assertRecordValues(mapping_pricelist, [{
            'name': master_pricelist.name,
            'currency_id': master_pricelist.currency_id.id,
        }])
        self.assertRecordValues(mapping_pricelist.rule_ids, [{
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
            'is_override_lst_price': True,
            'override_lst_price': 150.0,
        }])

    @patch_model('channel.pricelist', 'export_to_channel')
    def test_export_new_pricelist_3_global_mixed(self, mock_export):
        def is_discount_type_equal(discount_type):
            return lambda rule: rule.bulk_pricing_discount_type == discount_type

        master_pricelist = self.pricelist_4
        channel = self.bigcommerce_channel_1
        wiz = self.env['export.pricelist.composer'].create({
            'pricelist_id': master_pricelist.id,
            'channel_id': channel.id,
        })
        wiz.export()
        mock_export.assert_called_once()
        mapping_pricelist = self.env['channel.pricelist'].search([
            ('pricelist_id', '=', master_pricelist.id),
            ('channel_id', '=', channel.id),
        ])
        self.assertRecordValues(mapping_pricelist, [{
            'name': master_pricelist.name,
            'currency_id': master_pricelist.currency_id.id,
        }])
        self.assertRecordValues(mapping_pricelist.rule_ids, [{
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
        }, {
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
        }])
        self.assertRecordValues(
            mapping_pricelist.rule_ids.filtered(is_discount_type_equal('fixed')).bulk_pricing_rule_ids,
            [{
                'quantity_min': 3,
                'discount_amount_fixed': 171.0,
            }],
        )
        self.assertRecordValues(
            mapping_pricelist.rule_ids.filtered(is_discount_type_equal('percent')).bulk_pricing_rule_ids,
            [{
                'quantity_min': 20,
                'discount_amount_percent': 50.0,
            }],
        )

    @patch_model('channel.pricelist', 'export_to_channel')
    def test_export_existing_pricelist(self, mock_export):
        master_pricelist = self.pricelist_1
        mapping_pricelist = self.env['channel.pricelist'].create({
            'name': 'abc',
            'currency_id': self.env.ref('base.CAD').id,
            'id_on_channel': 'price-list-1',
            'channel_id': self.bigcommerce_channel_1.id,
            'pricelist_id': master_pricelist.id,
        })
        wiz = self.env['export.pricelist.composer'].create({
            'pricelist_id': master_pricelist.id,
            'channel_id': self.bigcommerce_channel_1.id,
        })
        wiz.export()
        mock_export.assert_called_once()
        self.assertRecordValues(mapping_pricelist, [{
            'name': master_pricelist.name,
            'currency_id': master_pricelist.currency_id.id,
            'id_on_channel': 'price-list-1',
        }])
        self.assertRecordValues(mapping_pricelist.rule_ids, [{
            'product_channel_variant_id': self.mapping_1.product_variant_id.id,
            'is_override_lst_price': True,
            'override_lst_price': 169.0,
        }])


class TestMappingPricelistCommon(BigCommerceTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._set_up_mapping_products()
        cls._set_up_channel_customer_groups()

    @classmethod
    def _set_up_mapping_products(cls):
        prod_1 = cls.test_data['prod_1']
        cls.mapping_1 = cls.env['product.channel'].create({
            'name': prod_1.product_tmpl_id.name,
            'id_on_channel': 'mapping-1',
            'default_code': prod_1.product_tmpl_id.default_code,
            'channel_id': cls.bigcommerce_channel_1.id,
            'product_tmpl_id': prod_1.product_tmpl_id.id,
            'lst_price': prod_1.product_tmpl_id.list_price,
            'product_variant_ids': [
                (0, 0, {
                    'id_on_channel': f'{ioc}',
                    'product_product_id': prod_1.id,
                    'default_code': f'SKU - {ioc}',
                    'lst_price': 95.0,
                })
                for ioc in [100745, 100746, 100864, 100867]
            ]
        })

    @classmethod
    def _set_up_channel_customer_groups(cls):
        cls.customer_groups = cls.env['channel.customer.group'].create([{
            'name': 'Test-CG-1',
            'channel_id': cls.bigcommerce_channel_1.id,
            'id_on_channel': '23144',
        }, {
            'name': 'Test-CG-2',
            'channel_id': cls.bigcommerce_channel_1.id,
            'id_on_channel': '42547',
        }])


@tagged('post_install', 'basic_test', '-at_install')
class TestImportMappingPricelist(TestMappingPricelistCommon):

    @ignore_delay
    def test_import_new_pricelists(self):
        channel = self.bigcommerce_channel_1
        api = BigCommerceHelper.connect_with_channel(channel)

        with open(get_data_path(__file__, 'data/bigcommerce_get_pricelists.json'), 'r') as fp:
            pl_json = json.load(fp)
        pl_data = pl_json['data']

        with open(get_data_path(__file__, 'data/bigcommerce_get_pricelist_records.json'), 'r') as fp:
            plr_json = json.load(fp)
        plr_data = plr_json['data']

        with open(get_data_path(__file__, 'data/bigcommerce_get_pricelist_assignments.json'), 'r') as fp:
            pla_json = json.load(fp)
        pla_data = pla_json['data']

        ok_response = Mock(ok=Mock(return_value=True))
        pl_first_page_res = api.pricelists.create_collection_with(pl_data)
        pl_first_page_res.last_response = ok_response
        plr_first_page_res = api.pricelist_records.create_collection_with(plr_data)
        plr_first_page_res.last_response = ok_response
        plr_empty_page = api.pricelist_records
        plr_empty_page.last_response = ok_response
        pla_first_page_res = api.pricelist_assignments.create_collection_with(pla_data)
        pla_first_page_res.last_response = ok_response
        pla_empty_page = api.pricelist_assignments
        pla_empty_page.last_response = ok_response
        with patch_request(
                {'url': r'.*/pricelists$', 'jsn': pl_json},
                {'url': r'.*/pricelists/1/records$', 'jsn': plr_json},
                {'url': r'.*/pricelists/.*/records$', 'jsn': {'data': []}},
                {'url': r'.*/pricelists/assignments', 'jsn': pla_json},
        ), \
                patch.object(ph.PricelistImporter, '_get_next_page', return_value=iter([])), \
                patch.object(ph.PricelistRuleImporter, '_get_next_page', return_value=iter([])), \
                patch.object(ph.PricelistAssignmentImporter, '_get_next_page', return_value=iter([])):
            self.env['channel.pricelist'].bigcommerce_get_data(self.bigcommerce_channel_1, all_records=True)

        ids_on_channel = ['1', '23', '24']
        imported = self.env['channel.pricelist'].search([
            ('id_on_channel', 'in', ids_on_channel),
            ('channel_id', '=', self.bigcommerce_channel_1.id),
        ])
        self.assertEqual(len(imported), len(ids_on_channel))
        pl_1 = imported.filtered(lambda r: r.id_on_channel == '1')
        self.assertRecordValues(pl_1, [{
            'name': 'Test 3',
            'is_published': True,
            'currency_id': self.env.ref('base.USD').id,
        }])
        variants = self.mapping_1.product_variant_ids.sorted('id_on_channel')
        pl_1_rules = pl_1.rule_ids.sorted(lambda r: r.product_channel_variant_id.id_on_channel)
        self.assertRecordValues(pl_1_rules, [{
            'product_channel_variant_id': variants[0].id,
            'is_override_lst_price': True,
            'override_lst_price': 105.0,
            'bulk_pricing_discount_type': 'percent',
        }, {
            'product_channel_variant_id': variants[1].id,
            'is_override_lst_price': True,
            'override_lst_price': 105.0,
            'bulk_pricing_discount_type': 'fixed',
        }, {
            'product_channel_variant_id': variants[2].id,
            'is_override_lst_price': True,
            'override_lst_price': 5.0,
            'bulk_pricing_discount_type': 'percent',
        }, {
            'product_channel_variant_id': variants[3].id,
            'is_override_lst_price': True,
            'override_lst_price': 6.99,
            'bulk_pricing_discount_type': 'percent',
        }])
        self.assertRecordValues(pl_1_rules.bulk_pricing_rule_ids, [{
            'quantity_min': 2,
            'discount_amount': 0.0,
        }, {
            'quantity_min': 2,
            'discount_amount': 99.0,
        }, {
            'quantity_min': 2,
            'discount_amount': 0.0,
        }, {
            'quantity_min': 5,
            'discount_amount': 10.0,
        }, {
            'quantity_min': 2,
            'discount_amount': 10.0,
        }, {
            'quantity_min': 3,
            'discount_amount': 5.0,
        }])


@tagged('post_install', 'basic_test', '-at_install')
class TestExportMappingPricelist(TestMappingPricelistCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._set_up_pricelists()

    @classmethod
    def _set_up_pricelists(cls):
        variants = cls.mapping_1.product_variant_ids.sorted('id_on_channel')
        cls.mapping_pricelist_1 = cls.env['channel.pricelist'].create({
            'name': 'abc',
            'currency_id': cls.env.ref('base.USD').id,
            'channel_id': cls.bigcommerce_channel_1.id,
            'rule_ids': [(0, 0, {
                'product_channel_variant_id': variants[0].id,
                'is_override_lst_price': True,
                'override_lst_price': 105.0,
            }), (0, 0, {
                'product_channel_variant_id': variants[1].id,
                'bulk_pricing_discount_type': 'percent',
                'bulk_pricing_rule_ids': [(0, 0, {
                    'quantity_min': 2.0,
                    'discount_amount_percent': 10.0,
                })]
            })],
            'channel_customer_group_ids': [(6, 0, cls.customer_groups.ids)],
        })

    def test_export_pricelist(self):
        mapping_pricelist = self.mapping_pricelist_1
        plx_result = Mock(data={'id': 826491})

        with patch.object(ph.PricelistExporter, '_export_with', return_value=plx_result) as mock_pl_x, \
                patch.object(ph.PricelistRuleExporter, '_export_with') as mock_plr_x, \
                patch.object(ph.PricelistAssignmentExporter, '_export_with') as mock_pla_x:
            mapping_pricelist.bigcommerce_export_to_channel()
        mock_pl_x.assert_called_once_with({
            'name': 'abc',
            'active': False,
        })
        mock_plr_x.assert_called_once_with([{
            'variant_id': 100745,
            'currency': 'USD',
            'price': 105.0,
        }, {
            'variant_id': 100746,
            'currency': 'USD',
            'price': 95.0,
            'bulk_pricing_tiers': [{
                'quantity_min': 2,
                'type': 'percent',
                'amount': 10.0,
            }],
        }])
        mock_pla_x.assert_called_once_with([{
            'price_list_id': 826491,
            'customer_group_id': 23144,
        }, {
            'price_list_id': 826491,
            'customer_group_id': 42547,
        }])
        self.assertRecordValues(mapping_pricelist, [{
            'id_on_channel': '826491',
            'need_to_export': False,
            'is_sync_in_progress': False,
        }])

    def test_update_non_existing_pricelist(self):
        mapping_pricelist = self.mapping_pricelist_1
        mapping_pricelist.update({'id_on_channel': '826491'})

        error_response = Mock(
            ok=Mock(return_value=False),
            get_error=Mock(return_value='Error'),
            raise_for_status=Mock(side_effect=IOError),
        )
        mock_put_res = Mock(get_status_code=Mock(return_value=404), last_response=error_response)
        mock_post_res = Mock(get_status_code=Mock(return_value=404), data={'id': '826494'})
        with patch.object(ph.PricelistExportWorkflow, '_log_error_onto_pricelist') as mock_log, \
                patch.object(ph.PricelistExporter, '_put_with', return_value=mock_put_res) as mock_pl_put, \
                patch.object(ph.PricelistExporter, '_post_with', return_value=mock_post_res) as mock_pl_post, \
                patch.object(ph.PricelistRuleExporter, '_export_with') as mock_plr_x, \
                patch.object(ph.PricelistAssignmentExporter, '_export_with') as mock_pla_x:
            mapping_pricelist.bigcommerce_export_to_channel()

        mock_log.assert_not_called()
        mock_pl_put.assert_called_once()
        mock_pl_post.assert_called_once()
        mock_plr_x.assert_called_once()
        mock_pla_x.assert_called_once()
        self.assertRecordValues(mapping_pricelist, [{
            'id_on_channel': '826494',
            'need_to_export': False,
            'is_sync_in_progress': False,
        }])

    def test_export_error(self):
        mapping_pricelist = self.mapping_pricelist_1
        mapping_pricelist.update({'id_on_channel': '826491'})

        with patch_request(mtd='PUT', rfs=True) as mock_pl_x:
            mapping_pricelist.bigcommerce_export_to_channel()

        mock_pl_x.assert_called_once()
        self.assertRecordValues(mapping_pricelist, [{
            'id_on_channel': '826491',
            'is_sync_in_progress': False,
        }])


@tagged('post_install', 'basic_test', '-at_install')
class TestBulkPProductPricing(TestMappingPricelistCommon):
    def test_create_with_empty_amounts(self):
        variants = self.mapping_1.product_variant_ids.sorted('id_on_channel')
        mapping_pricelist = self.env['channel.pricelist'].create({
            'name': 'abc',
            'currency_id': self.env.ref('base.USD').id,
            'channel_id': self.bigcommerce_channel_1.id,
            'rule_ids': [(0, 0, {
                'product_channel_variant_id': variants[1].id,
                'bulk_pricing_discount_type': 'percent',
                'bulk_pricing_rule_ids': [(0, 0, {
                    'quantity_min': 2.0,
                    'discount_amount_percent': 10.0,
                    'discount_amount_fixed': 0.0,
                    'discount_amount_price': 0.0,
                })]
            })],
        })
        self.assertEqual(mapping_pricelist.rule_ids[0].bulk_pricing_rule_ids[0].discount_amount, 10.0)
