# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from typing import Iterable, Union

from .registry import ModelEnvironment
from .connection import Connection, Response, NonExistResponse
from .exceptions import UnexpectedPropagatedError


DELEGATED_MARKER = 'delegated'


def delegated(*args, set_to='prop', **kwargs):
    """
    Request options from the handler to pass to the function
    :param set_to: the parameter name that the handler will pass to
    :param kwargs: options to ask from the handler
    """
    def is_simple_call():
        return args and len(args) == 1 and len(kwargs) == 0 and callable(args[0])

    def delegated_decorator(func):
        """
        Simply set attributes to the function
        """
        setattr(func, DELEGATED_MARKER, set_to)
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func

    if is_simple_call():
        return delegated_decorator(args[0])
    return delegated_decorator


class Resource:
    """
    Base class for all resource classes to inherit
    """


class ResourceData(Resource):
    """
    Simply an abstract class which holds data
    This class should just hold data and other data manipulating methods
    """

    def __len__(self):
        raise NotImplementedError

    @property
    def data(self):
        """
        Return the formatted data this resource holds
        """
        raise NotImplementedError

    @data.setter
    def data(self, value):
        """
        Replace resource data with the new data
        """
        raise NotImplementedError

    def replace_with(self, data):
        """
        Overwrite data with the new data
        """

    def update(self, data):
        """
        Update data by appending new data
        """

    def items(self) -> Iterable[Union[list, dict]]:
        """
        Return an iterable of the contained data
        """

    @classmethod
    def from_data(cls, data) -> 'ResourceData':
        """
        Build ResourceData from data
        """

    @classmethod
    def from_iter(cls, iterable) -> 'ResourceData':
        """
        Build ResourceData from iterable
        """


class ResourceModel(Resource):
    """
    This class contains all needed method to apply and request on resource
    """
    env: ModelEnvironment
    primary_key: str
    secondary_keys: tuple


class ResourceComposite(Resource):
    """
    The client will hold this instance of this class for requesting data
    This class will propagate method calls to the appropriate component
    """
    connection: Connection
    last_response: Response = NonExistResponse()
    _model: ResourceModel
    _data: ResourceData

    def __getattr__(self, name):
        """
        Propagate method call to specific resources
        """
        return self._propagate(name)

    def _propagate(self, name):
        """
        Propagate method call to specific resources
        """
        for prop in self._propagation_resources:
            try:
                res = getattr(prop, name)
            except AttributeError:
                pass
            else:
                return self._propagate_to_attr(res)
        return super().__getattribute__(name)

    @property
    def _propagation_resources(self) -> Iterable[Resource]:
        """
        Return resources to which will be used to propagate methods
        """
        return self._data, self._model

    def _propagate_to_attr(self, attr):
        """
        Handle and process delegated attribute
        """
        try:
            res = self._process_if_delegated(attr)
            return res
        except AttributeError as e:
            raise UnexpectedPropagatedError(str(e)) from e

    def _process_if_delegated(self, attr):
        """
        Check whether the attribute is delegated
        Dynamic decorate this attribute
        """
        if self._is_delegated(attr):
            self._attach_model_environment()
            return self._process_delegated(attr)
        return attr

    @classmethod
    def _is_delegated(cls, attr) -> bool:
        """
        Check whether the attribute is delegated
        """
        return callable(attr) and hasattr(attr, DELEGATED_MARKER)

    def _attach_model_environment(self):
        raise NotImplementedError

    def _process_delegated(self, func):
        raise NotImplementedError

    def ok(self):
        """
        Ask whether the last response is a success
        If there is no response, always return True
        """
        if self.last_response:
            return self.last_response.ok()
        return True
