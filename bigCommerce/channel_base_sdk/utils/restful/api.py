# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common import ResourceComposite
from ..common.api import API
from ..common.registry import ModelRegistry

from ..restful.request_builder import RestfulResourceModel


class RestfulAPI(API):
    """
    API gateway
    """
    registry: ModelRegistry

    def __init__(self, credentials: dict, registry: ModelRegistry):
        """
        Initiate Restful API Gateway with the provided credentials
        """
        self.registry = registry
        self.update_credentials(credentials)

    def __getattr__(self, item):
        if self.is_model(item):
            return self.get_interface(item)
        return super().__getattribute__(item)

    def __getitem__(self, item):
        return getattr(self, item)

    def is_model(self, model_name):
        """
        Whether the model is registered
        """
        return model_name in self.registry

    def get_interface(self, model_name):
        """
        Get interface from model name
        """
        model = self.registry[model_name]
        return self.get_composite_for(model)

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """

    def get_composite_for(self, model: RestfulResourceModel):
        """
        Build Restful Resource Interface for the specify model
        """
        result = ResourceComposite.init_with(self.connection, model, self.registry)
        return result
