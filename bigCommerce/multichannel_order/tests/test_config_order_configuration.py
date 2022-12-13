import datetime

from unittest.mock import patch

from odoo import Command

from odoo.addons.omni_manage_channel.tests.utils import get_data_path

from .common import ChannelOrderTestCommon, ignore_delay, no_commit, tagged
from .utils import json_loads


@tagged('post_install', 'basic_test', '-at_install')
class TestConfigChannelOrderConfiguration(ChannelOrderTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_customer_channels()
        cls._add_order_status_channels()
        cls._update_store_order_configuration()

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
    def _add_order_status_channels(cls):
        # Create fulfillment status
        unfulfilled_status = cls.env['order.status.channel'].create({
            'name': 'unfulfilled',
            'platform': 'none',
            'type': 'fulfillment'
        })
        fulfilled_status = cls.env['order.status.channel'].create({
            'name': 'fulfilled',
            'platform': 'none',
            'type': 'fulfillment'
        })

        # Create payment status
        unpaid_status = cls.env['order.status.channel'].create({
            'name': 'unpaid',
            'platform': 'none',
            'type': 'payment'
        })
        paid_status = cls.env['order.status.channel'].create({
            'name': 'paid',
            'platform': 'none',
            'type': 'payment'
        })

        # Update to test_data
        cls.test_data['fulfillment_status'] = {
            'unfulfilled': unfulfilled_status,
            'fulfilled': fulfilled_status
        }
        cls.test_data['payment_status'] = {
            'unpaid': unpaid_status,
            'paid': paid_status
        }

    @classmethod
    def _update_store_order_configuration(cls):
        store = cls.test_data['store_1']
        store.write({
            'order_process_rule_ids': [Command.clear(), Command.create({
                'name': 'Default',
                'channel_id': store.id,
                'order_status_channel_ids': [Command.link(cls.test_data['fulfillment_status']['unfulfilled'].id)],
                'payment_status_channel_ids': [Command.link(cls.test_data['payment_status']['paid'].id)],
                'is_order_confirmed': False,
                'is_invoice_created': False,
                'is_payment_created': False,
            })]
        })

    @classmethod
    def mock_get_order_status_channel(cls, status, channel, type='fulfillment'):
        if type == 'fulfillment':
            if status in cls.test_data['fulfillment_status']:
                return cls.test_data['fulfillment_status'][status]
        if type == 'payment':
            if status in cls.test_data['payment_status']:
                return cls.test_data['payment_status'][status]

        return None

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
    def test_import_order_based_on_date(self):
        store = self.test_data['store_1']
        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)
        datum = data[0]
        datum.update({
            'status_id': 'unfulfilled',
            'payment_status_id': 'paid',
            'date_order': datetime.date(2021, 11, 2),
        })

        with patch.object(type(self.env['sale.order']), '_get_order_status_channel',
                          side_effect=self.mock_get_order_status_channel):
            with self.subTest('Order date is prior'):
                store.min_order_date_to_import = datetime.date(3500, 1, 1)
                is_allowed = so_env._check_imported_order_data(store, datum)
                self.assertFalse(is_allowed)

            with self.subTest('Min order date is not set'):
                store.min_order_date_to_import = False
                is_allowed = so_env._check_imported_order_data(store, datum)
                self.assertTrue(is_allowed)

            with self.subTest('Order date is after'):
                store.min_order_date_to_import = datetime.date(1000, 1, 1)
                is_allowed = so_env._check_imported_order_data(store, datum)
                self.assertTrue(is_allowed)

    @ignore_delay
    @no_commit
    def test_import_order_based_on_status(self):
        store = self.test_data['store_1']
        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

        with patch.object(type(self.env['sale.order']), '_get_order_status_channel',
                          side_effect=self.mock_get_order_status_channel):
            with self.subTest('Fulfillment status not in order configuration'):
                data[0]['status_id'] = 'fulfilled'
                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=store.id
                )
                order = so_env.search([('id_on_channel', '=', '4540854665454'), ('channel_id', '=', store.id)])
                self.assertEqual(len(order), 0)

            with self.subTest('Payment status not in order configuration'):
                data[0]['status_id'] = 'unfulfilled'
                data[0]['payment_status_id'] = 'unpaid'
                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=store.id
                )
                order = so_env.search([('id_on_channel', '=', '4540854665454'), ('channel_id', '=', store.id)])
                self.assertEqual(len(order), 0)

            with self.subTest('Fulfillment and payment status in order configuration'):
                data[0]['payment_status_id'] = 'paid'
                self.env['sale.order'].create_jobs_for_synching(
                    vals_list=data,
                    channel_id=store.id
                )
                order = so_env.search([('id_on_channel', '=', '4540854665454'), ('channel_id', '=', store.id)])
                self.assertEqual(len(order), 1)

    @ignore_delay
    @no_commit
    def test_not_confirm_order_when_importing(self):
        store = self.test_data['store_1']
        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

        with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._get_order_status_channel',
                   side_effect=self.mock_get_order_status_channel):
            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=store.id
            )
            order = so_env.search([('name', '=', '1042'), ('channel_id', '=', store.id)], limit=1)
            self.assertEqual(len(order), 1)
            self.assertEqual(order.state, 'draft')

    @ignore_delay
    @no_commit
    def test_confirm_order_when_importing(self):
        store = self.test_data['store_1']
        store.order_process_rule_ids[0].is_order_confirmed = True

        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

        with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._get_order_status_channel',
                   side_effect=self.mock_get_order_status_channel):
            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=store.id
            )
            order = so_env.search([('name', '=', '1042'), ('channel_id', '=', store.id)], limit=1)
            self.assertEqual(len(order), 1)

            # Test if order confirmed
            self.assertEqual(order.state, 'sale')

            # Test if no invoices created
            self.assertEqual(order.invoice_count, 0)
            self.assertEqual(order.invoice_status, 'to invoice')

            # Test if no payments created
            self.assertEqual(order.deposit_count, 0)

    @ignore_delay
    @no_commit
    def test_create_invoice_when_importing(self):
        store = self.test_data['store_1']
        store.order_process_rule_ids[0].is_order_confirmed = True
        store.order_process_rule_ids[0].is_invoice_created = True

        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

        with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._get_order_status_channel',
                   side_effect=self.mock_get_order_status_channel):
            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=store.id
            )
            order = so_env.search([('name', '=', '1042'), ('channel_id', '=', store.id)], limit=1)
            self.assertEqual(order.invoice_count, 1)
            self.assertEqual(order.invoice_status, 'invoiced')
            self.assertEqual(order.invoice_ids[0].amount_total, 88.5)

    @ignore_delay
    @no_commit
    def test_create_payment_when_importing(self):
        store = self.test_data['store_1']
        store.order_process_rule_ids[0].is_order_confirmed = True
        store.order_process_rule_ids[0].is_payment_created = True

        so_env = self.env['sale.order']

        with open(get_data_path(__file__, 'data/order_data_1.json')) as fp:
            data = json_loads(fp, datetime_fields=['channel_date_created'])
            self._update_order_data(data)

        with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._get_order_status_channel',
                   side_effect=self.mock_get_order_status_channel):
            self.env['sale.order'].create_jobs_for_synching(
                vals_list=data,
                channel_id=store.id
            )
            order = so_env.search([('name', '=', '1042'), ('channel_id', '=', store.id)], limit=1)
            self.assertEqual(order.deposit_count, 1)
            self.assertEqual(order.deposit_ids[0].amount, 88.5)
