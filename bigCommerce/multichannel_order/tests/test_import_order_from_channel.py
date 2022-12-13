from copy import deepcopy

from unittest.mock import patch

from odoo.tools import mute_logger

from odoo.addons.omni_manage_channel.tests.utils import get_data_path

from .common import ChannelOrderTestCommon, ignore_delay, no_commit, tagged
from .utils import json_loads


@tagged('post_install', 'basic_test', '-at_install')
class TestImportOrderFromChannel(ChannelOrderTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_customer_channels()

    @classmethod
    def _add_customer_channels(cls):
        store = cls.test_data['store_1']
        customer = cls.test_data['main_contact_us_1']
        customer_id_on_channel = 23765765766

        # Create customer_channel for current store
        cls.test_data['customer_channel_1'] = cls.env['customer.channel'].create({
            'id_on_channel': customer_id_on_channel,
            'channel_id': store.id,
        })

    @classmethod
    def _update_order_data(cls, data):
        for line in data:
            # Update country_id in customer_data
            if 'customer_data' in line:
                if 'country_code' in line['customer_data']:
                    line['customer_data']['country_id'] = cls.env['res.country'].search([
                        ('code', '=', line['customer_data']['country_code'])
                    ], limit=1).id
                    del line['customer_data']['country_code']

    @ignore_delay
    @no_commit
    def test_import_order_from_channel_successfully(self):
        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

            # Call for synchronizing order data
            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=self.test_data['store_1'].id
            )

        order = self.env['sale.order'].search([
            ('name', '=', '1042'),
            ('channel_id', '=', self.test_data['store_1'].id)
        ], limit=1)

        # Check if the order info imported correctly
        self.assertRecordValues(order, [{
            'id_on_channel': '4540854665454',
            'amount_untaxed': 80,
            'amount_undiscounted': 88.5,
            'amount_tax': 8.5,
            'amount_total': 88.5,
            'channel_id': self.test_data['store_1'].id,
            'customer_message': 'Thanksgiving present for mom.',
        }])

        # Check if create new customer if not found
        with open(get_data_path(__file__, 'data/expected_result/import_order/customer_data.json')) as fp:
            customer = order.partner_id or order.customer_channel_id
            self.assertRecordValues(customer, json_loads(fp))

        # Check if the billing address and shipping address are imported correctly
        with open(get_data_path(__file__, 'data/expected_result/import_order/customer_invoice_data.json')) as fp:
            partner_invoice = order.partner_invoice_id
            self.assertRecordValues(partner_invoice, json_loads(fp))
        with open(get_data_path(__file__, 'data/expected_result/import_order/customer_shipping_data.json')) as fp:
            partner_shipping = order.partner_shipping_id
            self.assertRecordValues(partner_shipping, json_loads(fp))

        # Check if the order lines are imported correctly,
        # the special lines are computed and added to the special sections
        with open(get_data_path(__file__, 'data/expected_result/import_order/order_line_data.json')) as fp:
            order_line = order.order_line.sorted(lambda line: line.sequence) if order else None
            self.assertRecordValues(order_line, json_loads(fp))

    @mute_logger('odoo.addons.multichannel_order.models.sale_order')
    @ignore_delay
    @no_commit
    def test_import_order_from_channel_not_auto_create_product_if_missing(self):
        with patch('odoo.addons.omni_log.models.omni_log.OmniLog.create') as mock_omni_log_create:
            with open(get_data_path(__file__, 'data/order_data_2.json')) as fp:
                data = json_loads(fp, datetime_fields=['channel_date_created'])
                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=self.test_data['store_1'].id
                )

            # Check if log the error when missing product
            self.assertEqual(mock_omni_log_create.call_args.args[0]['message'], 'SKU not found')
            self.assertEqual(
                len(self.env['sale.order'].search([
                    ('channel_id', '=', self.test_data['store_1'].id)
                ], limit=1)),
                0
            )

    @ignore_delay
    @no_commit
    def test_import_order_from_channel_auto_create_product_if_missing(self):
        customer_channel = self.test_data['customer_channel_1']
        store = customer_channel.channel_id

        with open(get_data_path(__file__, 'data/order_data_2.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            data[0]['customer_id'] = customer_channel.id_on_channel
            data[0]['customer_data'] = self.shared_data['partner_us_1_data']
            data[0]['customer_data'].update({
                'id': customer_channel.id_on_channel
            })

            with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder.create_waiting_job') \
                    as create_waiting_job:
                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=self.test_data['store_1'].id
                )
                # Check if call for import missing product
                create_waiting_job.assert_called_once_with(store, data[0]['lines'], data[0])

    @ignore_delay
    @no_commit
    def test_update_order_after_importing(self):
        # Import the first time
        with open(get_data_path(__file__, 'data/order_data_3.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=self.test_data['store_1'].id
            )

        order = self.env['sale.order'].search([
            ('name', '=', '1042'),
            ('channel_id', '=', self.test_data['store_1'].id)
        ], limit=1)
        self.assertRecordValues(order, [{
            'id_on_channel': '4540854665454',
            'amount_untaxed': 10,
            'amount_undiscounted': 10,
            'amount_tax': 0,
            'amount_total': 10,
            'channel_id': self.test_data['store_1'].id,
            'customer_message': 'Thanksgiving present for mom.',
        }])

        with open(get_data_path(__file__, 'data/expected_result/update_order/first_importing_time/customer_data.json')) as fp:
            customer = order.partner_id or order.customer_channel_id
            self.assertRecordValues(customer, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/first_importing_time/customer_invoice_data.json')) as fp:
            partner_invoice = order.partner_invoice_id
            self.assertRecordValues(partner_invoice, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/first_importing_time/customer_shipping_data.json')) as fp:
            partner_shipping = order.partner_shipping_id
            self.assertRecordValues(partner_shipping, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/first_importing_time/order_line_data.json')) as fp:
            order_line = order.order_line.sorted(lambda line: line.sequence) if order else None
            self.assertRecordValues(order_line, json_loads(fp))

        # Import the second time
        with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._log_exception_shipping_address_changes'):
            with open(get_data_path(__file__, 'data/order_data_4.json')) as fp:
                data = json_loads(fp, datetime_fields=['channel_date_created'])
                self._update_order_data(data)

                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=self.test_data['store_1'].id,
                    update=True
                )

        order = self.env['sale.order'].search([
            ('name', '=', '1042'),
            ('channel_id', '=', self.test_data['store_1'].id)
        ], limit=1)
        self.assertRecordValues(order, [{
            'id_on_channel': '4540854665454',
            'amount_untaxed': 100,
            'amount_undiscounted': 100,
            'amount_tax': 0,
            'amount_total': 100,
            'channel_id': self.test_data['store_1'].id,
            'customer_message': 'Nothing to say to you, mom.',
        }])

        with open(get_data_path(__file__, 'data/expected_result/update_order/second_importing_time/customer_data.json')) as fp:
            customer = order.partner_id or order.customer_channel_id
            self.assertRecordValues(customer, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/second_importing_time/customer_invoice_data.json')) as fp:
            partner_invoice = order.partner_invoice_id
            self.assertRecordValues(partner_invoice, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/second_importing_time/customer_shipping_data.json')) as fp:
            partner_shipping = order.updated_shipping_address_id
            self.assertRecordValues(partner_shipping, json_loads(fp))

        with open(get_data_path(__file__, 'data/expected_result/update_order/second_importing_time/order_line_data.json')) as fp:
            order_line = order.order_line.sorted(lambda line: line.sequence) if order else None
            self.assertRecordValues(order_line, json_loads(fp))

    @ignore_delay
    @no_commit
    def test_import_order_from_channel_with_custom_product(self):
        with open(get_data_path(__file__, 'data/order_data_2.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            the_line = data[0]['lines'][0]
            the_line.update({
                'variant_id': 'None',
                'product_id': 'None',
            })

        mock_prepare_custom = self._create_order_with_custom_product(data)
        self.assertEqual(mock_prepare_custom.call_count, 1)

        product = self.env['product.product'].search([('default_code', '=', the_line['sku'])])
        self.assertRecordValues(product, [{
            'name': 'Picture 1',
            'type': 'consu',
            'is_custom_product': True,
            'lst_price': 100.0,
        }])
        self.assertRecordValues(product.product_tmpl_id, [{
            'name': 'Picture 1',
            'type': 'consu',
            'lst_price': 100.0,
        }])

    def _create_order_with_custom_product(self, data, **kwargs):
        sale_order_model = self.env['sale.order']
        with patch.object(
                type(sale_order_model),
                '_prepare_imported_order_lines_generate_custom_product',
                side_effect=sale_order_model._prepare_imported_order_lines_generate_custom_product
        ) as mock_prepare_custom:
            sale_order_model.create_jobs_for_synching(
                vals_list=data,
                channel_id=self.test_data['store_1'].id,
                **kwargs
            )

        return mock_prepare_custom

    @ignore_delay
    @no_commit
    def test_import_order_from_channel_with_custom_product_and_update(self):
        """
        Custom products should only be checked and created when its line is not in the system yet
        """
        with open(get_data_path(__file__, 'data/order_data_2.json')) as fp:
            sample = json_loads(fp, datetime_fields=['channel_date_created'])

        data = deepcopy(sample)
        the_line = data[0]['lines'][0]
        the_line.update({
            'variant_id': 'None',
            'product_id': 'None',
        })

        mock_prepare_custom = self._create_order_with_custom_product(data)
        self.assertEqual(mock_prepare_custom.call_count, 1)

        order = self.env['sale.order'].search([
            ('id_on_channel', '=', '4540854665454'),
            ('channel_id', '=', self.test_data['store_1'].id),
        ])
        # Manually confirm this order because it is not automatically confirmed
        order.action_confirm()

        data = deepcopy(sample)
        the_line = data[0]['lines'][0]
        the_line.update({
            'variant_id': 'None',
            'product_id': 'None',
        })

        mock_prepare_custom = self._create_order_with_custom_product(data, update=True)
        self.assertEqual(mock_prepare_custom.call_count, 0)

        data = deepcopy(sample)
        first_line = data[0]['lines'][0]
        first_line.update({
            'variant_id': 'None',
            'product_id': 'None',
        })
        data[0]['lines'].append({
            'id_on_channel': '11746959261936',
            'name': 'Picture 3',
            'variant_id': 'None',
            'product_id': 'None',
            'sku': 'P-7894635',
            'type': 'consu',
            'price': 75.0,
            'quantity': 9.0,
        })

        mock_prepare_custom = self._create_order_with_custom_product(data, update=True)
        self.assertEqual(mock_prepare_custom.call_count, 1)

    def test_process_custom_products(self):
        sale_order_model = self.env['sale.order']
        line_1 = dict(sku='test-prod-78546320', name='test-prod-78546320', type='service', price=52.25)
        prod_1 = sale_order_model._prepare_imported_order_lines_generate_custom_product(line_1)
        self.assertRecordValues(prod_1, [{
            'name': 'test-prod-78546320',
            'default_code': 'test-prod-78546320',
            'type': 'service',
            'is_custom_product': True,
            'lst_price': 52.25,
        }])

        line_2 = dict(sku='test-prod-78546320', name='test-prod-78546321', type='consu', price=52.75)
        prod_2 = sale_order_model._prepare_imported_order_lines_generate_custom_product(line_2)
        self.assertEqual(prod_1, prod_2)

    def test_process_custom_products_wo_sku(self):
        sale_order_model = self.env['sale.order']
        line_1 = dict(sku='', name='test-prod-78546320', type='service', price=52.25)
        prod_1 = sale_order_model._prepare_imported_order_lines_generate_custom_product(line_1)
        self.assertRecordValues(prod_1, [{
            'name': 'test-prod-78546320',
            'default_code': '',
            'type': 'service',
            'is_custom_product': True,
            'lst_price': 52.25,
        }])

        line_2 = dict(sku='', name='test-prod-78546320', type='service', price=52.25)
        prod_2 = sale_order_model._prepare_imported_order_lines_generate_custom_product(line_2)
        self.assertRecordValues(prod_2, [{
            'name': 'test-prod-78546320',
            'default_code': '',
            'type': 'service',
            'is_custom_product': True,
            'lst_price': 52.25,
        }])
        self.assertNotEqual(prod_1, prod_2)
