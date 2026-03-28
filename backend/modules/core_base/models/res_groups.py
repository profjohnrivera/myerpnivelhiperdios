# backend/modules/core_base/models/res_groups.py
from app.core.orm import Model, Field

class ResGroups(Model):
    """
    👥 GRUPOS DE SEGURIDAD (Roles)
    Agrupa usuarios para asignarles permisos de acceso masivos (RBAC) y Reglas (RLS).
    Ejemplo: 'Ventas / Administrador', 'Inventario / Lector'.
    """
    _name = "res.groups"
    _rec_name = "name"

    name = Field(type_='string', label='Nombre del Grupo', required=True)
    description = Field(type_='text', label='Descripción detallada')
    
    # En HiperDios, los Many2many se gestionan nativamente guardando 
    # arreglos de IDs en Postgres (gracias al motor de JSONB o tablas Rel).
    user_ids = Field(type_='many2many', target='res.users', label='Usuarios asignados')