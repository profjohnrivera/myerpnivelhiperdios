# backend/app/core/abstract_models.py
from app.core.orm import Model, Field, SelectionField, RelationField, compute
from app.core.env import Context


def _default_company_id():
    """
    Resuelve la compañía por contexto activo.
    Nunca usar 1 fijo.
    """
    env = Context.get_env()
    if not env:
        return None

    # 1) Contexto explícito
    ctx_company = env.context.get("company_id") if getattr(env, "context", None) else None
    if ctx_company is not None:
        return ctx_company

    # 2) Usuario actual
    try:
        if env.user and env.user.company_id:
            return env.user.company_id.id if hasattr(env.user.company_id, "id") else env.user.company_id
    except Exception:
        pass

    return None


class AbstractDocument(Model):
    """
    📄 Plantilla Maestra para Cabeceras de Documentos
    """
    _abstract = True

    name = Field(type_="string", label="Referencia", default="Nuevo", readonly=True)

    state = SelectionField(
        options=[("draft", "Borrador"), ("done", "Completado"), ("cancel", "Cancelado")],
        default="draft",
        label="Estado",
    )

    company_id = RelationField(
        "res.company",
        label="Compañía",
        required=True,
        default=_default_company_id,
    )

    partner_id = RelationField("res.partner", label="Contacto", required=True)

    amount_total = Field(type_="float", label="Total", default=0.0, readonly=True)


class AbstractDocumentLine(Model):
    """
    📑 Plantilla Maestra para Líneas de Detalle.
    """
    _abstract = True

    sequence = Field(type_="int", default=10, label="Secuencia")

    display_type = SelectionField(
        options=[("line_section", "Sección"), ("line_note", "Nota")],
        default=None,
        label="Tipo de Visualización",
    )

    name = Field(type_="string", label="Descripción")
    product_id = RelationField("product.product", label="Producto")

    qty = Field(type_="float", default=1.0, label="Cantidad")
    price_unit = Field(type_="float", default=0.0, label="Precio Unitario")

    price_subtotal = Field(type_="float", label="Subtotal", default=0.0, readonly=True)

    @compute(depends=["qty", "price_unit", "display_type"])
    def _compute_subtotal(self):
        if self.display_type:
            self.price_subtotal = 0.0
        else:
            quantity = float(self.qty if self.qty is not None else 0.0)
            unit_price = float(self.price_unit if self.price_unit is not None else 0.0)
            self.price_subtotal = quantity * unit_price