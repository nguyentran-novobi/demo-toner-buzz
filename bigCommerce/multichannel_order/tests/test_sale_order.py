# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.sale.tests.common import TestSaleCommonBase


@tagged('post_install', 'basic_test', '-at_install')
class TestCancelOnlineOrderWorkflow(TestSaleCommonBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.ref('base.main_company')

        with patch('odoo.addons.multichannel_product.models.product.ProductProduct.check_unique_default_code'):
            cls.company_data = cls.setup_sale_configuration_for_company(cls.company)
        cls.set_up_partners()
        cls.set_up_sale_orders()

    @classmethod
    def set_up_partners(cls):
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'partner_a',
        })

    @classmethod
    def set_up_sale_orders(cls):
        cls.order_1 = cls.env['sale.order'].with_context(mail_notrack=True, mail_create_nolog=True).create({
            'partner_id': cls.partner_a.id,
            'partner_invoice_id': cls.partner_a.id,
            'partner_shipping_id': cls.partner_a.id,
            'order_line': [
                (0, 0, {
                    'name': cls.company_data['product_order_cost'].name,
                    'product_id': cls.company_data['product_order_cost'].id,
                    'product_uom_qty': 2,
                    'qty_delivered': 2,
                    'product_uom': cls.company_data['product_order_cost'].uom_id.id,
                    'price_unit': cls.company_data['product_order_cost'].list_price,
                })
            ],
        })

    @patch('odoo.addons.multichannel_order.wizard.order_channel_cancel_confirmation'
           '.OrderChannelCancelConfirmation.do_cancel_order_on_channel', return_value=True)
    def test_cancel_online_order_full_options(self, mock_cancel_online):
        self.order_1.action_confirm()
        ctx = dict(active_model=self.order_1._name, active_ids=self.order_1.ids)
        wiz1 = self.env['sale.advance.payment.inv'].with_context(ctx).create({
            'advance_payment_method': 'delivered'
        })
        wiz1.create_invoices()
        invoice = self.order_1.invoice_ids[0]
        invoice.action_post()
        self.order_1.with_context(disable_cancel_warning=True).action_cancel()

        wiz2 = self.env['order.channel.cancel.confirmation'].create({
            'sale_order_id': self.order_1.id,
            'is_credit_note_creation_enabled': True,
            'credit_note_reason': 'test_reason',
            'is_notification_email_enabled': True,
        })

        wiz2.button_confirm()
        mock_cancel_online.assert_called_once()

        credit_note = self.order_1.invoice_ids.filtered(lambda inv: inv.move_type == 'out_refund')
        self.assertIn('test_reason', credit_note.ref)

        new_mail = self.env['mail.mail'].search([('model', '=', self.order_1._name), ('res_id', '=', self.order_1.id)])
        self.assertTrue(new_mail)
