# backend/modules/mod_products/models/__init__.py

from .product import ProductProduct
from .product_category import ProductCategory

__all__ = [
    "ProductProduct",
    "ProductCategory",
]