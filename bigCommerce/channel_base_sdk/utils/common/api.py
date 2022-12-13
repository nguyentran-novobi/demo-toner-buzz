# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pickle

from functools import lru_cache, wraps

from .connection import Connection


class API:
    """
    This should be the first place a client looks for to navigate to other resources
    """
    connection: Connection


def cache(connecting_func):
    """
    Cache the connecting function.
    If the same credentials are provided, reuse the previous result API.
    """

    @lru_cache()
    def cached_func(serialized):
        args, kwargs = pickle.loads(serialized)
        return connecting_func(*args, **kwargs)

    @wraps(connecting_func)
    def wrapper(*args, **kwargs):
        serialized = pickle.dumps((args, kwargs))
        return cached_func(serialized)

    wrapper.cache_clear = cached_func.cache_clear
    return wrapper
