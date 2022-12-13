from .common import ChannelOrderTestCommon, tagged
from unittest.mock import patch
from .common import ignore_delay, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class TestDetermineCustomer(ChannelOrderTestCommon):

    def setUp(self):
        super().setUp()
        self.invoice_info = {
            'name': 'invoice_name',
            'phone': 'invoice_phone',
            'email': 'invoice_email',
            'street': 'invoice_street',
            'street2': 'invoice_street2',
            'city': 'invoice_city',
            'state_id': False,
            'country_id': False,
            'zip': 'invoice_zip',
            'type': 'invoice',
            'customer_rank': 1
        }
        self.shipping_info = {
            'name': 'shipping_name',
            'phone': 'shipping_phone',
            'email': 'shipping_email',
            'street': 'shipping_street',
            'street2': 'shipping_street2',
            'city': 'shipping_city',
            'state_id': False,
            'country_id': False,
            'zip': 'invoice_zip',
            'type': 'delivery',
            'customer_rank': 1
        }
        self.order_number = "S0001"

    def test_determine_customer_with_invoice_info(self):
        customer_channel = self.env['customer.channel'].browse()
        customer_channel, partner, partner_invoice, partner_shipping = customer_channel.determine_customer(self.test_data['store_1'], self.invoice_info, False, self.order_number)
        self.assertEqual(partner_invoice.name, 'invoice_name')

    def test_determine_customer_with_shipping_info(self):
        customer_channel = self.env['customer.channel'].browse()
        customer_channel, partner, partner_invoice, partner_shipping = customer_channel.determine_customer(self.test_data['store_1'], False, self.shipping_info, self.order_number)
        self.assertEqual(partner_shipping.name, 'shipping_name')

    def test_determine_customer_without_invoice_shipping_info(self):
        customer_channel = self.env['customer.channel'].browse()
        customer_channel, partner, partner_invoice, partner_shipping = customer_channel.determine_customer(self.test_data['store_1'], False, False, self.order_number)
        self.assertEqual(partner.name, 'Guest Customer Name S0001')
