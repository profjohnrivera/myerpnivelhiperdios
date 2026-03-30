# backend/modules/core_base/models/res_groups.py
# ============================================================
# FIX CRÍTICO-2: Admin identificado por flag is_system_admin,
#   no por nombre de string hardcodeado.
#
# ANTES: ir_rule.py buscaba:
#   WHERE g.name IN ('Administración / Ajustes', ...)
#   → Frágil: renombrar el grupo rompe la seguridad.
#   → Peligroso: crear un grupo con ese nombre = acceso total.
#
# AHORA: ir_rule.py busca:
#   WHERE g.is_system_admin = TRUE
#   → Inmutable: el flag solo se puede cambiar desde el código
#     de boot o con sudo() explícito.
#   → Auditable: cualquier cambio a is_system_admin genera
#     un registro en ir.audit.log.
# ============================================================
from app.core.orm import Model, Field


class ResGroups(Model):
    """
    👥 GRUPOS DE SEGURIDAD (Roles)
    Agrupa usuarios para asignarles permisos de acceso masivos (RBAC) y Reglas (RLS).
    """
    _name = "res.groups"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre del Grupo", required=True)
    description = Field(type_="text", label="Descripción detallada")

    user_ids = Field(type_="many2many", target="res.users", label="Usuarios asignados")

    # FIX CRÍTICO-2: Flag de administrador del sistema.
    # Cuando es True, el usuario bypass toda regla RLS.
    # SOLO se activa desde el boot de core_system/data/security.py.
    # Nunca se activa desde la UI — readonly en el formulario.
    is_system_admin = Field(
        type_="bool",
        default=False,
        label="Es Administrador del Sistema",
        readonly=True,
    )