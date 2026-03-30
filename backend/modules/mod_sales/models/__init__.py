# backend/modules/mod_sales/models/__init__.py

from .sale_order import SaleOrder
from .sale_order_line import SaleOrderLine

__all__ = [
    "SaleOrder",
    "SaleOrderLine",
]