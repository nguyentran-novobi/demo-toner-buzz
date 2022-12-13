# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import contextlib

from unittest.mock import Mock, patch

from utils.restful.connection import RestfulRequest


@contextlib.contextmanager
def patch_request(
        json=None,
        headers=None,
        error=None,
        side_effect=None,
):
    if json is not None:
        with patch_request_ok(json=json, headers=headers) as mock_request:
            yield mock_request
    elif error is not None:
        with patch_request_error(error=error) as mock_request:
            yield mock_request
    elif side_effect is not None:
        with patch_request_side_effect(side_effect=side_effect, headers=headers) as mock_request:
            yield mock_request
    else:
        with patch_request_ok() as mock_request:
            yield mock_request


@contextlib.contextmanager
def patch_request_ok(json=None, headers=None):
    mock_response = Mock(ok=Mock(return_value=True))
    if json is not None:
        mock_response.json = Mock(return_value=json)
    if headers is not None:
        mock_response.headers = headers
    mock_request = Mock(return_value=mock_response)
    mock_engine = Mock(request=mock_request)
    with patch.object(RestfulRequest, 'carrier', mock_engine):
        yield mock_request


@contextlib.contextmanager
def patch_request_error(error):
    error_exception = RestfulRequest.engine_request_error
    mock_request = Mock(side_effect=error_exception(error))
    mock_engine = Mock(request=mock_request)
    with patch.object(RestfulRequest, 'carrier', mock_engine):
        yield mock_request


@contextlib.contextmanager
def patch_request_side_effect(side_effect=None, headers=None):
    mock_response = Mock(ok=Mock(return_value=True))
    mock_response.json = Mock(side_effect=side_effect)
    if headers is not None:
        mock_response.headers = headers
    mock_request = Mock(return_value=mock_response)
    mock_engine = Mock(request=mock_request)
    with patch.object(RestfulRequest, 'carrier', mock_engine):
        yield mock_request
