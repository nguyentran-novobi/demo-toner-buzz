# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceSaleOrder(BigCommerceTestCommon):

    @classmethod
    def _add_sale_orders(cls):
        test_data = cls.test_data
        sale_order_model = cls.env['sale.order']
        sale_order_line_model = cls.env['sale.order.line']

        open_status = cls.env['order.status.channel'].search([
            ('platform', '=', 'bigcommerce'),
            ('id_on_channel', '=', '9'),
        ], limit=1)
        # Simple order with all deliverable items and discounts and taxes
        simple_order = sale_order_model.create({
            'partner_id': test_data['main_contact_us_1'].id,
            'partner_invoice_id': test_data['billing_address_us_1'].id,
            'partner_shipping_id': test_data['shipping_address_us_1'].id,
            'company_id': test_data['company_1'].id,
            'warehouse_id': test_data['company_1_warehouse_1'].id,
            'channel_id': cls.bigcommerce_channel_1.id,
            'staff_notes': 'This order is only a test from the customer',
            'customer_message': 'I am actually a staff',
            'order_status_channel_id': open_status.id,
            'id_on_channel': '46894679',
            'channel_date_created': datetime(2018, 3, 15),
            'date_order': datetime(2018, 3, 15),
            'customer_channel_id': test_data['customer_bigcommerce_us_1'].id,
            'updated_shipping_address_id': test_data['shipping_address_us_1'].id,
            'channel_order_ref': '2512',
        })
        # Order Items
        sale_order_line_model.create({
            'name': test_data['consum_1'].name,
            'product_id': test_data['consum_1'].id,
            'product_uom_qty': 1,
            'product_uom': test_data['consum_1'].uom_id.id,
            'price_unit': test_data['consum_1'].list_price,
            'order_id': simple_order.id,
            'tax_id': False,
            'quantity_on_channel': 1,
            'id_on_channel': '7865898486',
            'qty_delivered_on_channel': 0,
            'discount_amount': 0,
            'sequence': 1,
        })
        sale_order_line_model.create({
            'name': test_data['serv_1'].name,
            'product_id': test_data['serv_1'].id,
            'product_uom_qty': 1,
            'product_uom': test_data['serv_1'].uom_id.id,
            'price_unit': test_data['serv_1'].list_price,
            'order_id': simple_order.id,
            'tax_id': False,
            'quantity_on_channel': 1,
            'id_on_channel': '7865898488',
            'qty_delivered_on_channel': 0,
            'discount_amount': 0,
            'sequence': 1,
        })
        sale_order_line_model.create({
            'name': test_data['prod_1'].name,
            'product_id': test_data['prod_1'].id,
            'product_uom_qty': 1,
            'product_uom': test_data['prod_1'].uom_id.id,
            'price_unit': test_data['prod_1'].list_price,
            'order_id': simple_order.id,
            'tax_id': False,
            'quantity_on_channel': 1,
            'id_on_channel': '7865898489',
            'qty_delivered_on_channel': 0,
            'discount_amount': 0,
            'sequence': 1,
        })
        # Discounts
        discount_product = cls.env.ref('multichannel_order.discount_product') \
            .with_context(active_test=False).product_variant_ids[:1]
        sale_order_line_model.create({
            'product_id': discount_product.id,
            'name': 'Discount - Happy New Year',
            'order_id': simple_order.id,
            'product_uom_qty': 1,
            'price_unit': 2.99,
            'tax_id': [(5, 0, 0)],
            'is_discount': True,
            'sequence': 3,
        })
        # Taxes
        tax_product = cls.env.ref('multichannel_order.tax_product_template') \
            .with_context(active_test=False).product_variant_ids[:1]
        sale_order_line_model.create({
            'product_id': tax_product.id,
            'name': 'Tax - VAT',
            'order_id': simple_order.id,
            'product_uom_qty': 1,
            'price_unit': 2.99,
            'tax_id': [(5, 0, 0)],
            'is_tax': True,
            'sequence': 7,
        })

        cls.simple_order = simple_order

    def set_up_environment(self):
        test_data = self.test_data
        self._set_up_environment(
            user=test_data['admin_user'],
            company=test_data['company_1'],
        )