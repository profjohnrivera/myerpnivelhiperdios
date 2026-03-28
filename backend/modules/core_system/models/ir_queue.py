# backend/modules/core_system/models/ir_queue.py
from app.core.orm import Model, Field, SelectionField

class IrQueue(Model):
    """
    🏗️ COLA DE TRABAJOS DISTRIBUIDA (ir.queue)
    Tabla persistente para tareas en segundo plano. A prueba de fallos y reinicios.
    """
    _name = 'ir.queue'
    _rec_name = 'method_name'

    model_name = Field(type_='string', label='Modelo Destino', required=True, index=True)
    method_name = Field(type_='string', label='Método a Ejecutar', required=True)
    
    # Los argumentos viajan como JSON (La memoria RAM no es compartida entre servidores)
    args_json = Field(type_='text', default='[]', label='Argumentos (JSON)')
    kwargs_json = Field(type_='text', default='{}', label='Kwargs (JSON)')
    
    state = SelectionField(
        options=[
            ('pending', 'Pendiente'), 
            ('started', 'En Progreso'), 
            ('done', 'Completado'), 
            ('failed', 'Fallido')
        ],
        default='pending',
        label='Estado',
        index=True
    )
    
    priority = Field(type_='integer', default=10, label='Prioridad', index=True)
    error_log = Field(type_='text', label='Log de Error')
    
    date_started = Field(type_='datetime', label='Fecha de Inicio')
    date_finished = Field(type_='datetime', label='Fecha de Fin')