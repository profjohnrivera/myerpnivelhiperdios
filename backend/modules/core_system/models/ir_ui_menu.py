# backend/modules/core_system/models/ir_ui_menu.py
from app.core.orm import Field, RelationField
from app.core.tree import TreeModel

class IrUiMenu(TreeModel):
    """
    🗺️ NAVEGACIÓN UNIVERSAL (SDUI)
    Define la estructura de menús que el cliente renderizará.
    Al heredar de TreeModel, gana superpoderes de jerarquía (Parent/Child).
    """
    _name = 'ir.ui.menu'
    _rec_name = 'name'
    
    name = Field(type_='string', required=True, label='Nombre del Menú')
    
    # Jerarquía: Relación consigo mismo para anidar menús infinitamente
    parent_id = RelationField('ir.ui.menu', ondelete='cascade', label='Menú Padre')
    
    # La acción o modelo a abrir. Ej: 'res.users', 'sale.order'
    action = Field(type_='string', label='Acción/Ruta SDUI') 
    
    icon = Field(type_='string', label='Icono (Lucide)')
    sequence = Field(type_='integer', default=10, label='Orden de Visualización')
    
    # 🛡️ SEGURIDAD DE UI: Si está vacío, es público. Si tiene roles, solo ellos lo ven.
    group_ids = Field(type_='many2many', target='res.groups', label='Grupos Permitidos')
    
    is_category = Field(type_='bool', default=False, label='Es Categoría Raíz')