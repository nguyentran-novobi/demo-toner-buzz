# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytest

from unittest.mock import patch

from utils.common import ResourceData, ResourceComposite
from utils.common.registry import ModelRegistry
from utils.common.resource import delegated
from utils.common.resource_data import EmptyDataError
from utils.common.api import cache

from utils.restful import request_builder
from utils.restful.api import RestfulAPI
from utils.restful.connection import RestfulConnection

from test_utils.restful.common import patch_request


class SampleAPI(RestfulAPI):
    def update_credentials(self, credentials: dict):
        host, key = credentials['host'], credentials['key']
        self.connection = RestfulConnection(
            scheme='https://',
            hostname=f'{host}/',
            uri=f'sample_api/',
            headers={
                'Accept': 'application/json',
                'Access-Token': key,
            },
        )


model_registry = ModelRegistry()


@cache
def connect():
    credentials = dict(host='www.test.com', key='***secret***')
    return SampleAPI(credentials, model_registry)


class SimpleTestModel(
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
):
    path = 'test'
    postfix = '.json'
    primary_key = 'id'


model_registry['simple_test'] = SimpleTestModel

base_headers = {
    'Accept': 'application/json',
    'Access-Token': '***secret***',
}


def test_cache():
    with patch.object(SampleAPI, 'update_credentials') as mock_update:
        connect()
        connect()
    mock_update.assert_called_once()
    connect.cache_clear()


def test_simple_get_one():
    api = connect()
    expected = {'status': 'ok', 'msg': 'gotcha'}
    ack = api.simple_test.acknowledge(12742109321)

    with patch_request(json=expected) as mock_request:
        res = ack.get_by_id()

    mock_request.assert_called_once_with(
        'GET',
        'https://www.test.com/sample_api/test/12742109321.json',
        headers=base_headers
    )

    assert res.ok()
    assert res.data == expected


def test_simple_get_one_connection_error():
    api = connect()
    ack = api.simple_test.acknowledge(12742109321)
    error_message = 'This is a testing error'

    with patch_request(error=error_message) as mock_request:
        res = ack.get_by_id()

    mock_request.assert_called_once_with(
        'GET',
        'https://www.test.com/sample_api/test/12742109321.json',
        headers=base_headers
    )

    assert not res.ok()
    with pytest.raises(EmptyDataError):
        assert bool(res.data is None)
    assert res.get_error_message() == error_message
    assert res.get_status_code() is None


def test_simple_all():
    api = connect()
    expected = [{'product': 'ok', 'id': f'{seq}'} for seq in range(15)]

    with patch_request(json=expected) as mock_request:
        res = api.simple_test.all(created_at_min='2018-04-25T10:02:53+00:00')

    mock_request.assert_called_once_with(
        'GET',
        'https://www.test.com/sample_api/test.json',
        headers=base_headers,
        params={
            'created_at_min': '2018-04-25T10:02:53+00:00'
        }
    )

    assert res.ok()
    assert res.data == expected


def test_simple_publish():
    api = connect()
    expected = {'status': 'ok', 'msg': 'gotcha'}
    new = api.simple_test.create_new()
    new.data = expected

    with patch_request(json=expected) as mock_request:
        res = new.publish()

    mock_request.assert_called_once_with(
        'POST',
        'https://www.test.com/sample_api/test.json',
        headers=base_headers,
        json=expected,
    )

    assert res.ok()
    assert res.data == expected


def test_simple_put_one():
    api = connect()
    data = {'status': 'ok', 'msg': 'gotcha'}
    ack = api.simple_test.acknowledge(12742109321)
    ack.data = data
    expected = {**dict(id=12742109321), **data}

    with patch_request(json=expected) as mock_request:
        res = ack.put_one()

    mock_request.assert_called_once_with(
        'PUT',
        'https://www.test.com/sample_api/test/12742109321.json',
        headers=base_headers,
        json=expected,
    )

    assert res.ok()
    assert res.data == expected


def test_simple_delete_one():
    api = connect()
    ack = api.simple_test.acknowledge(12742109321)

    with patch_request(json=dict()) as mock_request:
        res = ack.delete_one()

    mock_request.assert_called_once_with(
        'DELETE',
        'https://www.test.com/sample_api/test/12742109321.json',
        headers=base_headers,
    )

    assert res.ok()
    with pytest.raises(EmptyDataError):
        assert bool(res.data is None)


def test_iterate_resource_nil():
    api = connect()
    res = [t for t in api.simple_test]
    assert len(res) == 0


def test_delegated():
    api = connect()
    expected_result = 21468921973
    expected_data = {'293812': 92163921}
    expected_response = {'845687': 6541687}

    class TempModel(SimpleTestModel):
        @delegated
        def assert_model_and_prop(self, prop=None):
            assert prop.data == expected_data
            assert isinstance(prop.resource, ResourceData)
            assert len(prop.resource) == 1
            assert prop.last_response == expected_response
            assert isinstance(prop.self, ResourceComposite)
            assert prop.self == temp
            assert self.env['simple_test']._model.__class__ == api.simple_test._model.__class__
            assert self.env['temp']._model.__class__ == api.temp._model.__class__
            return expected_result

    model_registry['temp'] = TempModel

    temp = api.get_composite_for(TempModel())
    temp = temp.create_new()
    temp.data = expected_data
    temp.last_response = expected_response
    result = temp.assert_model_and_prop()
    assert result == expected_result

    del model_registry['temp']
