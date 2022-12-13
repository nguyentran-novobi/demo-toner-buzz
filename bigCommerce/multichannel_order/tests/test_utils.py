# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from .utils import map_address


@tagged('post_install', 'basic_test', '-at_install')
class TestUtils(TransactionCase):
    def test_map_address(self):
        self.assertDictEqual(map_address(dict(a=3)), dict(a=3))

        self.assertDictEqual(map_address(dict(b=2), mapping=dict(b='a')), dict(a=2))
        self.assertDictEqual(map_address(dict(a=3, b=2), mapping=dict(b='c')), dict(a=3, c=2))

        self.assertDictEqual(map_address(dict(a=3, b=2), default=dict(d=3)), dict(a=3, b=2, d=3))
        self.assertDictEqual(map_address(dict(a=3, b=2), default=dict(b=3)), dict(a=3, b=3))

        self.assertDictEqual(map_address(dict(a=3, b=2), excluded={'b'}), dict(a=3))
        self.assertDictEqual(map_address(dict(b=2, d=4), excluded={'b', 'c', 'd'}), dict())

        self.assertDictEqual(map_address(dict(a=3, b=2, d=4),
                                         mapping=dict(a='c', d='f'),
                                         default=dict(e=5, g=1),
                                         excluded={'b', 'c', 'd'}),
                             dict(c=3, e=5, f=4, g=1))
        