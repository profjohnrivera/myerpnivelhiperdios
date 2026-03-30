# backend/modules/mod_products/models/product_category.py

from app.core.orm import Field
from app.core.tree import TreeModel


class ProductCategory(TreeModel):
    """
    🌳 CATEGORÍAS DE PRODUCTO

    Frontera correcta de dominio:
    - pertenece a Productos
    - NO pertenece a Ventas
    """
    _name = "product.category"
    _rec_name = "name"
    _description = "Categoría de Producto"

    name = Field(type_="string", label="Nombre de Categoría", required=True)