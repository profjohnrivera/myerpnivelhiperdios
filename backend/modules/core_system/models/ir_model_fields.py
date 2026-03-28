# backend/modules/core_system/models/ir_model_fields.py
from app.core.orm import Model, Field, RelationField


class IrModelFields(Model):
    """
    🧬 CATÁLOGO TÉCNICO DE CAMPOS
    Representa los campos físicos/lógicos de cada modelo.
    """
    _name = "ir.model.fields"
    _rec_name = "name"

    _sql_constraints = [
        ("ir_model_fields_unique_model_name", 'UNIQUE("model_id", "name")', "El campo ya existe para este modelo."),
    ]

    name = Field(type_="string", label="Nombre Técnico", required=True, index=True)
    field_description = Field(type_="string", label="Etiqueta")
    model = Field(type_="string", label="Modelo Técnico", required=True, index=True)

    model_id = RelationField("ir.model", label="Modelo", required=True, ondelete="cascade")

    ttype = Field(type_="string", label="Tipo", required=True)
    relation = Field(type_="string", label="Modelo Relacionado")
    required = Field(type_="bool", label="Requerido", default=False)
    readonly = Field(type_="bool", label="Solo Lectura", default=False)
    index = Field(type_="bool", label="Indexado", default=False)
    store = Field(type_="bool", label="Persistido", default=True)
    translate = Field(type_="bool", label="Traducible", default=False)
    active = Field(type_="bool", label="Activo", default=True)