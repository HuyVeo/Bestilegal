"""Thread-safe singleton decorator for resource managers."""

import threading
from typing import TypeVar, Callable

T = TypeVar("T")

_instances: dict = {}
_locks: dict = {}
_global_lock = threading.Lock()


def singleton(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that turns a factory function into a thread-safe singleton.

    Usage::

        @singleton
        def get_db_pool() -> ConnectionPool:
            return ConnectionPool(...)

        pool = get_db_pool()  # created once, returned thereafter
    """
    key = func.__qualname__

    with _global_lock:
        _locks[key] = threading.Lock()

    def wrapper(*args, **kwargs) -> T:
        if key not in _instances:
            with _locks[key]:
                if key not in _instances:
                    _instances[key] = func(*args, **kwargs)
        return _instances[key]

    wrapper.__wrapped__ = func
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper._reset = lambda: _instances.pop(key, None)
    return wrapper
