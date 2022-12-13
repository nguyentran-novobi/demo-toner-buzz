# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from typing import Any

from ..common.exceptions import ModelNotFoundError


class ModelRegistry:
    _content: dict

    def __init__(self):
        self._content = dict()

    def __getitem__(self, model_name):
        """
        Get new instance of the model with model name
        See `get` for more information
        """
        return self.get(model_name)

    def __setitem__(self, model_name, model):
        """
        Put the model into the registry with the provided name
        See `register` for more information
        """
        self.register(model_name, model)

    def __delitem__(self, model_name):
        """
        Remove the specified model name from the registry
        See `remove_model` for more information
        """
        self.remove_model(model_name)

    def __contains__(self, model_name):
        """
        Whether the name is registered
        """
        return model_name in self._content

    def get(self, model_name):
        """
        Get new instance of the model with model name
        Raise error if not found
        """
        try:
            model = self._content[model_name]
        except KeyError as e:
            raise ModelNotFoundError(str(e)) from e
        return model()

    def register(self, model_name, model):
        """
        Put the model into the registry with the provided name
        """
        self._content[model_name] = model

    def remove_model(self, model_name):
        """
        Remove the specified model name from the registry
        """
        del self._content[model_name]


class ModelEnvironment:
    registry: ModelRegistry
    composite: Any

    def __init__(self, registry, composite):
        self.registry = registry
        self.composite = composite

    def __getitem__(self, item):
        model = self.registry[item]
        return self.composite.clone_nil(model)

    def attach_to(self, model):
        """
        Simply attach model with this environment
        """
        model.env = self


def register_platform_model(model_registry: ModelRegistry, platform: str, model_name: str):
    """
    Add the model class into the registry of the corresponding platform
    """
    platform_registry.setdefault(platform, model_registry)

    def decorate(cls):
        model_registry[model_name] = cls
        return cls
    return decorate


platform_registry = {}
