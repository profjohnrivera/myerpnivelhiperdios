# backend/modules/mod_sales/views/sale_order_views.py
from app.core.sdui import Component, Container, HeaderBar, ModelStatusBar, Card, Group, Many2OneLookup, Notebook, One2ManyLines, ModelActions, Chatter, DateInput, Typography, MonetaryInput, TextInput

class SaleOrderFormView(Component):
    """🎨 VISTA EXPLÍCITA PARA PEDIDOS DE VENTA (Replica Geométrica Odoo 20)"""
    def __init__(self):
        self.id = "sale.order.form"
    
    def compile(self) -> dict:
        view_ast = Container(layout="col", gap=0, padding=0, border=False, children=[
            HeaderBar(children=[
                ModelActions("sale.order"), 
                ModelStatusBar("sale.order", options=[
                    {"value": "draft", "label": "Cotización", "color": "info"},
                    {"value": "sent", "label": "Cotización Enviada", "color": "info"},
                    {"value": "sale", "label": "Orden de Venta", "color": "success"},
                    {"value": "done", "label": "Completado", "color": "success"},
                    {"value": "cancel", "label": "Cancelado", "color": "danger"}
                ])
            ]),
            Card(children=[
                # ⚡ TÍTULO GIGANTE S00003
                Container(layout="col", gap=0, padding=0, children=[
                    TextInput(name="name", label="", readonly=True) 
                ]),

                # ⚡ CABECERA: Layout Odoo (Cliente Izquierda, 3 campos Derecha)
                Group(columns=2, children=[
                    # Izquierda
                    Container(layout="col", gap=2, padding=0, children=[
                        Many2OneLookup(
                            name="partner_id", 
                            label="Cliente", 
                            comodel="res.partner", 
                            placeholder="",
                            modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]}
                        )
                    ]),
                    # Derecha
                    Container(layout="col", gap=1, padding=0, children=[
                        DateInput(name="create_date", label="Vencimiento", readonly=True),
                        Many2OneLookup(name="sale_order_template_id", label="Lista de precios", comodel="sale.order.template"),
                        Many2OneLookup(name="user_id", label="Términos de pago", comodel="res.users"),
                    ])
                ]),

                # ⚡ PESTAÑAS Y TABLA
                Notebook(tabs=["Líneas de la orden", "Otra información"], children=[
                    Container(layout="col", gap=0, padding=0, children=[
                        # TABLA DE LÍNEAS
                        One2ManyLines(
                            name="order_line", 
                            comodel="sale.order.line",
                            modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]},
                            columns=[
                                {"field": "product_id", "label": "Producto", "type": "Many2OneLookup", "comodel": "product.product"},
                                {"field": "product_uom_qty", "label": "Cantidad", "type": "NumberInput"},
                                {"field": "price_unit", "label": "Precio unitario", "type": "MonetaryInput"},
                                {"field": "name", "label": "Impuestos", "type": "TextInput", "readonly": True}, # Placeholder para Odoo UI
                                {"field": "price_subtotal", "label": "Importe", "type": "MonetaryInput", "readonly": True}
                            ]
                        ),
                        
                        # ⚡ ZONA INFERIOR: TÉRMINOS Y TOTALES ESTRANGULADOS
                        Container(layout="row", justify="between", align="start", padding=4, children=[
                            # Izquierda: Términos (Alineado a la izquierda, ocupa la mitad)
                            Container(layout="col", gap=2, padding=0, children=[
                                TextInput(
                                    name="note", 
                                    label="", 
                                    placeholder="Términos y condiciones...",
                                    modifiers={"readonly": [["state", "in", ["sale", "done", "cancel"]]]}
                                )
                            ]),
                            # Derecha: Bloque compacto para Subtotal y Total (Alineado al extremo derecho)
                            Container(layout="col", align="end", gap=1, padding=0, children=[
                                Group(columns=1, children=[
                                    MonetaryInput(name="amount_total", label="Subtotal:", readonly=True),
                                    MonetaryInput(name="amount_total", label="Total:", readonly=True)
                                ])
                            ])
                        ])
                    ]),
                    
                    # Pestaña 2
                    Container(layout="col", gap=4, padding=4, children=[
                        Typography(content="Configuración", variant="h2", color="slate-800"),
                        Many2OneLookup(name="company_id", label="Empresa", comodel="res.company")
                    ])
                ])
            ]),
            Chatter(res_model="sale.order")
        ]).to_json()
        
        view_ast['id'] = self.id
        return view_ast