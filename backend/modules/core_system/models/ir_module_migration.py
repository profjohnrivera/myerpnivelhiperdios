# backend/modules/core_system/models/ir_module_migration.py

from app.core.orm import Model, Field, SelectionField


class IrModuleMigration(Model):
    """
    🧬 REGISTRO DE MIGRACIONES APLICADAS

    Cada fila representa una migración versionada por módulo.
    """
    _name = "ir.module.migration"
    _rec_name = "name"
    _description = "Migraciones de Módulo"

    _sql_constraints = [
        (
            "ir_module_migration_unique_module_name",
            'UNIQUE("module_name", "name")',
            "La migración ya fue registrada para este módulo.",
        ),
    ]

    module_name = Field(type_="string", label="Módulo", required=True, index=True)
    name = Field(type_="string", label="Migración", required=True, index=True)
    description = Field(type_="string", label="Descripción")
    state = SelectionField(
        options=[("done", "Aplicada"), ("failed", "Fallida")],
        default="done",
        label="Estado",
        required=True,
    )
    applied_at = Field(type_="datetime", label="Aplicada en", required=True)
    duration_ms = Field(type_="integer", label="Duración ms", default=0)
    checksum = Field(type_="string", label="Checksum", index=True)
    error_log = Field(type_="text", label="Error")
    active = Field(type_="bool", label="Activo", default=True)