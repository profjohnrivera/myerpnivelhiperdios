# backend/modules/mod_products/models/product.py

from app.core.orm import Model, Field, SelectionField, RelationField


class ProductProduct(Model):
    """
    📦 CATÁLOGO MAESTRO DE PRODUCTOS

    Ownership correcto:
    - pertenece a mod_products
    - lo consumen ventas, compras, inventario, etc.
    """
    _name = "product.product"
    _rec_name = "name"
    _description = "Producto"

    name = Field(type_="string", label="Nombre del Producto", required=True)

    type = SelectionField(
        options=[
            ("product", "Almacenable"),
            ("consu", "Consumible"),
            ("service", "Servicio"),
        ],
        default="product",
        label="Tipo de Producto",
    )

    category_id = RelationField(
        "product.category",
        label="Categoría",
    )

    list_price = Field(type_="float", default=1.0, label="Precio de Venta")
    standard_price = Field(type_="float", default=0.0, label="Costo")
    default_code = Field(type_="string", label="Referencia Interna (SKU)")
    barcode = Field(type_="string", label="Código de Barras")

    active = Field(type_="bool", default=True, label="Activo")