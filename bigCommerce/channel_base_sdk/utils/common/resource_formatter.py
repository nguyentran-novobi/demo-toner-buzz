# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytz
import datetime
import dateutil.parser

from typing import Any, Callable
from dataclasses import dataclass


class DataTrans:
    """
    An utility for transforming data into the desired format
    """

    def __call__(self, data):
        """
        Transform data
        """
        raise NotImplementedError


class SimpleFunctionDataTrans(DataTrans):
    """
    An utility for transforming data into the desired format using a simple function
    """
    _transform: Callable[[Any], Any]

    def __init__(self, rule):
        """
        Initiate Transformer with the provided rule
        """
        self._transform = rule

    def __call__(self, data):
        """
        Transform data with the simple function
        """
        return self._transform(data)


class NoneTrans(DataTrans):
    """
    Data will not be changed at all
    """

    def __call__(self, data):
        """
        Return the same provided data without changing anything
        """
        return data


class EmptyTrans(DataTrans):
    """
    Empty data
    """

    def __call__(self, data):
        """
        Ignore what store in data and return empty
        """
        return {}


@dataclass
class StrToDatetimeTrans(DataTrans):
    """
    Datetime in string will be changed to datetime object
    The default timezone will be UTC
    """
    timezone: Any = pytz.utc
    parser = dateutil.parser

    def __call__(self, value: str):
        """
        Datetime in string will be changed to datetime object
        """
        return self.parser.parse(value).astimezone(self.timezone).replace(tzinfo=None)


@dataclass
class PickedDictTrans(DataTrans):
    """
    Extract only needed keys from dict
    """
    kept_keys: list = None

    def __call__(self, data):
        """
        Copy only keys listed in the provided list
        """
        if self.kept_keys:
            return {k: v for k, v in data.items() if k in self.kept_keys}
        return data


@dataclass
class DatetimeToStrTrans(DataTrans):
    """
    Datetime object will be changed to datetime in string
    The default timezone will be UTC
    """
    timezone: Any = pytz.utc
    iso_format: bool = True
    format_str: str = '%Y-%m-%dT%H:%M:%S+00:00'

    def __call__(self, value: datetime.datetime):
        """
        Datetime in string will be changed to datetime object
        """
        if self.iso_format:
            return self.format_iso(value)
        else:
            return self.format_custom(value)

    def format_iso(self, value):
        """
        Convert datetime to ISO format
        """
        return value.replace(tzinfo=self.timezone).isoformat()

    def format_custom(self, value):
        """
        Convert datetime to custom format
        """
        return value.replace(tzinfo=self.timezone).strftime(self.format_str)


@dataclass
class DefaultFloatTrans(DataTrans):
    """
    Transform float or default value
    """
    default: float = 0.0

    def __call__(self, value):
        return self.to_float_or_default(value, self.default)

    @classmethod
    def to_float_or_default(cls, value, default=0.0):
        """
        Try converting value to float
        If not possible, return zero as default
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


@dataclass
class MonetaryStringTrans(DataTrans):
    """
    Transform float to monetary
    """
    symbol: str = '$'
    prefix: bool = True
    postfix: bool = False
    precious: int = 2

    def __call__(self, data):
        """
        Format monetary
        """
        amount_str = f'{data:0.{self.precious}f}'
        prefix_str = self.symbol if self.prefix else ''
        post_str = self.symbol if self.postfix else ''
        return f'{prefix_str}{amount_str}{post_str}'


class UnitConversionTrans(DataTrans):
    """
    Convert value from one unit to another unit
    """

    UNITS: dict
    SYSTEMS: dict
    SMALLEST: str

    from_unit: str
    to_unit: str

    def __call__(self, weight):
        """
        Convert value
        """
        return self.convert(weight, self.from_unit, self.to_unit)

    @classmethod
    def convert(cls, weight, from_unit, to_unit):
        """
        Convert value based on the params
        """
        if cls.is_in_the_same_system(from_unit, to_unit):
            return cls._convert_within_same_system(weight, from_unit, to_unit)
        return cls._convert_based_on_smallest(weight, from_unit, to_unit)

    @classmethod
    def is_in_the_same_system(cls, from_unit, to_unit):
        return cls.UNITS[from_unit] == cls.UNITS[to_unit]

    @classmethod
    def _convert_within_same_system(cls, weight, from_unit, to_unit):
        """
        Convert value between units in the same system
        """
        suffix = cls.SYSTEMS[cls.UNITS[cls.from_unit]]
        return cls._convert_using_suffix(weight, from_unit, to_unit, suffix=suffix)

    @classmethod
    def _convert_based_on_smallest(cls, weight, from_unit, to_unit):
        """
        Use the smallest supported units to convert
        """
        return cls._convert_using_suffix(weight, from_unit, to_unit, suffix=cls.SMALLEST)

    @classmethod
    def _convert_using_suffix(cls, weight, from_unit, to_unit, suffix):
        convert_to_method_name = f'convert_to_{suffix}'
        convert_from_method_name = f'convert_from_{suffix}'
        temp = getattr(cls, convert_to_method_name)(weight, from_unit)
        return getattr(cls, convert_from_method_name)(temp, to_unit)


@dataclass
class WeightConversionTrans(UnitConversionTrans):
    """
    Convert weight from one unit to another unit
    """

    UNITS = {
        't': 2,
        'kg': 2,
        'lb': 1,
        'oz': 1,
        'g': 2,
        'pounds': 1,
        'ounces': 1,
        'grams': 2,
        'pound': 1,
        'ounce': 1,
        'gram': 2
    }
    SYSTEMS = {
        1: 'ounce',
        2: 'gram',
    }
    TO_GRAM = {
        't': 1000000,
        'kg': 1000,
        'lb': 453.59237,
        'oz': 28.3495231,
        'g': 1,
        'pounds': 453.59237,
        'ounces': 28.3495231,
        'grams': 2,
        'pound': 453.59237,
        'ounce': 28.3495231,
        'gram': 2
    }
    TO_OUNCE = {
        't': 35273.96195,
        'kg': 35.27396195,
        'lb': 16,
        'oz': 1,
        'g': 0.03527396195,
    }
    SMALLEST = 'gram'

    from_unit: str = 'kg'
    to_unit: str = 'lb'

    @classmethod
    def convert_to_gram(cls, weight, unit):
        """
        Convert weight to gram
        """
        return weight * cls.TO_GRAM[unit]

    @classmethod
    def convert_from_gram(cls, weight, unit):
        """
        Convert weight from gram
        """
        return weight / cls.TO_GRAM[unit]

    @classmethod
    def convert_to_ounce(cls, weight, unit):
        """
        Convert weight to ounce
        """
        return weight * cls.TO_OUNCE[unit]

    @classmethod
    def convert_from_ounce(cls, weight, unit):
        """
        Convert weight from ounce
        """
        return weight / cls.TO_OUNCE[unit]


@dataclass
class LengthConversionTrans(UnitConversionTrans):
    """
    Convert length from one unit to another unit
    """

    UNITS = {
        'mi': 1,
        'km': 2,
        'm': 2,
        'yd': 1,
        'ft': 1,
        'in': 1,
        'cm': 2,
        'mm': 2,
    }
    SYSTEMS = {
        1: 'inch',
        2: 'millimeter',
    }
    TO_INCH = {
        'mi': 63360,
        'km': 39370.0787,
        'm': 39.3700787,
        'yd': 36,
        'ft': 12,
        'in': 1,
        'cm': 0.393700787,
        'mm': 0.0393700787,
    }
    TO_MILLIMETER = {
        'mi': 1609344,
        'km': 1000000,
        'm': 1000,
        'yd': 914.4,
        'ft': 304.8,
        'in': 25.4,
        'cm': 10,
        'mm': 1,
    }
    SMALLEST = 'millimeter'

    from_unit: str = 'm'
    to_unit: str = 'ft'

    @classmethod
    def convert_to_inch(cls, length, unit):
        """
        Convert length to inch
        """
        return length * cls.TO_INCH[unit]

    @classmethod
    def convert_from_inch(cls, length, unit):
        """
        Convert length from inch
        """
        return length / cls.TO_INCH[unit]

    @classmethod
    def convert_to_millimeter(cls, length, unit):
        """
        Convert length to millimeter
        """
        return length * cls.TO_MILLIMETER[unit]

    @classmethod
    def convert_from_millimeter(cls, length, unit):
        """
        Convert length from millimeter
        """
        return length / cls.TO_MILLIMETER[unit]


class FieldTrans(DataTrans):
    """
    A descriptor to transform a single field
    """

    name: str
    res_name: str

    def __init__(self, other_name=None):
        self.res_name = other_name

    def __call__(self, data):
        raise NotImplementedError

    def __set_name__(self, owner, name):
        self.name = name
        self.res_name = self.res_name or name

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        instance.__dict__[self.res_name] = self(value)

    def inverse(self):
        raise NotImplementedError

    def get_inverse_tuple(self):
        return self.res_name, self.inverse()


class InverseDescriptorTransBuilder:
    """
    A descriptor to generate the inverse trans of the descriptor trans
    """

    def __get__(self, instance, owner):
        inverse_attr = dict(
            att.get_inverse_tuple()
            for att_name, att in owner.__dict__.items()
            if isinstance(att, FieldTrans)
        )
        inverse_class = type('InverseDescriptorTrans', (owner,), inverse_attr)
        return inverse_class()


class DescriptorTrans(DataTrans):
    """
    Convert data based on the descriptors defined
    """

    inverse = InverseDescriptorTransBuilder()

    def __call__(self, data):
        """
        Transfer only keys that defined as descriptors
        Any keys that is not mentioned will simply be ignored
        """
        copy = self.copy()
        for k, v in data.items():
            if self.has_attr(k):
                setattr(copy, k, v)
        return copy.values

    @classmethod
    def copy(cls):
        return cls()

    @classmethod
    def has_attr(cls, name):
        return name in cls.__dict__

    @property
    def values(self):
        return self.__dict__


class ResourceFormatterMixin:
    """
    Mixin for resource that needs data transformation
    """

    transform_in_data: DataTrans = NoneTrans()
    transform_out_data: DataTrans = NoneTrans()
    transform_error_message: DataTrans = NoneTrans()
    transform_request_param: DataTrans = NoneTrans()
