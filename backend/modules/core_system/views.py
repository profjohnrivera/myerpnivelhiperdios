# backend/modules/core_system/views.py
from app.core.sdui import (
    Component,
    Container,
    HeaderBar,
    Card,
    Group,
    Notebook,
    Typography,
    TextInput,
    Button,
    Badge,
)


class SequenceFormView(Component):
    """
    🎨 VISTA EXPLÍCITA MODERNA PARA ir.sequence
    Compatible con el SDUI actual.
    """
    def __init__(self):
        self.id = "ir.sequence.form"
        self.model = "ir.sequence"
        self.view_type = "form"

    def compile(self) -> dict:
        view_ast = Container(
            layout="col",
            gap=0,
            padding=0,
            border=False,
            children=[
                HeaderBar(children=[
                    Container(
                        layout="row",
                        gap=2,
                        padding=0,
                        border=False,
                        children=[
                            Button(label="Generar Siguiente", action="action_confirm", variant="primary"),
                        ],
                    )
                ]),
                Card(children=[
                    Container(
                        layout="col",
                        gap=2,
                        padding=0,
                        children=[
                            Typography(content="Gestión de Secuencia", variant="h1"),
                            Group(columns=2, children=[
                                Container(layout="col", gap=1, padding=0, children=[
                                    TextInput(name="name", label="Referencia/Nombre"),
                                    TextInput(name="code", label="Código Técnico"),
                                    TextInput(name="prefix", label="Prefijo"),
                                    TextInput(name="padding", label="Relleno"),
                                ]),
                                Container(layout="col", gap=1, padding=0, children=[
                                    TextInput(name="number_next", label="Siguiente"),
                                    Badge(name="active", label="Activo"),
                                    Badge(name="state", label="Estado"),
                                ]),
                            ]),
                            Notebook(
                                tabs=["General", "Auditoría"],
                                children=[
                                    Container(
                                        layout="col",
                                        gap=2,
                                        padding=2,
                                        children=[
                                            Typography(content="Configuración general", variant="h2"),
                                            TextInput(name="implementation", label="Implementación"),
                                        ],
                                    ),
                                    Container(
                                        layout="col",
                                        gap=2,
                                        padding=2,
                                        children=[
                                            Typography(content="Trazabilidad técnica", variant="h2"),
                                            TextInput(name="create_date", label="Creado el"),
                                            TextInput(name="create_uid", label="Creado por"),
                                            TextInput(name="write_date", label="Editado el"),
                                            TextInput(name="write_uid", label="Editado por"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ]),
            ],
        ).to_json()

        view_ast["id"] = self.id
        view_ast["model"] = self.model
        view_ast["view_type"] = self.view_type
        return view_ast


def sequence_detail(id=None):
    """
    Compatibilidad con el diseño viejo basado en funciones.
    """
    return SequenceFormView().compile()