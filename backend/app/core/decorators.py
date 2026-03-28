# backend/app/core/decorators.py
import functools
import asyncio
from typing import Callable, Any, Optional, Tuple
from app.core.transaction import transaction as tx_manager

# --- 🎯 INTERFAZ Y ACCIONES (Server-Driven UI) ---

def action(label: str, icon: str = "zap", variant: str = "primary", confirm: str = None):
    """
    🎯 DECORADOR DE ACCIÓN
    Marca un método para que el Frontend genere automáticamente un botón para ejecutarlo.
    """
    def decorator(func: Callable) -> Callable:
        func._is_action = True
        func._action_meta = {
            "name": func.__name__,
            "label": label,
            "icon": icon,
            "variant": variant,
            "confirm_message": confirm
        }
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._is_action = True
        wrapper._action_meta = func._action_meta
        return wrapper
        
    return decorator

# --- 🔐 INTEGRIDAD Y TRANSACCIONES ---

def transaction(func: Callable) -> Callable:
    """
    🎁 DECORADOR DE TRANSACCIONALIDAD ATÓMICA
    Asegura que la función se ejecute dentro de un bloque ACID.
    Si algo falla, el Rollback es automático.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with tx_manager():
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
            
    return wrapper

# --- 🧠 INTELIGENCIA REACTIVA (ORM Core) ---

def depends(*fields: str):
    """
    🧮 DECORADOR DE DEPENDENCIAS
    Indica que un campo calculado debe re-ejecutarse si estos campos cambian.
    """
    def decorator(func: Callable) -> Callable:
        func._is_compute = True
        func._depends_on = fields
        return func
    return decorator

def constrains(*fields: str):
    """
    🛡️ DECORADOR DE RESTRICCIONES
    Garantiza la integridad de negocio. Se dispara automáticamente al validar.
    """
    def decorator(func: Callable) -> Callable:
        func._is_constrain = True
        func._constrain_fields = fields
        return func
    return decorator

# --- 🛠️ HELPERS DE INSPECCIÓN ---

def is_ui_action(func: Any) -> bool:
    """Verifica si un método es una acción de interfaz."""
    return getattr(func, "_is_action", False)

def is_compute(func: Any) -> bool:
    """Verifica si un método es un cálculo reactivo."""
    return getattr(func, "_is_compute", False)

def is_constrain(func: Any) -> bool:
    """Verifica si un método es una restricción de integridad."""
    return getattr(func, "_is_constrain", False)