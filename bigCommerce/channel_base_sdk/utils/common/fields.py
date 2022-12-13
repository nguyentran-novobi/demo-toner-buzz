# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from typing import Callable

from .resource_formatter import FieldTrans, NoneTrans


class Custom(FieldTrans):
    _compute: Callable
    _inverse: Callable

    def __init__(self, other_name=None, *, compute: Callable, inverse: Callable):
        super().__init__(other_name)
        self._compute = compute
        self._inverse = inverse

    def __repr__(self):
        return f'{self.__class__.__name__}(' \
               f'compute={self._compute},' \
               f'inverse={self._inverse})'

    def __call__(self, data):
        return self._compute(data)

    def inverse(self):
        return Custom(self.name, compute=self._inverse, inverse=self._compute)


class PredefinedCustom(Custom):
    def __init__(self, other_name=None):
        super().__init__(other_name, compute=self._compute, inverse=self._inverse)


class Retaining(PredefinedCustom):
    _compute = NoneTrans()
    _inverse = NoneTrans()


class Str2Int(PredefinedCustom):
    _compute = int
    _inverse = str


class Int2Str(PredefinedCustom):
    _compute = str
    _inverse = int
