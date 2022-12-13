# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.channel_base_sdk.utils.common import resource_formatter


class UomNotFoundError(Exception):
    pass


class UnitConverter:
    """
    This converter will try its best to use Odoo functionality when do the conversion
    If Odoo doesn't support *any* of the specified unit of measure,
    this will fallback and use external converter
    """

    def __init__(self, obj):
        self.env = obj.env

    def convert_weight(self, weight, from_unit, to_unit):
        """
        Convert weight from `from_unit` to `to_unit`
        unit can be either unit of measure name or Odoo uom.uom record
        """
        try:
            return self._platform_convert_unit(weight, from_unit, to_unit)
        except UomNotFoundError:
            return self._external_convert_weight(weight, from_unit, to_unit)

    def _platform_convert_unit(self, value, from_unit, to_unit):
        from_unit, to_unit = self._get_uom_from(from_unit), self._get_uom_from(to_unit)
        return from_unit._compute_quantity(value, to_unit, round=False)

    def _get_uom_from(self, obj):
        """
        Extract unit of measure name from `obj`
        `obj` can be either the name or Odoo uom.uom record
        """
        def ensure_uom(ref):
            if ref._name == 'uom.uom':
                return ref
            raise AttributeError()

        def find_uom(ref):
            res = self.env['uom.uom'].search([('name', '=', str(ref))], limit=1)
            if not res:
                raise UomNotFoundError()
            return res

        try:
            return ensure_uom(obj)
        except AttributeError:
            return find_uom(obj)

    @classmethod
    def _external_convert_weight(cls, weight, from_unit, to_unit):
        """
        Convert weight from `from_unit` to `to_unit`
        unit must be either unit of measure name
        """
        from_unit, to_unit = cls._get_unit_from(from_unit), cls._get_unit_from(to_unit)
        convert = resource_formatter.WeightConversionTrans(from_unit=from_unit, to_unit=to_unit)
        return convert(weight)

    @classmethod
    def _get_unit_from(cls, obj):
        """
        Extract unit of measure name from `obj`
        `obj` can be either the name or Odoo uom.uom record
        """
        try:
            return str(obj.name)
        except AttributeError:
            return str(obj)

    def convert_length(self, length, from_unit, to_unit):
        """
        Convert length from `from_unit` to `to_unit`
        unit can be either unit of measure name or Odoo uom.uom record
        """
        try:
            return self._platform_convert_unit(length, from_unit, to_unit)
        except UomNotFoundError:
            return self._external_convert_length(length, from_unit, to_unit)

    @classmethod
    def _external_convert_length(cls, length, from_unit, to_unit):
        """
        Convert length from `from_unit` to `to_unit`
        unit must be either unit of measure name
        """
        from_unit, to_unit = cls._get_unit_from(from_unit), cls._get_unit_from(to_unit)
        convert = resource_formatter.LengthConversionTrans(from_unit=from_unit, to_unit=to_unit)
        return convert(length)
