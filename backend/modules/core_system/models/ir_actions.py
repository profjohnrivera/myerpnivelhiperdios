# backend/modules/core_system/models/ir_actions.py
import asyncio
from app.core.orm import Model, Field, SelectionField
from app.core.worker import WorkerEngine

class IrActionsActWindow(Model):
    """
    🚀 ACCIONES DE VENTANA
    Define qué sucede cuando un usuario hace clic en un elemento del menú.
    Controla qué modelo se abre y con qué filtros (Domain) o valores por defecto (Context).
    """
    _name = 'ir.actions.act_window'
    _rec_name = 'name'

    name = Field(type_='string', label='Nombre de la Acción', required=True)
    
    # El modelo que se va a abrir (ej: 'res.users')
    res_model = Field(type_='string', label='Modelo Destino', required=True, index=True)
    
    # Vistas permitidas, ej: "list,form"
    view_mode = Field(type_='string', default='list,form', label='Modos de Vista')
    
    # Filtro fijo inyectado en la búsqueda. Ej: [('is_company', '=', True)]
    domain = Field(type_='string', default='[]', label='Dominio (Filtro JSON)')
    
    # Valores por defecto al crear nuevos registros. Ej: {'default_is_company': True}
    context = Field(type_='string', default='{}', label='Contexto (JSON)')
    
    # Ayuda visual si la tabla está vacía
    help_text = Field(type_='text', label='Mensaje de Ayuda (HTML/Markdown)')


class IrActionsServer(Model):
    """
    ⚡ ACCIONES DE SERVIDOR
    Permite ejecutar código Python o disparar tareas asíncronas desde la UI.
    """
    _name = 'ir.actions.server'
    _rec_name = 'name'
    
    name = Field(type_='string', required=True, label="Nombre de la Acción")
    
    # Identificador del modelo sobre el que aplica la acción (Ej: 'sale.order')
    model_id = Field(type_='string', required=True, label="Modelo Destino") 
    
    state = SelectionField(
        options=[
            ('code', 'Ejecutar Código Python'), 
            ('object_create', 'Crear Nuevo Registro'), 
            ('worker', 'Tarea de Fondo (Worker)')
        ], 
        default='code', 
        label="Tipo de Ejecución"
    )
    
    code = Field(type_='text', label="Código Python / Script")

    async def run(self, record_ids: list):
        """Ejecuta la lógica de la acción."""
        if self.state == 'worker':
            # Disparamos la tarea al obrero para que el usuario no espere (No bloquea el Event Loop)
            await WorkerEngine.enqueue(self._execute_logic, record_ids)
            return {"type": "notification", "message": "Procesando en segundo plano..."}
        
        # Lógica para ejecutar código dinámico o métodos...
        print(f"   ⚡ Ejecutando Acción de Servidor: {self.name} sobre los IDs: {record_ids}")
        return True

    async def _execute_logic(self, ids):
        """Simulación de un trabajo pesado procesado por el WorkerEngine."""
        # Aquí iría la ejecución real pesada
        await asyncio.sleep(2) 
        print(f"   ✅ Acción asíncrona '{self.name}' finalizada con éxito para los IDs: {ids}")