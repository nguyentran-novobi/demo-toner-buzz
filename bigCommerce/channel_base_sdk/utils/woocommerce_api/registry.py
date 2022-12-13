# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import functools

from ..common.registry import ModelRegistry, register_platform_model

from .const import PLATFORM


model_registry = ModelRegistry()
register_model = functools.partial(register_platform_model, model_registry, PLATFORM)


def bulk_register_models(bulk_data: dict):
    """
    Make it simpler to create models which do not contain any more than basic methods
    """
    for model_name, (model_classes, attributes) in bulk_data.items():
        model_class_name = f'{PLATFORM.title()}{model_name.title()}Model'
        result = type(model_class_name, tuple(model_classes), dict(attributes))
        register_model(model_name)(result)
