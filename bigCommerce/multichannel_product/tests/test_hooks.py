from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

from odoo.addons.multichannel_product.hooks import pre_init_hook


@tagged('post_install', 'basic_test', '-at_install')
class TestHooks(TransactionCase):
    def test_default_code_check_ok(self):
        pre_init_hook(self.env.cr)

    def test_default_code_check_failed(self):
        self.env['product.product'].with_context(for_synching=True).create([{
            'name': 'test-product-dup-1',
            'default_code': 'test-product-dup',
        }, {
            'name': 'test-product-dup-2',
            'default_code': 'test-product-dup',
        }])

        with self.assertRaises(ValidationError):
            pre_init_hook(self.env.cr)
