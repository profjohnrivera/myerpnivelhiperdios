# backend/modules/core_system/models/ir_model.py
from app.core.orm import Model, Field


class IrModel(Model):
    """
    🧠 CATÁLOGO TÉCNICO DE MODELOS
    Representa cada modelo registrado en el Registry.
    """
    _name = "ir.model"
    _rec_name = "name"

    _sql_constraints = [
        ("ir_model_model_unique", 'UNIQUE("model")', "El nombre técnico del modelo debe ser único."),
    ]

    name = Field(type_="string", label="Nombre Humano", required=True, index=True)
    model = Field(type_="string", label="Nombre Técnico", required=True, index=True)
    state = Field(type_="string", label="Estado", default="base")
    module = Field(type_="string", label="Módulo")
    transient = Field(type_="bool", label="Transient", default=False)
    abstract = Field(type_="bool", label="Abstract", default=False)
    active = Field(type_="bool", label="Activo", default=True)