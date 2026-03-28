# backend/modules/core_system/models/ir_actions.py
from app.core.orm import Model, Field


class IrActionsActWindow(Model):
    """
    Acción de ventana tipo Odoo:
    abre vistas de un modelo en list/form/kanban, etc.
    """
    _name = "ir.actions.act_window"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre", required=True, index=True)
    res_model = Field(type_="string", label="Modelo Destino", required=True, index=True)
    view_mode = Field(type_="string", label="Modo de Vista", default="list,form")
    domain = Field(type_="text", label="Dominio")
    context = Field(type_="text", label="Contexto")
    target = Field(type_="string", label="Target", default="current")
    active = Field(type_="bool", label="Activo", default=True)


class IrActionsServer(Model):
    """
    Acción de servidor:
    ejecuta lógica del backend sobre un modelo.
    """
    _name = "ir.actions.server"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre", required=True, index=True)
    model_name = Field(type_="string", label="Modelo", required=True, index=True)
    state = Field(type_="string", label="Estado", default="code")
    code = Field(type_="text", label="Código")
    usage = Field(type_="string", label="Uso")
    active = Field(type_="bool", label="Activo", default=True)


# -----------------------------------------------------------------------------
# Compatibilidad hacia atrás
# -----------------------------------------------------------------------------
IrActionActWindow = IrActionsActWindow
IrActionServer = IrActionsServer