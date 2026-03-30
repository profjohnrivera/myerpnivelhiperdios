# backend/app/core/abstract_models.py
# FIX: company_id required=False — el modelo concreto valida con @constrains.
# required=True aquí causaba ValueError cuando _default_company_id devuelve None
# (Graph de sesión sin usuario cargado en requests de frontend).
from app.core.orm import Model, Field, SelectionField, RelationField, compute
from app.core.env import Context


def _default_company_id():
    """
    Resolución síncrona de compañía.
    Pipeline:
    1. env.context['company_id'] — pasado explícitamente por el frontend
    2. Graph de sesión — si el usuario fue pre-cargado
    3. None — el modelo concreto resuelve con _resolve_company_async() antes de crear
    """
    env = Context.get_env()
    if not env:
        return None

    ctx_company = env.context.get("company_id") if getattr(env, "context", None) else None
    if ctx_company is not None:
        return ctx_company

    try:
        if env.user_id and str(env.user_id).isdigit():
            graph = getattr(env, "graph", None)
            if graph:
                node = ("res.users", int(env.user_id), "company_id")
                c = graph.get(node)
                if c:
                    return c
    except Exception:
        pass

    return None


class AbstractDocument(Model):
    """📄 Plantilla Maestra para Cabeceras de Documentos Comerciales."""
    _abstract = True

    name = Field(type_="string", label="Referencia", default="Nuevo", readonly=True)

    state = SelectionField(
        options=[
            ("draft",  "Borrador"),
            ("done",   "Completado"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        label="Estado",
    )

    # FIX: required=False — el modelo concreto (sale_order) valida con @constrains
    company_id = RelationField(
        "res.company",
        label="Compañía",
        required=False,
        default=_default_company_id,
    )

    partner_id = RelationField("res.partner", label="Contacto", required=True)
    amount_total = Field(type_="float", label="Total", default=0.0, readonly=True)


class AbstractDocumentLine(Model):
    """📑 Plantilla Maestra para Líneas de Detalle."""
    _abstract = True

    sequence = Field(type_="int", default=10, label="Secuencia")

    display_type = SelectionField(
        options=[
            ("line_section", "Sección"),
            ("line_note",    "Nota"),
        ],
        default=None,
        label="Tipo de Visualización",
    )

    name       = Field(type_="string", label="Descripción")
    product_id = RelationField("product.product", label="Producto")

    qty        = Field(type_="float", default=1.0, label="Cantidad")
    price_unit = Field(type_="float", default=0.0, label="Precio Unitario")

    price_subtotal = Field(type_="float", label="Subtotal", default=0.0, readonly=True)

    @compute(depends=["qty", "price_unit", "display_type"])
    def _compute_subtotal(self):
        if self.display_type:
            self.price_subtotal = 0.0
        else:
            qty   = float(self.qty        if self.qty        is not None else 0.0)
            price = float(self.price_unit if self.price_unit is not None else 0.0)
            self.price_subtotal = qty * price