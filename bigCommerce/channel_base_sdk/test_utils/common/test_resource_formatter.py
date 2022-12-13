# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest
import cmath

from utils.common import resource_formatter as common_formatter
from utils.common import fields


class ABasicDescriptorTrans(common_formatter.DescriptorTrans):
    option = fields.Retaining('option')
    data = fields.Retaining('data')
    keeper = fields.Retaining('finder')
    id = fields.Int2Str('id_on_channel')
    money = fields.Custom(compute=str, inverse=float)


@pytest.mark.parametrize('i,f,t,e', [
    (1, 'lb', 'lb', 1),
    (14, 'oz', 'lb', 0.875),
    (5, 'lb', 'kg', 2.267962),
    (0.7, 'lb', 'g', 317.5146),
])
def test_weight_convert(i, f, t, e):
    convert = common_formatter.WeightConversionTrans()
    convert.from_unit = f
    convert.to_unit = t
    assert cmath.isclose(convert(i), e, rel_tol=1e-5)


@pytest.mark.parametrize('i,f,t,e', [
    (1, 'in', 'in', 1),
    (459, 'cm', 'm', 4.59),
    (25, 'yd', 'mm', 22860),
    (24, 'km', 'mi', 14.9129086),
])
def test_weight_convert(i, f, t, e):
    convert = common_formatter.LengthConversionTrans()
    convert.from_unit = f
    convert.to_unit = t
    assert cmath.isclose(convert(i), e, rel_tol=1e-5)


@pytest.mark.parametrize('data,expected', [
    (dict(option=1, abc=2), dict(option=1)),
    (dict(option=1, data=dict(k=2, b=5)), dict(option=1, data=dict(k=2, b=5))),
    (dict(option=1, data=dict(k=2, b=5), keeper=65), dict(option=1, data=dict(k=2, b=5), finder=65)),
    (dict(option=1, id=2), dict(option=1, id_on_channel='2')),
    (dict(money=0.5), dict(money='0.5')),
])
def test_basic_trans_descriptor(data, expected):
    transform = ABasicDescriptorTrans()
    assert transform(data) == expected


@pytest.mark.parametrize('data,expected', [
    (dict(option=1, abc=2), dict(option=1)),
    (dict(option=1, data=dict(k=2, b=5)), dict(option=1, data=dict(k=2, b=5))),
    (dict(option=1, data=dict(k=2, b=5), finder=65), dict(option=1, data=dict(k=2, b=5), keeper=65)),
    (dict(option=1, id_on_channel='2'), dict(option=1, id=2)),
    (dict(money='0.5'), dict(money=0.5)),
])
def test_basic_trans_descriptor_inverse(data, expected):
    inverse_transform = ABasicDescriptorTrans.inverse
    assert inverse_transform(data) == expected


@pytest.mark.parametrize('data', [
    dict(),
    dict(option=1, abc=2),
    dict(option=1, data=dict(k=2, b=5), finder=65),
    dict(id=1, data=dict(k=2, money=0.5), finder=65),
])
def test_descriptor_trans_bidirectional(data):
    transform = ABasicDescriptorTrans()
    inverse_transform = ABasicDescriptorTrans.inverse
    double = inverse_transform.inverse

    result = inverse_transform(transform(data))
    adjusted = {k: v for k, v in data.items() if k in result}
    assert adjusted == result

    result = transform(inverse_transform(data))
    adjusted = {k: v for k, v in data.items() if k in result}
    assert adjusted == result

    result = double(inverse_transform(data))
    adjusted = {k: v for k, v in data.items() if k in result}
    assert adjusted == result

    trans1 = transform(data)
    trans2 = double(data)
    assert trans1 == trans2
