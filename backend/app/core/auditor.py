# backend/app/core/auditor.py
from typing import Any
from app.core.event_bus import EventBus
from app.core.env import Context
from app.core.registry import Registry
from app.core.worker import WorkerEngine
import json

class AuditService:
    """
    👁️ SERVICIO DE TRAZABILIDAD AUTOMÁTICA
    Escucha al EventBus y genera logs forenses sin bloquear el hilo principal.
    """
    
    @classmethod
    async def bootstrap(cls):
        bus = EventBus()
        # Escuchamos mutaciones de CUALQUIER modelo (*)
        bus.subscribe("*.created", cls.on_record_created)
        bus.subscribe("*.updated", cls.on_record_updated)
        bus.subscribe("*.unlinked", cls.on_record_unlinked)
        print("🕵️ Auditor Universal: Conectado y vigilando mutaciones.")

    @classmethod
    async def on_record_created(cls, model_name: str, record: Any):
        # Encolamos la tarea en el Worker para no ralentizar el 'create'
        await WorkerEngine.enqueue(
            model_name='ir.audit.log', 
            method_name='create_log_task', 
            kwargs={'model': model_name, 'res_id': record.id, 'method': 'create', 'values': None}
        )

    @classmethod
    async def on_record_updated(cls, model_name: str, record: Any, changes: dict, **kwargs):
        # Solo auditamos si hay cambios reales
        if not changes: return
        
        await WorkerEngine.enqueue(
            model_name='ir.audit.log', 
            method_name='create_log_task', 
            kwargs={'model': model_name, 'res_id': record.id, 'method': 'create', 'values': None}
        )

    @classmethod
    async def on_record_unlinked(cls, model_name: str, record_id: str):
        await WorkerEngine.enqueue(
            model_name='ir.audit.log', 
            method_name='create_log_task', 
            kwargs={'model': model_name, 'res_id': record.id, 'method': 'create', 'values': None}
        )

    @staticmethod
    async def _create_log_task(model: str, res_id: str, method: str, values: dict = None):
        """Esta función se ejecuta dentro del Worker (background)"""
        env = Context.get_env()
        try:
            IrAuditLog = Registry.get_model('ir.audit.log')
            
            # Si es una actualización, registramos campo por campo
            if method == 'write' and values:
                for field, new_val in values.items():
                    # Evitamos auditar campos técnicos de fecha/uid para no saturar
                    if field in ['write_date', 'write_uid', 'write_version']: continue
                    
                    await IrAuditLog.create({
                        'res_model': model,
                        'res_id': res_id,
                        'field_name': field,
                        'new_value': str(new_val),
                        'user_id': env.uid if env else 'system',
                        'method': method
                    })
            else:
                # Create o Unlink
                await IrAuditLog.create({
                    'res_model': model,
                    'res_id': res_id,
                    'user_id': env.uid if env else 'system',
                    'method': method
                })
        except Exception as e:
            print(f"⚠️ Error en Auditoría Background: {e}")