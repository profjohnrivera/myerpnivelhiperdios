# backend/modules/core_system/models/ir_ui_view.py

from app.core.orm import Model, Field, SelectionField


class IrUiView(Model):
    """
    🎨 CATÁLOGO PERSISTENTE DE VISTAS (NO runtime source of truth)

    Decisión arquitectónica:
    - La ejecución real de vistas vive en ViewScaffolder
    - ir.ui.view persiste snapshots, metadatos técnicos y material exportable
    - NO sobreescribe automáticamente la vista de runtime

    Uso previsto:
    - inspección técnica
    - auditoría / diff
    - exportación
    - snapshot de vistas explícitas o generadas
    - futura base para extensiones declarativas (sin convertir BD en la verdad principal)
    """
    _name = "ir.ui.view"
    _rec_name = "name"
    _description = "Catálogo técnico de vistas"

    name = Field(type_="string", label="Nombre de la Vista", required=True)

    # Clave lógica estable: ej. "sale.order.form"
    view_key = Field(type_="string", label="Clave de Vista", required=True, index=True)

    # Modelo destino: ej. "sale.order"
    model_name = Field(type_="string", label="Modelo Destino", required=True, index=True)

    type = SelectionField(
        options=[
            ("list", "Lista / DataGrid"),
            ("form", "Formulario"),
            ("kanban", "Tablero Kanban"),
        ],
        default="form",
        label="Tipo de Vista",
        required=True,
    )

    # JSON / AST SDUI serializado
    arch = Field(type_="text", label="Arquitectura (JSON)", required=True)

    # Origen técnico de la vista persistida
    source = SelectionField(
        options=[
            ("explicit_code", "Vista explícita en código"),
            ("generated_code", "Vista generada por scaffolder"),
            ("manual_snapshot", "Snapshot manual"),
        ],
        default="generated_code",
        label="Origen",
        required=True,
    )

    # Rol persistente, NO runtime
    runtime_role = SelectionField(
        options=[
            ("snapshot", "Snapshot técnico"),
            ("catalog", "Catálogo técnico"),
            ("experimental", "Experimental"),
        ],
        default="snapshot",
        label="Rol",
        required=True,
    )

    # Huella para detectar cambios entre compilaciones/exportaciones
    checksum = Field(type_="string", label="Checksum", index=True)

    # Se conserva por compatibilidad técnica / orden visual
    priority = Field(type_="int", default=16, label="Prioridad")

    notes = Field(type_="text", label="Notas Técnicas")
    active = Field(type_="bool", default=True, label="Activo")