# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import contextlib

from unittest.mock import patch

from utils.common.resource_formatter import NoneTrans
from utils.common.resource_formatter import ResourceFormatterMixin


class TransformerSuppressor(contextlib.ContextDecorator):
    TRANSFORMERS = [
        'transform_in_data',
        'transform_out_data',
        'transform_error_message',
        'transform_request_param',
    ]

    def __init__(self, resource_model=None):
        if resource_model:
            self.patchers = self._create_patchers_with_model(resource_model)
        else:
            self.patchers = self._create_patchers_without_model()

    def _create_patchers_with_model(self, resource_model):
        return [
            patch.object(resource_model, trans, NoneTrans())
            for trans in self.TRANSFORMERS
        ]

    def _create_patchers_without_model(self):
        to_be_patched_classes = set(self._get_class_tree_from(ResourceFormatterMixin))
        return [
            patch.object(patched_class, trans, NoneTrans())
            for trans in self.TRANSFORMERS
            for patched_class in to_be_patched_classes
        ]

    @classmethod
    def _get_class_tree_from(cls, model):
        yield model
        yield from cls._get_descendants_of(model)

    @classmethod
    def _get_descendants_of(cls, model):
        for subclass in model.__subclasses__():
            yield from cls._get_class_tree_from(subclass)

    def __enter__(self):
        for patcher in self.patchers:
            patcher.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patcher in self.patchers:
            patcher.stop()


not_transform_data = TransformerSuppressor
