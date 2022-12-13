# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.


class EmptyDataError(Exception):
    pass


class KeyNotFoundError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class UnsupportedOperationError(Exception):
    pass


class NotParseableException(ValueError):
    """
    Error raised when the content cannot be parsed
    """


class UnexpectedPropagatedError(Exception):
    """
    Attribute error raised when propagating
    """


class MissingRequiredKey(KeyError):
    """
    Indicates that the provided dict does not have the mandatory key
    """


class NoResponseError(Exception):
    """
    Error raised when trying to interact with non-existing response
    """
