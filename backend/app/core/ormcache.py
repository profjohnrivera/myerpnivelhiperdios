# backend/app/core/ormcache.py
# ============================================================
# CACHÉ DISTRIBUIDA BIFÁSICA — ARQUITECTURA DEFINITIVA
#
# Dos capas:
#   _model_cache   → búsquedas globales por modelo (listas, dominios)
#   _record_cache  → datos granulares por registro individual
#
# Protección anti-OOM: LRUCache por modelo y por registro.
#
# Invalidación quirúrgica via PostgreSQL LISTEN/NOTIFY:
#   'sale.order'   → limpia búsquedas globales, preserva registros
#   'sale.order:5' → limpia registro 5 + búsquedas globales
#
# FIX DEFINITIVO — Sentinel para distinguir cache miss de None:
#   El problema anterior: ORMCache.get() retornaba None tanto para
#   "clave no encontrada" como para "valor cacheado es None".
#   El decorator @ormcache hacía `if cached_result is not None`
#   → funciones que retornan None legítimamente nunca se cacheaban.
#   Solución: objeto centinela _CACHE_MISS que solo existe aquí.
#   get() retorna _CACHE_MISS si no hay hit → distinguible de None.
# ============================================================

from functools import wraps
from typing import Any, Dict, Optional
from cachetools import LRUCache
import hashlib
import json


# Centinela privado. Identidad de objeto única en toda la VM.
# Nunca puede aparecer como valor legítimo de negocio.
_CACHE_MISS = object()


class ORMCache:
    """
    🧠 GESTOR DE CACHÉ DISTRIBUIDA BIFÁSICA

    Separación de responsabilidades:
    - _model_cache  : resultados de búsqueda/dominio (scope: modelo completo)
    - _record_cache : datos de registros individuales (scope: id específico)

    Ambas capas protegidas por LRUCache para evitar OOM.
    Invalidación por NOTIFY desde postgres_storage después de cada write.
    """

    # Caché Global: { 'sale.order': LRUCache(5000) }
    _model_cache: Dict[str, LRUCache] = {}

    # Caché Granular: { 'sale.order': { '5': LRUCache(200) } }
    _record_cache: Dict[str, Dict[str, LRUCache]] = {}

    # Límites de seguridad anti-OOM
    MAX_MODEL_SIZE = 5000
    MAX_RECORD_SIZE = 200

    @classmethod
    def get(cls, model_name: str, key: str, record_id: Optional[str] = None) -> Any:
        """
        Extrae un valor en O(1).
        Retorna _CACHE_MISS si la clave no existe.
        Retorna None si el valor cacheado ES None (hit legítimo).
        """
        if record_id:
            rec_store = cls._record_cache.get(model_name, {}).get(str(record_id))
            if rec_store is None:
                return _CACHE_MISS
            return rec_store.get(key, _CACHE_MISS)

        model_store = cls._model_cache.get(model_name)
        if model_store is None:
            return _CACHE_MISS
        return model_store.get(key, _CACHE_MISS)

    @classmethod
    def is_miss(cls, value: Any) -> bool:
        """Helper para comprobar si get() produjo un cache miss."""
        return value is _CACHE_MISS

    @classmethod
    def set(cls, model_name: str, key: str, value: Any, record_id: Optional[str] = None):
        """Almacena cualquier valor, incluido None, con protección LRU."""
        if record_id:
            rec_id = str(record_id)
            if model_name not in cls._record_cache:
                cls._record_cache[model_name] = {}
            if rec_id not in cls._record_cache[model_name]:
                cls._record_cache[model_name][rec_id] = LRUCache(maxsize=cls.MAX_RECORD_SIZE)
            cls._record_cache[model_name][rec_id][key] = value
        else:
            if model_name not in cls._model_cache:
                cls._model_cache[model_name] = LRUCache(maxsize=cls.MAX_MODEL_SIZE)
            cls._model_cache[model_name][key] = value

    @classmethod
    def clear(cls, payload: str = None):
        """
        🧹 INVALIDACIÓN QUIRÚRGICA (llamada desde LISTEN/NOTIFY de Postgres)

        Sin payload       → flush total (solo en emergencias/tests)
        'sale.order'      → limpia búsquedas globales, preserva registros
        'sale.order:5'    → limpia registro 5 + búsquedas globales del modelo
        """
        if not payload:
            cls._model_cache.clear()
            cls._record_cache.clear()
            return

        if ":" in payload:
            model_name, record_id = payload.split(":", 1)
            # Invalida solo este registro
            if model_name in cls._record_cache:
                cls._record_cache[model_name].pop(record_id, None)
            # Invalida búsquedas globales (pueden incluir este registro)
            if model_name in cls._model_cache:
                cls._model_cache[model_name].clear()
        else:
            # Solo búsquedas globales; registros individuales siguen válidos
            if payload in cls._model_cache:
                cls._model_cache[payload].clear()


def ormcache(model_name: str):
    """
    🛡️ DECORADOR DE CACHÉ — INTELIGENCIA CONTEXTUAL

    Auto-detecta granularidad:
    - Si args[0] tiene .id  → caché granular (por registro)
    - Si no               → caché global (por modelo)

    Cache key: SHA-256 de los argumentos (sin self/cls).
    Usa SHA-256 en lugar de MD5 para evitar colisiones en args complejos.

    Corrección definitiva del sentinel:
    Antes: `if cached_result is not None` → nunca cacheaba None legítimo.
    Ahora: `if not ORMCache.is_miss(cached_result)` → correcto para cualquier valor.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Detectar si es instancia (granular) o clase (global)
            record_id = None
            if args and not isinstance(args[0], type) and hasattr(args[0], "id"):
                record_id = str(args[0].id) if args[0].id else None

            # Hash de argumentos (excluir self/cls)
            safe_args = args[1:] if args else ()
            try:
                raw = json.dumps(
                    {"a": safe_args, "k": kwargs},
                    sort_keys=True,
                    default=str,
                )
            except Exception:
                raw = str(safe_args) + str(kwargs)

            key = hashlib.sha256(raw.encode()).hexdigest()

            # Intentar hit de caché
            cached = ORMCache.get(model_name, key, record_id)
            if not ORMCache.is_miss(cached):
                return cached

            # Ejecutar función original
            result = await func(*args, **kwargs)

            # Almacenar resultado (incluido None)
            ORMCache.set(model_name, key, result, record_id)
            return result

        return wrapper
    return decorator