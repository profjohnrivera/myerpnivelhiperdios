# backend/app/core/service.py
from typing import Any, Dict
from app.core.registry import Registry
from app.core.env import Context
from app.core.storage.postgres_storage import PostgresGraphStorage

class Service:
    @staticmethod
    async def execute_action(model_name: str, action_name: str, record_id: str, payload: Dict = {}) -> Any:
        ModelClass = Registry.get_model(model_name)
        record = ModelClass(_id=record_id)
        
        if not hasattr(record, action_name):
            raise ValueError(f"Action '{action_name}' not found")
        
        method = getattr(record, action_name)

        # 📸 FOTO ANTES DE LA ACCIÓN (Snapshot)
        snapshot = record.graph.snapshot()

        try:
            # 1. Ejecutar Lógica
            result = method(**payload) if payload else method()
            
            # 2. Recalcular Grafo (Procesar @compute y Políticas)
            await record.graph.recalculate()
            
            # 3. Persistencia Atómica
            storage = PostgresGraphStorage()
            await storage.save(record.graph)
            
            return result
            
        except Exception as e:
            # ⏪ SI ALGO FALLA, VOLVEMOS ATRÁS
            record.graph.rollback(snapshot)
            print(f"🔥 TRANSACTION ABORTED: {e}")
            raise e