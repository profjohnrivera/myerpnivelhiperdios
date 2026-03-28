# backend/modules/core_system/models/ir_model_data.py
import re
from typing import Optional, Any, Type
from app.core.orm import Model, Field
from app.core.env import Context
from app.core.registry import Registry

class IrModelData(Model):
    """
    🔗 MAPA DE IDENTIFICADORES EXTERNOS (ir.model.data)
    Traduce nombres legibles (xml_id: 'base.main_company') a IDs enteros físicos.
    Esta pieza es el motor de la idempotencia: permite recargar archivos JSON 
    sin duplicar datos.
    """
    _name = 'ir.model.data'
    _rec_name = 'name'
    
    module = Field(type_='string', label='Módulo', required=True, index=True)
    name = Field(type_='string', label='ID Externo', required=True, index=True)
    model_name = Field(type_='string', label='Modelo Técnico', required=True)
    
    # 💎 FIX FASE 3: El ID físico ahora es un entero
    res_id = Field(type_='integer', label='ID Físico', required=True)
    
    noupdate = Field(type_='bool', default=False, label='No Actualizar')
    active = Field(type_='bool', default=True, label='Activo')

    # =========================================================
    # 🧠 MOTOR DE CACHÉ (Aislado por Transacción)
    # =========================================================

    @classmethod
    def _get_cache(cls) -> dict:
        """Extrae la caché directamente del Grafo vivo en el Contexto actual."""
        graph = Context.get_graph()
        if not graph:
            # Fallback para procesos fuera de contexto (mantenimiento)
            if not hasattr(cls, '_static_cache'): cls._static_cache = {}
            return cls._static_cache
        
        # Anclamos la caché al grafo para que se limpie sola al terminar la transacción
        if not hasattr(graph, '_xmlid_cache'):
            graph._xmlid_cache = {}
        return graph._xmlid_cache

    # =========================================================
    # 🔍 MÉTODOS DE RESOLUCIÓN
    # =========================================================

    @classmethod
    async def get_id(cls, xml_id: str) -> Optional[int]:
        """
        Traduce 'modulo.nombre' a un ID Entero.
        Usa caché en memoria antes de tocar la Base de Datos.
        """
        cache = cls._get_cache()
        if xml_id in cache:
            return cache[xml_id]
        
        if "." not in xml_id:
            return None
            
        module, name = xml_id.split(".", 1)
        # Búsqueda optimizada vía ORM
        records = await cls.search([('module', '=', module), ('name', '=', name)])
        
        if records:
            res_id = records[0].res_id
            cache[xml_id] = res_id
            return res_id
            
        return None

    @classmethod
    async def get_object(cls, xml_id: str) -> Optional[Any]:
        """
        Retorna la instancia real del modelo (Recordset) usando un xml_id.
        Ejemplo: user = await IrModelData.get_object('base.user_admin')
        """
        cache = cls._get_cache()
        res_id = await cls.get_id(xml_id)
        
        if not res_id:
            return None
            
        # Buscamos el registro para saber qué modelo es
        data_record = (await cls.search([('res_id', '=', res_id)]))[0]
        ModelClass = Registry.get_model(data_record.model_name)
        
        return ModelClass(_id=res_id, context=Context.get_graph())

    @classmethod
    def set_cache(cls, xml_id: str, res_id: int) -> None:
        """Registra un mapeo en la caché actual."""
        cache = cls._get_cache()
        cache[xml_id] = res_id

    # =========================================================
    # 🛠️ UTILITARIOS
    # =========================================================

    @classmethod
    def is_xml_id(cls, value: str) -> bool:
        """Verifica si un string tiene formato de identificador externo."""
        return isinstance(value, str) and bool(re.match(r'^[a-z0-9_]+\.[a-z0-9_]+$', value))

    async def unlink(self):
        """Al eliminar el mapeo, limpiamos la caché."""
        xml_id = f"{self.module}.{self.name}"
        cache = self._get_cache()
        if xml_id in cache:
            del cache[xml_id]
        return await super().unlink()