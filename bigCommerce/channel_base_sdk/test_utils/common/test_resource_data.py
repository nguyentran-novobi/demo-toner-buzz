# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from utils.common import ResourceComposite


composite = ResourceComposite.init_with(connection=None, model=None, model_registry=None)


@pytest.mark.parametrize('values', [
    [],
    [dict(id=2)],
    [dict(title='abc')],
    [dict(id=2), dict(id=4), dict(id=7)],
    [dict(title='abc'), dict(name='abc'), dict(desc='abc')],
])
def test_resource_iter(values):
    temp = composite.create_collection_with(values)
    result = temp.iter()
    assert values != result
    assert values == list(result)


@pytest.mark.parametrize('values,pre,expected', [
    ([], lambda x: x.get('id') == 1, 0),
    ([dict(id=2)], lambda x: x['id'] == 2, 1),
    ([dict(title='abc')], lambda x: x.get('name') == 'abc', 0),
    ([dict(id=2), dict(id=4), dict(id=7)], lambda x: x['id'] == 2, 1),
    ([dict(title='abc'), dict(name='abc'), dict(desc='abc')], lambda x: x.get('name') == 'abc', 1),
])
def test_resource_filter_collection(values, pre, expected):
    temp = composite.create_collection_with(values)
    count = len(list(temp.filter(pre)))
    assert count == expected


@pytest.mark.parametrize('values,fields,expected', [
    ([], dict(id=4), 0),
    ([dict(id=2)], dict(id=2), 1),
    ([dict(id=2), dict(abc='33'), dict(id=7)], dict(id=5), 0),
    ([dict(id=5), dict(xyz=''), dict(id=5, xyz='go')], dict(id=5), 2),
    ([dict(id=5, xyz=''), dict(xyz=''), dict(id=5, xyz='go')], dict(id=5, xyz='go'), 1),
])
def test_resource_filter_field(values, fields, expected):
    temp = composite.create_collection_with(values)
    count = len(list(temp.filter_field(**fields)))
    assert count == expected


@pytest.mark.parametrize('values,func,expected', [
    ([], lambda x: x.get('id'), []),
    ([dict(id=2)], lambda x: x.get('id'), [2]),
    ([dict(id=2), dict(abc='33'), dict(id=7)], lambda x: x.get('id'), [2, None, 7]),
])
def test_resource_map(values, func, expected):
    temp = composite.create_collection_with(values)
    result = temp.map(func)
    assert result != expected
    assert list(result) == expected


@pytest.mark.parametrize('values,path,expected', [
    ([], '', []),
    ([dict(id=2)], '', [dict(id=2)]),
    ([dict(id=2), dict(id=4), dict(id=7)], '', [dict(id=2), dict(id=4), dict(id=7)]),
    ([dict(id=2)], 'id', [2]),
    ([dict(id=2), dict(id=4), dict(id=7)], 'id', [2, 4, 7]),
    ([dict(id=2), dict(abc='33'), dict(id=7)], 'id', [2, 7]),
    ([dict(var=dict(id=3)), dict(var=dict(id=4)), dict(id=7)], 'var.id', [3, 4]),
    (
        [
            dict(var=[dict(id=3), dict(id=9)]),
            dict(var=dict(id=4)),
            dict(id=7, var=[dict(id=7), dict(id=1), dict(msg='abc')]),
        ],
        'var',
        [[dict(id=3), dict(id=9)], dict(id=4), [dict(id=7), dict(id=1), dict(msg='abc')]]
    ),
    (
        [
            dict(var=[dict(id=3), dict(id=9)]),
            dict(var=dict(id=4)),
            dict(id=7, var=[dict(id=7), dict(id=1), dict(msg='abc')]),
        ],
        'var.id',
        [3, 9, 4, 7, 1]
    ),
    (
        [
            dict(prod=dict(var=[dict(msg=dict(code='a')), dict(msg=dict(code='b'))])),
            dict(prod=dict()),
            dict(prod=dict(var=[])),
            dict(prod=dict(var=[dict(), dict(), dict(msg=dict()), dict(msg=dict(code='c')), dict(msg=dict())])),
        ],
        'prod.var.msg.code',
        ['a', 'b', 'c']
    )
])
def test_resource_map_path(values, path, expected):
    temp = composite.create_collection_with(values)
    result = temp.map_path(path)
    assert result != expected
    assert list(result) == expected
