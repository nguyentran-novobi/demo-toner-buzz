# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from typing import Iterable, Union

from .exceptions import EmptyDataError, NoResponseError


class Connection:
    """
    Contain information needed to establish an connection to channel
    """


class Request:
    """
    This contains information for sending a single request to channel
    """

    def send(self) -> 'Response':
        """
        Send the request and receive the response
        """


class Response:
    """
    This contains information related to the response received from the request
    """
    request: Request

    def __bool__(self):
        """
        Whether this is a response or not
        """
        return True

    def ok(self) -> bool:
        """
        Whether the request is sent successfully and the response is received with green status
        """

    def json(self) -> Union[list, dict]:
        """
        Extract data from response and parse it to the JSON-like format
        This may raise Exception if the response is not in expected format
        """

    def iter(self) -> Iterable[Union[list, dict]]:
        """
        Extract data from response and parse it to the JSON-like format one by one
        This may raise Exception if the response is not in expected format
        """


class NonExistResponse(Response):
    """
    This response has not yet existed
    Used as a default when request is not yet sent
    """

    def __bool__(self):
        """
        As a non-existing response, this is definitely not a response
        """
        return False

    def ok(self) -> bool:
        return False

    def json(self):
        raise EmptyDataError(f"{type(self).__name__} doesn't have any data")

    def raise_for_status(self):
        """
        Raise error if the request is not successful
        """
        raise NoResponseError('This response does not exist!')
