# backend/modules/mod_test/views/test_advanced_record_views.py

from app.core.sdui import (
    Component,
    Container,
    HeaderBar,
    StatusBar,
    Card,
    Group,
    ModelActions,
    TextInput,
    Many2OneLookup,
    SelectInput,
    HtmlEditor,
    JsonEditor,
    ReferenceInput,
)


class TestAdvancedRecordFormView(Component):
    def __init__(self):
        self.id = "test.advanced.record.form"
        self.model = "test.advanced.record"
        self.view_type = "form"

    def compile(self) -> dict:
        view_ast = Container(
            layout="col",
            gap=0,
            padding=0,
            border=False,
            children=[
                HeaderBar(children=[
                    ModelActions("test.advanced.record"),
                    StatusBar(
                        field="state",
                        options=[["draft", "Borrador"], ["done", "Completado"]],
                    ),
                ]),
                Card(children=[
                    Group(columns=2, children=[
                        Container(layout="col", gap=1, padding=0, children=[
                            TextInput(name="name", label="Nombre"),
                            Many2OneLookup(name="user_id", label="Responsable", comodel="res.users"),
                            Many2OneLookup(name="partner_id", label="Contacto", comodel="res.partner"),
                            ReferenceInput(
                                name="reference_target",
                                label="Referencia Global",
                                allowed_models=["res.partner", "res.company", "product.product"],
                            ),
                        ]),
                        Container(layout="col", gap=1, padding=0, children=[
                            TextInput(name="user_login", label="Login del Responsable", readonly=True),
                            Many2OneLookup(
                                name="user_company_id",
                                label="Compañía del Responsable",
                                comodel="res.company",
                                readonly=True,
                            ),
                            TextInput(name="partner_email", label="Email del Contacto", readonly=True),
                            SelectInput(
                                name="state",
                                label="Estado",
                                options=[["draft", "Borrador"], ["done", "Completado"]],
                            ),
                        ]),
                    ]),
                    Container(layout="col", gap=4, padding=4, children=[
                        HtmlEditor(name="html_content", label="Contenido HTML"),
                        JsonEditor(name="payload_json", label="Payload JSON"),
                    ]),
                ]),
            ],
        ).to_json()

        view_ast["id"] = self.id
        return view_ast