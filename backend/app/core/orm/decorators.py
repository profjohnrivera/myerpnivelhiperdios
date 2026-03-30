# backend/app/core/orm/decorators.py

from functools import wraps
from typing import List

from .fields import ComputedField


def compute(depends: List[str], store: bool = False):
    def decorator(func):
        return ComputedField(func, depends, store=store)
    return decorator


def check_state(allowed_states: List[str]):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            current_state = getattr(self, "state", None)
            if current_state and current_state not in allowed_states:
                raise PermissionError(
                    f"⛔ Acción '{func.__name__}' bloqueada. Estado '{current_state}' no permitido."
                )
            return await func(self, *args, **kwargs)

        wrapper._is_action = True
        return wrapper
    return decorator


def onchange(*fields):
    def decorator(func):
        func._onchange_fields = fields
        return func
    return decorator