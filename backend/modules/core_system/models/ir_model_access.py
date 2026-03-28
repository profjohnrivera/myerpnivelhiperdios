# backend/modules/core_system/models/ir_model_access.py
from app.core.orm import Model, Field, RelationField

class IrModelAccess(Model):
    """
    🛡️ PERMISOS DE ACCESO CRUD (ir.model.access)
    Define si un Grupo (Rol) tiene derecho a interactuar con un Modelo (Tabla).
    """
    _name = "ir.model.access"
    _rec_name = "name"

    name = Field(type_='string', label='Nombre del Permiso', required=True)
    
    # Relación a la tabla técnica 'ir.model' generada por el SyncEngine
    model_id = RelationField("ir.model", label="Modelo", required=True, ondelete="cascade")
    
    # Si group_id está vacío, el permiso se vuelve GLOBAL (público para todos)
    group_id = RelationField("res.groups", label="Grupo de Acceso", ondelete="cascade")
    
    # Matriz de Permisos (Por defecto cerrado/False)
    perm_read = Field(type_='bool', default=False, label='Permiso Lectura')
    perm_write = Field(type_='bool', default=False, label='Permiso Escritura')
    perm_create = Field(type_='bool', default=False, label='Permiso Creación')
    perm_unlink = Field(type_='bool', default=False, label='Permiso Borrado')
    
    active = Field(type_='bool', default=True, label='Activo')