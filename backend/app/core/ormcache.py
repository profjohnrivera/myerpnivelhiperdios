# backend/app/core/ormcache.py
from functools import wraps
import hashlib
import json
from typing import Any, Dict, Optional
from cachetools import LRUCache  # El guardián anti-colapso de RAM

class ORMCache:
    """
    🧠 GESTOR DE CACHÉ DISTRIBUIDA BIFÁSICA (Nivel HiperDios)
    Separa la caché Global (búsquedas, vistas) de la caché Granular (registros individuales).
    Usa LRU para proteger el servidor de Fugas de Memoria (OOM Killer).
    """
    
    # 1. Caché Global: { 'sale.order': LRUCache(1000) }
    _model_cache: Dict[str, LRUCache] = {}
    
    # 2. Caché Granular: { 'sale.order': { '5': LRUCache(100), '6': LRUCache(100) } }
    _record_cache: Dict[str, Dict[str, LRUCache]] = {}

    # Umbrales máximos de seguridad
    MAX_MODEL_SIZE = 5000
    MAX_RECORD_SIZE = 200

    @classmethod
    def get(cls, model_name: str, key: str, record_id: Optional[str] = None) -> Any:
        """Extrae el dato en O(1)."""
        if record_id:
            return cls._record_cache.get(model_name, {}).get(str(record_id), {}).get(key)
        return cls._model_cache.get(model_name, {}).get(key)

    @classmethod
    def set(cls, model_name: str, key: str, value: Any, record_id: Optional[str] = None):
        """Almacena protegiendo los límites de memoria."""
        if record_id:
            rec_id = str(record_id)
            if model_name not in cls._record_cache:
                cls._record_cache[model_name] = {}
            if rec_id not in cls._record_cache[model_name]:
                # Inyectamos el escudo LRU por cada registro
                cls._record_cache[model_name][rec_id] = LRUCache(maxsize=cls.MAX_RECORD_SIZE)
            cls._record_cache[model_name][rec_id][key] = value
        else:
            if model_name not in cls._model_cache:
                cls._model_cache[model_name] = LRUCache(maxsize=cls.MAX_MODEL_SIZE)
            cls._model_cache[model_name][key] = value

    @classmethod
    def clear(cls, payload: str = None):
        """
        🧹 INVALIDACIÓN QUIRÚRGICA:
        - Payload 'sale.order' -> Limpia búsquedas globales (listas), pero SALVA los registros individuales.
        - Payload 'sale.order:5' -> Limpia SOLO el registro 5 y las búsquedas globales.
        """
        if not payload:
            cls._model_cache.clear()
            cls._record_cache.clear()
            print("   🧹 [ORMCache] Limpieza total (Flush All) ejecutada por seguridad.")
            return

        if ":" in payload:
            model_name, record_id = payload.split(":", 1)
            
            # 1. Aniquilamos la caché exclusiva de este registro modificado
            if model_name in cls._record_cache and record_id in cls._record_cache[model_name]:
                del cls._record_cache[model_name][record_id]
                # print(f"   🎯 [ORMCache] Reciclaje granular: {model_name} ID {record_id}")
            
            # 2. Vaciamos la caché global del modelo (porque un cambio afecta a las vistas de Lista/Search)
            if model_name in cls._model_cache:
                cls._model_cache[model_name].clear()
        else:
            model_name = payload
            # Borramos SOLO la caché global. Los miles de registros intactos se quedan en RAM.
            if model_name in cls._model_cache:
                cls._model_cache[model_name].clear()


def ormcache(model_name: str):
    """
    🛡️ DECORADOR DE ACELERACIÓN EXTREMA (Inteligencia Contextual)
    Auto-detecta si el método pertenece a la clase (Global) o a un registro instanciado (Granular).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. AUTO-DESCUBRIMIENTO DE GRANULARIDAD
            record_id = None
            # Si args[0] NO es una clase (Type) y tiene atributo 'id', es un Recordset instanciado.
            if args and not isinstance(args[0], type) and hasattr(args[0], 'id'):
                record_id = str(args[0].id) if args[0].id else None

            # 2. HASH INMUTABLE (Ignorando 'self' o 'cls' que es args[0])
            safe_args = args[1:] if args else ()
            try:
                hash_str = json.dumps({"args": safe_args, "kwargs": kwargs}, sort_keys=True, default=str)
            except Exception:
                hash_str = str(safe_args) + str(kwargs)
                
            key = hashlib.md5(hash_str.encode()).hexdigest()

            # 3. INTERCEPCIÓN EN RAM
            cached_result = ORMCache.get(model_name, key, record_id)
            if cached_result is not None:
                return cached_result

            # 4. EJECUCIÓN NATIVA (Viaje a DB o procesamiento CPU)
            result = await func(*args, **kwargs)

            # 5. PERSISTENCIA EN CACHÉ
            ORMCache.set(model_name, key, result, record_id)
            return result
            
        return wrapper
    return decorator