# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.omni_manage_channel.models.customer_channel import compare_address, _phonenumbers_lib_imported
from .common import ListingTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestCustomerChannel(ListingTestCommon):
    def test_compare_address(self):
        self.assertTrue(compare_address(self.env['res.partner'].new({
            'name': 'Isabelle F Carr',
            'phone': '912-314-5149',
            'email': 'msisabelle@test.mail',
            'street': '959 Adamsville Road',
            'street2': 'Apt 242',
            'city': 'Metter',
            'zip': '30439',
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_11').id,
            'company_name': 'Landskip Yard Care',
            'type': 'delivery',
        }), {
            'name': 'Isabelle F Carr',
            'phone': '912-314-5149',
            'email': 'msisabelle@test.mail',
            'street_1': '959 Adamsville Road',
            'street_2': 'Apt 242',
            'city': 'Metter',
            'zip': '30439',
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_11').id,
        }))

        if _phonenumbers_lib_imported:
            self.assertTrue(compare_address(self.env['res.partner'].new({
                'name': 'Isabelle F Carr',
                'phone': '+1 912-314-5149',
                'email': 'msisabelle@test.mail',
                'street': '959 Adamsville Road',
                'street2': 'Apt 242',
                'city': 'Metter',
                'zip': '30439',
                'country_id': False,
            }), {
                'name': 'Isabelle F Carr',
                'phone': '9123145149',
                'email': 'msisabelle@test.mail',
                'street_1': '959 Adamsville Road',
                'street_2': 'Apt 242',
                'city': 'Metter',
                'zip': '30439',
                'country_id': '',
                'state_id': '',
            }, country_code='US'))

        self.assertTrue(compare_address(self.env['res.partner'].new({
            'name': 'Isabelle F Carr',
            'email': 'msisabelle@test.mail',
            'street': '959 Adamsville Road',
            'city': 'Metter',
            'zip': '30439',
            'country_id': False,
        }), {
            'name': 'Isabelle F Carr',
            'phone': False,
            'email': 'msisabelle@test.mail',
            'street_1': '959 Adamsville Road',
            'street_2': None,
            'city': 'Metter',
            'zip': '30439',
            'country_id': '',
            'state_id': '',
        }))

        self.assertFalse(compare_address(self.env['res.partner'].new({
            'street': '959 Adamsville Road',
            'city': 'Metter',
            'zip': '30439',
            'country_id': False,
        }), {
            'name': '',
            'phone': False,
            'email': '',
            'street_1': '959 Adamsville Road',
            'street_2': None,
            'city': 'Metter',
            'zip': '30539',
            'country_id': '',
            'state_id': '',
        }))

        self.assertFalse(compare_address(self.env['res.partner'].new({
            'street': '959 Adamsville Road',
            'city': 'Metter',
            'zip': '30439',
            'country_id': False,
        }), {
            'name': '',
            'phone': False,
            'email': '',
            'street_1': None,
            'street_2': None,
            'city': 'Metter',
            'zip': '30439',
            'country_id': '',
            'state_id': '',
        }))
