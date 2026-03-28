# backend/modules/mod_sales/models/product_category.py
from app.core.orm import Field
from app.core.tree import TreeModel

class ProductCategory(TreeModel):
    """
    ===========================================================================
    1. CATEGORÍAS DE PRODUCTO
    ===========================================================================
    """
    _name = 'product.category'
    _rec_name = 'name'
    _description = 'Categoría de Producto'
    
    name = Field(type_='string', label='Nombre de Categoría', required=True)