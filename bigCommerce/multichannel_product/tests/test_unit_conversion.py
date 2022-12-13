# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


class TestChannelUnitConversionCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._set_up_settings()
        cls._set_up_channels()

    @classmethod
    def _set_up_settings(cls):
        icp_sudo = cls.env['ir.config_parameter'].sudo()
        icp_sudo.set_param('product.weight_in_lbs', '0')  # kg
        icp_sudo.set_param('product.volume_in_cubic_feet', '0')  # m

    @classmethod
    def _set_up_channels(cls):
        cls.channel_1 = cls.env['ecommerce.channel'].create({
            'platform': False,
            'name': 'conversion',
        })

    @classmethod
    def _set_unit(cls, channel, weight=None, length=None):
        if weight is not None:
            channel.weight_unit = weight
        if length is not None:
            channel.dimension_unit = length


@tagged('post_install', 'basic_test', '-at_install')
class TestChannelUnitConversion(TestChannelUnitConversionCommon):
    def test_weight_conversion(self):
        cases = [
            dict(value=76.66, from_='oz', to='oz', expected=76.66),
            dict(value=26.2, from_='g', to='kg', expected=0.0262),
            dict(value=20.95, from_='kg', to='lb', expected=46.18685),
            dict(value=35.65, from_='oz', to='g', expected=1010.66),
            dict(value=16.53, from_='oz', to='kg', expected=0.4686176),
            dict(value=39.49, from_='kg', to='oz', expected=1392.969),
            dict(value=95.36, from_='g', to='lb', expected=0.2102328),
        ]
        for case in cases:
            self._set_unit(self.channel_1, weight=case['to'])
            res = self.channel_1._convert_channel_weight(case['value'], unit=case['from_'])
            self.assertAlmostEqual(res, case['expected'], places=2)

    def test_weight_conversion_inverse(self):
        cases = [
            dict(value=76.66, from_='oz', to='oz', expected=76.66),
            dict(value=26.2, from_='g', to='kg', expected=26200),
            dict(value=20.95, from_='kg', to='lb', expected=9.50276),
            dict(value=35.65, from_='oz', to='g', expected=1.257517),
            dict(value=16.53, from_='oz', to='kg', expected=583.0786),
            dict(value=39.49, from_='kg', to='oz', expected=1.119523),
            dict(value=95.36, from_='g', to='lb', expected=43254.62),  # Deviation
        ]
        for case in cases:
            self._set_unit(self.channel_1, weight=case['to'])
            res = self.channel_1._convert_channel_weight(case['value'], unit=case['from_'], inverse=True)
            self.assertAlmostEqual(res, case['expected'], places=2)

    def test_length_conversion(self):
        cases = [
            dict(value=76.66, from_='in', to='in', expected=76.66),
            dict(value=26.2, from_='cm', to='m', expected=0.262),
            dict(value=20.95, from_='m', to='yd', expected=22.9112),
            dict(value=35.65, from_='in', to='cm', expected=90.551),
            dict(value=16.53, from_='in', to='m', expected=0.419862),
            dict(value=39.49, from_='m', to='in', expected=1554.724),
            dict(value=95.36, from_='cm', to='yd', expected=1.04287),
        ]
        for case in cases:
            self._set_unit(self.channel_1, length=case['to'])
            res = self.channel_1._convert_channel_dimension(case['value'], unit=case['from_'])
            self.assertAlmostEqual(res, case['expected'], places=2)
