# backend/modules/mod_sales/models/sale_order_line.py

from app.core.orm import Field, SelectionField, RelationField, compute, onchange
from app.core.abstract_models import AbstractDocumentLine
from app.core.registry import Registry


class SaleOrderLine(AbstractDocumentLine):
    """
    Línea de pedido de venta.

    Enfoque endurecido:
    - sin SQL directo en lógica de negocio
    - ORM/Registry como fuente de verdad
    - cálculos consistentes y seguros
    - sin romper el flujo actual que ya funciona
    """
    _name = "sale.order.line"
    _rec_name = "name"
    _description = "Línea de Pedido de Venta"

    order_id = RelationField("sale.order", label="Pedido", required=True, ondelete="cascade")
    product_id = RelationField("product.product", label="Producto")

    product_uom_qty = Field(type_="float", default=1.0, label="Cantidad")
    price_unit = Field(type_="float", default=0.0, label="Precio Unitario")
    price_subtotal = Field(type_="float", default=0.0, readonly=True, label="Subtotal")
    display_type = Field(type_="string", default=None)

    qty_delivered = Field(type_="float", default=0.0, label="Cantidad Entregada")
    qty_invoiced = Field(type_="float", default=0.0, label="Cantidad Facturada")
    qty_to_invoice = Field(type_="float", default=0.0, label="A Facturar", readonly=True)

    invoice_status = SelectionField(
        options=[
            ("upselling", "Oportunidad de Upselling"),
            ("invoiced", "Totalmente Facturado"),
            ("to invoice", "A Facturar"),
            ("no", "Nada que Facturar"),
        ],
        default="no",
        label="Estado de Facturación",
    )

    # =========================================================================
    # HELPERS
    # =========================================================================
    @staticmethod
    async def _get_product_record(product_value):
        if not product_value:
            return None

        product_id = product_value.id if hasattr(product_value, "id") else product_value
        if not str(product_id).isdigit():
            return None

        ProductModel = Registry.get_model("product.product")
        if not ProductModel:
            return None

        rs = await ProductModel.search([("id", "=", int(product_id))])
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        return rs[0] if rs and len(rs) > 0 else None

    @staticmethod
    async def _get_order_record(order_value):
        if not order_value:
            return None

        order_id = order_value.id if hasattr(order_value, "id") else order_value
        if not str(order_id).isdigit():
            return None

        OrderModel = Registry.get_model("sale.order")
        if not OrderModel:
            return None

        rs = await OrderModel.search([("id", "=", int(order_id))])
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        return rs[0] if rs and len(rs) > 0 else None

    def _recompute_subtotal_now(self):
        if getattr(self, "display_type", None):
            self.price_subtotal = 0.0
            return

        qty = float(getattr(self, "product_uom_qty", 0.0) or 0.0)
        price = float(getattr(self, "price_unit", 0.0) or 0.0)
        self.price_subtotal = qty * price

    # =========================================================================
    # ONCHANGE
    # =========================================================================
    @onchange("product_id")
    async def _onchange_product_id(self):
        if not getattr(self, "product_id", None):
            return

        try:
            product = await self._get_product_record(self.product_id)
            if not product:
                return

            product_name = getattr(product, "display_name", None) or getattr(product, "name", None) or "Producto"
            list_price = float(getattr(product, "list_price", 0.0) or 0.0)

            self.name = product_name
            self.price_unit = list_price
            self._recompute_subtotal_now()
        except Exception as e:
            print(f"⚠️ [ONCHANGE ERROR] Fallo al cargar precio del producto: {e}")

    @onchange("product_uom_qty", "price_unit", "display_type")
    def _onchange_quantity_or_price(self):
        self._recompute_subtotal_now()

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @compute(depends=["product_uom_qty", "price_unit", "display_type"])
    def _compute_subtotal(self):
        self._recompute_subtotal_now()

    @compute(depends=["product_uom_qty", "qty_invoiced", "display_type"])
    def _compute_qty_to_invoice(self):
        if getattr(self, "display_type", None):
            self.qty_to_invoice = 0.0
            return

        qty = float(getattr(self, "product_uom_qty", 1.0) or 1.0)
        qty_invoiced = float(getattr(self, "qty_invoiced", 0.0) or 0.0)
        self.qty_to_invoice = max(0.0, qty - qty_invoiced)

    @compute(depends=["product_uom_qty", "qty_delivered", "qty_to_invoice", "qty_invoiced", "display_type", "order_id"])
    async def _compute_invoice_status(self):
        if getattr(self, "display_type", None):
            self.invoice_status = "no"
            return

        order_state = None
        try:
            order = await self._get_order_record(getattr(self, "order_id", None))
            order_state = getattr(order, "state", None) if order else None
        except Exception:
            order_state = None

        if order_state not in ["sale", "done"]:
            self.invoice_status = "no"
            return

        qty = float(getattr(self, "product_uom_qty", 1.0) or 1.0)
        qty_delivered = float(getattr(self, "qty_delivered", 0.0) or 0.0)
        qty_invoiced = float(getattr(self, "qty_invoiced", 0.0) or 0.0)
        qty_to_invoice = float(getattr(self, "qty_to_invoice", 0.0) or 0.0)

        if qty_to_invoice > 0:
            self.invoice_status = "to invoice"
        elif qty_invoiced >= qty and qty > 0:
            self.invoice_status = "invoiced"
        elif qty_delivered > qty:
            self.invoice_status = "upselling"
        else:
            self.invoice_status = "no"