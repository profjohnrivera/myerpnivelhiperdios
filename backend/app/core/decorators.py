# backend/app/core/decorators.py
import functools
import asyncio
from typing import Callable, Any
from app.core.transaction import transaction as tx_manager


def action(label: str, icon: str = "zap", variant: str = "primary", confirm: str = None):
    def decorator(func: Callable) -> Callable:
        func._is_action = True
        func._action_meta = {
            "name": func.__name__,
            "label": label,
            "icon": icon,
            "variant": variant,
            "confirm_message": confirm,
        }

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper._is_action = True
        wrapper._action_meta = func._action_meta
        return wrapper

    return decorator


def transaction(func: Callable) -> Callable:
    """
    FIX P1-C: @transaction solo acepta coroutines.
    tx_manager() maneja el token del ContextVar correctamente
    (set antes del yield, reset en finally).
    El anidamiento usa savepoints automáticamente.
    """
    if not asyncio.iscoroutinefunction(func):
        raise TypeError(
            f"@transaction solo puede decorar coroutines (async def). "
            f"'{func.__name__}' es una función síncrona."
        )

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with tx_manager():
            return await func(*args, **kwargs)

    wrapper._is_action = getattr(func, "_is_action", False)
    wrapper._action_meta = getattr(func, "_action_meta", None)
    return wrapper


def depends(*fields: str):
    def decorator(func: Callable) -> Callable:
        func._is_compute = True
        func._depends_on = fields
        return func
    return decorator


def constrains(*fields: str):
    def decorator(func: Callable) -> Callable:
        func._is_constrain = True
        func._constrain_fields = fields
        return func
    return decorator


def is_ui_action(func: Any) -> bool:
    return getattr(func, "_is_action", False)

def is_compute(func: Any) -> bool:
    return getattr(func, "_is_compute", False)

def is_constrain(func: Any) -> bool:
    return getattr(func, "_is_constrain", False)