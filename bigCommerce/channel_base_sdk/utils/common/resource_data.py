# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import copy
import functools

from typing import Any, Callable, Iterable, List, Optional, Union
from dataclasses import dataclass

from .registry import ModelRegistry, ModelEnvironment
from .resource import DELEGATED_MARKER, ResourceComposite as BaseResourceComposite, \
    ResourceData as BaseResourceData, ResourceModel
from .exceptions import EmptyDataError, KeyNotFoundError, UnsupportedOperationError


NO_DATA = object()


@dataclass
class PropagatedParam:
    __slots__ = (
        'connection',
        'options',
        'data',
        'resource',
        'self',
        'last_response',
        'extra_content',
    )

    connection: Any
    options: Any
    data: Union[list, dict]
    resource: 'ResourceData'
    self: 'ResourceCompositeData'
    last_response: Any
    extra_content: Optional[dict]

    def __getitem__(self, item):
        return getattr(self, item)

    def __contains__(self, item):
        return hasattr(self, item)

    @classmethod
    def init_from(cls, composite: 'ResourceCompositeData'):
        """
        Process attribute of the requested attributes of the propagated function
        and extract value from composite to pass the corresponding values
        """
        result = PropagatedParam(
            connection=composite.connection,
            options=cls.get_options_from(composite),
            data=cls.get_data_from(composite),
            resource=composite.resource,
            self=composite,
            last_response=composite.last_response,
            extra_content=composite.extra_content,
        )
        return result

    @classmethod
    def get_options_from(cls, composite: 'ResourceCompositeData'):
        resource = composite.resource
        options = {}
        if isinstance(resource, ResourceSingular):
            options.update(resource.keys)
        if isinstance(resource, ResourceIrregular):
            options.update(resource.meta)
        return options

    @classmethod
    def get_data_from(cls, composite: 'ResourceCompositeData'):
        try:
            return composite.resource.data
        except EmptyDataError:
            return None


class DelegatedReturn:
    __slots__ = (
        'model',
        'data',
        'resource',
        'response',
        'extra',
        'nil',
        'error',
    )

    model: str
    data: Union[list, dict]
    resource: Any
    response: Any
    extra: Any
    nil: bool
    error: bool

    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        """
        Update the attribute of this result
        """
        template = {
            'model': None,
            'data': None,
            'resource': None,
            'response': None,
            'extra': None,
            'nil': False,
            'error': False,
        }
        values = {**template, **kwargs}
        for k, v in values.items():
            setattr(self, k, v)

    def get_delegated_result_from(self, composite: 'ResourceCompositeData', registry: ModelRegistry):
        """
        Process the result of the propagated
        """
        model = self.get_model(registry)
        result = self.get_returned_composite(composite, model)
        assert result is not None
        return self.assign_values_to_returned_composite(result)

    def get_model(self, registry) -> 'ResourceModel':
        """
        Get the instance of the model from the registry
        """
        return registry[self.model] if self.model else None

    def get_returned_composite(self, composite: 'ResourceCompositeData', model: 'ResourceModel')\
            -> 'ResourceCompositeData':
        """
        Based on the requested data type, clone a composite with the specified model
        """
        result = None
        if self.data is not None:
            result = composite.clone_with(ResourceData.from_data(self.data), model)
        elif self.resource is not None:
            result = composite.clone_with(self.resource, model)
        elif self.nil:
            result = composite.clone_nil(model)
        elif self.error:
            result = composite.clone_nil(model)
        return result

    def assign_values_to_returned_composite(self, result: 'ResourceCompositeData') -> 'ResourceCompositeData':
        """
        Finalize the result before returning to the caller
        """
        if self.extra:
            result._extra_content = self.extra
        if self.response:
            result.last_response = self.response
        return result


class ResourceData(BaseResourceData):
    """
    A new base class for resource Data
    """

    def __iter__(self):
        yield from []

    def __len__(self):
        raise NotImplementedError

    def __add__(self, other: 'ResourceData') -> 'ResourceData':
        return ResourceCollection.build_from(self, other)

    @property
    def data(self):
        raise NotImplementedError

    @data.setter
    def data(self, value):
        raise NotImplementedError

    @classmethod
    def from_data(cls, data) -> 'ResourceData':
        """
        Build ResourceData from data
        """
        if isinstance(data, list):
            return cls._from_collection(data)
        return cls._from_data(data)

    @classmethod
    def _from_data(cls, data: dict) -> 'ResourceSingular':
        """
        Build ResourceSingular from data
        """
        res = ResourceSingular(data)
        return res

    @classmethod
    def _from_collection(cls, collection: list) -> Union['ResourceNil', 'ResourceSingular', 'ResourceCollection']:
        """
        Build ResourceCollection from data
        """
        if len(collection) == 0:
            res = ResourceNil()
        else:
            if len(collection) == 1:
                res = ResourceSingular(collection[0])
            else:
                res = ResourceCollection(collection)
        return res

    def filter(self, pre: Callable) -> Iterable['ResourceData']:
        """
        Filter and return resources based on the predicate
        """
        raise NotImplementedError

    def filter_field(self, **kwargs) -> Iterable['ResourceData']:
        """
        Filter and return resources based on the provided fields and values
        """
        raise NotImplementedError

    def map(self, func: Callable) -> Iterable:
        """
        Apply the function on each of the data and return the result of each
        """
        raise NotImplementedError

    def map_path(self, path: str) -> Iterable:
        """
        Get data of the data based on the path
        path should be a list of fields separated by dots (.)
        """
        raise NotImplementedError


class ResourceNil(ResourceData):
    """
    This resource does not exist
    """

    def __len__(self):
        return 0

    @property
    def data(self) -> Union[list, dict]:
        """
        Raise error as this resource does not contain data
        """
        raise EmptyDataError('This resource does not contain data')

    @data.setter
    def data(self, value):
        """
        Raise error as this resource cannot hold data
        """
        raise EmptyDataError('This resource cannot hold data')

    def filter(self, pre):
        yield from []

    def filter_field(self, **kwargs):
        yield from []

    def map(self, func):
        yield from []

    def map_path(self, path):
        yield from []


class ResourceSingular(ResourceData):
    """
    This is a single resource
    """
    _data: dict
    _key_names: tuple
    _keys: dict

    def __init__(self, data=None):
        """
        Initiate resource with the provided data
        If no data provided, empty will be assigned
        """
        self._key_names = ()
        self._keys = {}
        self.data = data or {}

    def __iter__(self):
        yield self

    def __len__(self):
        return 1

    @property
    def data(self) -> Union[list, dict]:
        """
        Return the formatted data this resource holds
        """
        return self._data

    @data.setter
    def data(self, value):
        """
        Replace resource data with the new data
        """
        value = value or {}
        self.acknowledge_if_key_exists(value)
        self._data = value
        self.assign_if_key_acknowledged()

    @property
    def key(self):
        """
        Return the key/keys if acknowledged
        """
        if self.key_acknowledged:
            if len(self._key_names) == 1:
                return self._keys[self._key_names[0]]
            else:
                return self._keys
        raise KeyNotFoundError()

    @property
    def keys(self):
        """
        Return the keys
        """
        return self._keys

    @property
    def key_acknowledged(self):
        """
        Whether keys are acknowledged
        """
        return (
            set(self._key_names) == set(self._keys.keys())
            and all(filter(lambda k: k is not None, self._keys.values()))
        )

    def update(self, value):
        """
        Update resource data
        """
        self.acknowledge_if_key_exists(value)
        self._data.update(value)

    def self_acknowledge(self):
        """
        Force data to acknowledge keys of the current data
        """
        self.acknowledge_if_key_exists(self._data)

    def acknowledge_if_key_exists(self, value):
        """
        Check whether key provided and acknowledge this key
        """
        for key_name in self._key_names:
            if key_name in value:
                self.acknowledge(key_name, value[key_name])

    def acknowledge(self, key_name, key):
        """
        Acknowledge primary key of the resource
        """
        self.acknowledge_key(key_name)
        self._keys[key_name] = key

    def acknowledge_key(self, key_name):
        """
        Acknowledge only key name of the resource
        """
        if key_name is not None and key_name not in self._key_names:
            self._key_names += (key_name,)

    def assign_if_key_acknowledged(self):
        """
        Make sure source data has key if key has already been acknowledged
        """
        if self.key_acknowledged:
            for key, value in self._keys.items():
                self._data.setdefault(key, value)

    def filter(self, pre):
        if pre(self._data):
            yield from self
        else:
            yield from []

    def filter_field(self, **kwargs):
        def eq(data, cri):
            return {k: v for k, v in data.items() if k in cri} == cri

        if eq(self._data, kwargs):
            yield from self
        else:
            yield from []

    def map(self, func):
        yield func(self._data)

    def map_path(self, path):
        yield from self._map_path(self._data, path)

    @classmethod
    def _map_path(cls, data, path):
        if path == '':
            yield data
        else:
            if isinstance(data, dict):
                yield from cls._map_path_dict(data, path)
            elif isinstance(data, list):
                yield from cls._map_path_list(data, path)

    @classmethod
    def _map_path_dict(cls, data: dict, path: str):
        field, *tail = path.split('.')
        if field in data:
            yield from cls._map_path(data[field], '.'.join(tail))

    @classmethod
    def _map_path_list(cls, data: list, path: str):
        for item in data:
            yield from cls._map_path(item, path)


class ResourceCollection(ResourceData):
    """
    This contains many resources (2 or more) in it
    """

    children: List[ResourceSingular]

    def __init__(self, collection=None):
        """
        Initiate resource with the provided data
        If not enough data is provided, error will raise
        """
        assert len(collection) > 1
        self.children = [ResourceSingular(item) for item in collection]

    def __iter__(self):
        yield from self.children

    def __len__(self):
        return len(self.children)

    @property
    def data(self) -> Union[list, dict]:
        """
        Return the formatted data this resource holds
        """
        return [child.data for child in self.children]

    @data.setter
    def data(self, value):
        """
        Raise error as this data should be assigned individually
        """
        raise UnsupportedOperationError('Data should be assigned individually')

    @classmethod
    def build_from(cls, *items):
        """
        Init and build a new collection from list of resource data
        """
        children = []
        for item in items:
            assert isinstance(item, ResourceData)
            children.extend(item)
        if len(children) > 1:
            return cls(list(map(lambda x: x.data, children)))
        elif len(children) == 1:
            return children[0]
        else:
            return ResourceNil()

    def filter(self, pre):
        for child in self.children:
            yield from child.filter(pre)

    def filter_field(self, **kwargs):
        for child in self.children:
            yield from child.filter_field(**kwargs)

    def map(self, func):
        for child in self.children:
            yield from child.map(func)

    def map_path(self, path):
        for child in self.children:
            yield from child.map_path(path)


class ResourceDeferral(ResourceData):
    """
    This resource may not be available or not fully available
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

    def filter(self, pre):
        raise NotImplementedError

    def filter_field(self, **kwargs):
        raise NotImplementedError

    def map(self, func):
        raise NotImplementedError

    def map_path(self, path):
        raise NotImplementedError


class ResourceIrregular(ResourceData):
    """
    This kind of resource can hold any kind of data
    Data can be a singular or a collection or nothing at all
    """
    _data: Any
    _meta: dict

    def __init__(self, data=NO_DATA, meta=None):
        self._data = data
        self._meta = meta or {}

    def __iter__(self):
        yield self

    def __len__(self):
        return 1

    @property
    def data(self):
        """
        Return the data this resource holds
        """
        return self._data

    @data.setter
    def data(self, value):
        """
        Replace resource data with the new data
        """
        self._data = value

    @property
    def meta(self):
        """
        Return metadata
        """
        return self._meta

    @meta.setter
    def meta(self, value):
        """
        Replace metadata
        """
        self._meta = value

    def filter(self, pre):
        if pre(self._data):
            yield from self
        else:
            yield from []

    def filter_field(self, **kwargs):
        raise AttributeError('Not supported')

    def map(self, func):
        yield func(self._data)

    def map_path(self, path):
        raise AttributeError('Not supported')


class ResourceCompositeData(BaseResourceComposite):
    _extra_content: Optional[dict] = None
    _registry: Any

    def __bool__(self):
        return not isinstance(self._data, ResourceNil)

    def __len__(self):
        return len(self._data)

    def __add__(self, other):
        assert isinstance(other, ResourceCompositeData)

        data = ResourceCollection.build_from(self._data, other._data)
        return self.clone_with(data)

    @property
    def data(self) -> Union[list, dict]:
        """
        Return the formatted data this resource holds
        """
        return copy.deepcopy(self._data.data)

    @data.setter
    def data(self, value):
        """
        Replace resource data with the new data
        """
        self._data.data = value

    @property
    def resource(self):
        return self._data

    @property
    def extra_content(self):
        return self._extra_content

    @classmethod
    def init_with(cls, connection, model, model_registry):
        """
        Initiate composite with the provided info
        """
        result = cls()
        result.connection = connection
        result._model = model
        result._data = ResourceNil()
        result._registry = model_registry
        return result

    def create_collection_with(self, values):
        """
        Clone and assign all values into a new collection
        """
        return sum((self.create_new_with(value) for value in values), self.clone_nil())

    def create_new_with(self, value):
        """
        Clone an empty composite from this and assign value
        """
        result = self.create_new()
        result.data = value
        return result

    def create_new(self):
        """
        Clone an empty composite from this
        """
        return self.clone_with(ResourceSingular())

    def acknowledge(self, key, **secondary):
        """
        Clone an interface that assigned with the provided keys
        """
        primary_key = getattr(self._model, 'primary_key', 'id')
        secondary_keys = getattr(self._model, 'secondary_keys', ())
        data = {}
        if key:
            data[primary_key] = key
        data.update(**{
            s_key: s_value
            for s_key, s_value in secondary.items()
            if s_key in secondary_keys
        })

        res_data = ResourceSingular()
        for k, v in data.items():
            res_data.acknowledge(k, v)
        resource_interface = self.clone_with(res_data)
        return resource_interface

    def recognize(self, **meta):
        """
        Clone an interface that assigned with the provided meta data
        """
        primary_key = getattr(self._model, 'primary_key', 'id')
        secondary_keys = getattr(self._model, 'secondary_keys', ())
        keys = (primary_key,) + secondary_keys
        meta = {k: v for k, v in meta.items() if k in keys}
        res_data = ResourceIrregular(meta=meta)
        resource_interface = self.clone_with(res_data)
        return resource_interface

    def clone_nil(self, model: ResourceModel = None):
        """
        Clone an composite with the nil data
        """
        return self.clone_with(ResourceNil(), model)

    def clone_with(self, data: ResourceData, model: ResourceModel = None):
        """
        Clone an composite with the provided data
        """
        res = self.__class__()
        res.connection = self.connection
        if model is not None:
            res._model = model
        else:
            res._model = self._model
        res._data = data
        if isinstance(res._data, ResourceSingular):
            self._acknowledge_keys(res._data, res._model)
        if isinstance(res._data, ResourceCollection):
            for singular in res._data:
                self._acknowledge_keys(singular, res._model)
        res._registry = self._registry
        return res

    @classmethod
    def _acknowledge_keys(cls, data: ResourceSingular, model: ResourceModel):
        """
        Assign key name of the model to data
        """
        primary_key = getattr(model, 'primary_key', 'id')
        secondary_keys = getattr(model, 'secondary_keys', ())
        key_names = (primary_key,) + secondary_keys
        for key_name in key_names:
            data.acknowledge_key(key_name)
            data.self_acknowledge()

    def _attach_model_environment(self):
        """
        Renew environment which will attach to the model
        """
        env = ModelEnvironment(self._registry, self)
        env.attach_to(self._model)

    def _process_delegated(self, func):
        """
        Dynamic decorate this attribute
        """
        passing_data = self._generate_propagating_value(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raw_result = func(*args, **passing_data, **kwargs)
            if not self.is_raw_return(raw_result):
                return self._process_result_propagated(raw_result)
            return raw_result

        return wrapper

    def _generate_propagating_value(self, func):
        """
        Extract requests from the function and return the according requested value
        """
        propagated_to = getattr(func, DELEGATED_MARKER)
        prop = PropagatedParam.init_from(self)
        return {
            propagated_to: prop
        }

    @classmethod
    def is_raw_return(cls, result):
        """
        Whether the result of the propagated does not need any processing
        """
        return not isinstance(result, DelegatedReturn)

    def _process_result_propagated(self, result: DelegatedReturn):
        """
        Process the result of the propagated before passing to the caller
        """
        return result.get_delegated_result_from(self, self._registry)


class ResourceCompositeIterable(ResourceCompositeData):
    _data: ResourceData

    def __iter__(self):
        """
        Check iteration variable for looping through resources
        """
        yield from map(self.clone_iter_with, self._data)

    def clone_iter_with(self, data: ResourceData, model: ResourceModel = None):
        res = self.clone_with(data, model)
        res.last_response = self.last_response
        return res

    def iter(self):
        """
        Iterate from the resources, return data each iteration
        """
        yield from map(lambda res: res.data, self)

    def filter(self, pre: Callable) -> Iterable['ResourceCompositeIterable']:
        """
        Filter and return resources based on the predicate
        """
        yield from map(self.clone_iter_with, self._data.filter(pre))

    def filter_field(self, **kwargs) -> Iterable['ResourceCompositeIterable']:
        """
        Filter and return resources based on the fields and values
        """
        yield from map(self.clone_iter_with, self._data.filter_field(**kwargs))

    def map(self, func: Callable) -> Iterable:
        """
        Apply the function on each of the resource and get the result
        """
        yield from self._data.map(func)

    def map_path(self, path: str) -> Iterable:
        """
        Use the provided path to get the resource data of each resource
        """
        yield from self._data.map_path(path)


ResourceComposite = ResourceCompositeIterable
