# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from .utils import get_data_path


@tagged('post_install', 'basic_test', '-at_install')
class TestUtils(TransactionCase):

    def test_get_data_path(self):
        res1 = get_data_path('/opt/odoo/test.py', 'data/demo1.xml')
        self.assertEqual(res1, '/opt/odoo/data/demo1.xml')

        res2 = get_data_path(__file__, 'data/demo2.csv')
        res2_p = res2.replace('data/demo2.csv', '')
        self.assertTrue(res2.endswith('data/demo2.csv'))
        self.assertIn(res2_p, __file__)
        self.assertNotEqual(res2_p, __file__)
