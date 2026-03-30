# backend/modules/mod_sales/views/sale_order_views.py

from app.core.sdui import (
    Component,
    Container,
    HeaderBar,
    ModelStatusBar,
    Card,
    Group,
    Many2OneLookup,
    Notebook,
    One2ManyLines,
    ModelActions,
    Chatter,
    DateInput,
    Typography,
    MonetaryInput,
    TextInput,
    SelectInput,
)


class SaleOrderFormView(Component):
    """
    Vista explícita alineada con el modelo real de sale.order.
    Sin campos fantasmas ni contratos heredados de Odoo que aún no existen.
    """

    def __init__(self):
        self.id = "sale.order.form"
        self.model = "sale.order"
        self.view_type = "form"

    def compile(self) -> dict:
        view_ast = Container(
            layout="col",
            gap=0,
            padding=0,
            border=False,
            children=[
                HeaderBar(children=[
                    ModelActions("sale.order"),
                    ModelStatusBar(
                        "sale.order",
                        options=[
                            {"value": "draft", "label": "Cotización", "color": "info"},
                            {"value": "sent", "label": "Cotización Enviada", "color": "info"},
                            {"value": "sale", "label": "Orden de Venta", "color": "success"},
                            {"value": "done", "label": "Completado", "color": "success"},
                            {"value": "cancel", "label": "Cancelado", "color": "danger"},
                        ],
                    ),
                ]),

                Card(children=[
                    Container(layout="col", gap=0, padding=0, children=[
                        TextInput(name="name", label="", readonly=True),
                    ]),

                    Group(columns=2, children=[
                        Container(layout="col", gap=2, padding=0, children=[
                            Many2OneLookup(
                                name="partner_id",
                                label="Cliente",
                                comodel="res.partner",
                                placeholder="Comienza a escribir...",
                                modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]},
                            ),
                            Many2OneLookup(
                                name="company_id",
                                label="Empresa",
                                comodel="res.company",
                                modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]},
                            ),
                        ]),
                        Container(layout="col", gap=1, padding=0, children=[
                            DateInput(name="create_date", label="Fecha de creación", readonly=True),
                            TextInput(name="currency_id", label="Moneda", readonly=True),
                            MonetaryInput(name="amount_total", label="Total Pedido", readonly=True),
                        ]),
                    ]),

                    Notebook(tabs=["Líneas de la orden", "Otra información"], children=[
                        Container(layout="col", gap=0, padding=0, children=[
                            One2ManyLines(
                                name="order_line",
                                data_source="order_line",
                                comodel="sale.order.line",
                                inverse_name="order_id",
                                modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]},
                                columns=[
                                    {
                                        "field": "product_id",
                                        "label": "Producto",
                                        "type": "Many2OneLookup",
                                        "comodel": "product.product",
                                    },
                                    {
                                        "field": "product_uom_qty",
                                        "label": "Cantidad",
                                        "type": "NumberInput",
                                    },
                                    {
                                        "field": "price_unit",
                                        "label": "Precio unitario",
                                        "type": "NumberInput",
                                    },
                                    {
                                        "field": "name",
                                        "label": "Descripción",
                                        "type": "TextInput",
                                    },
                                    {
                                        "field": "price_subtotal",
                                        "label": "Importe",
                                        "type": "NumberInput",
                                        "readonly": True,
                                    },
                                ],
                            ),
                        ]),

                        Container(layout="col", gap=4, padding=4, children=[
                            Typography(content="Seguimiento", variant="h2", color="slate-800"),
                            SelectInput(
                                name="invoice_status",
                                label="Estado de Facturación",
                                readonly=True,
                                options=[
                                    ["upselling", "Oportunidad de Upselling"],
                                    ["invoiced", "Totalmente Facturado"],
                                    ["to invoice", "A Facturar"],
                                    ["no", "Nada que Facturar"],
                                ],
                            ),
                        ]),
                    ]),
                ]),

                Chatter(res_model="sale.order"),
            ],
        ).to_json()

        view_ast["id"] = self.id
        return view_ast