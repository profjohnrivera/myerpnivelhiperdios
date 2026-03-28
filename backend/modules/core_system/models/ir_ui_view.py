# backend/modules/core_system/models/ir_ui_view.py
from app.core.orm import Model, Field, SelectionField, RelationField

class IrUiView(Model):
    """
    🎨 VISTAS EN BASE DE DATOS (SDUI Persistente)
    Almacena la arquitectura visual de las pantallas. Si existe una vista aquí,
    sobreescribe al Scaffolder automático.
    """
    _name = 'ir.ui.view'
    _rec_name = 'name'

    name = Field(type_='string', label='Nombre de la Vista', required=True)
    
    # El modelo al que pertenece esta vista (ej: 'sale.order')
    model_name = Field(type_='string', label='Modelo Destino', required=True, index=True)
    
    type = SelectionField(
        options=[('list', 'Lista / DataGrid'), ('form', 'Formulario'), ('kanban', 'Tablero Kanban')],
        default='form',
        label='Tipo de Vista',
        required=True
    )
    
    # Aquí se guardará el JSON/AST del componente visual (SDUI)
    arch = Field(type_='text', label='Arquitectura (JSON)', required=True)
    
    # Si hay múltiples vistas para un modelo, se elige la de menor prioridad
    priority = Field(type_='integer', default=16, label='Prioridad')
    active = Field(type_='bool', default=True, label='Activo')