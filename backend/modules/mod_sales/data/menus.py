# backend/modules/mod_sales/data/menus.py

async def init_sales_menus(env):
    """
    🛒 MENÚS DE VENTAS
    Idempotentes por XML-ID.
    """
    loader = env.data

    cat_sales = await loader.ensure_menu(
        "menu_sales_root",
        {
            "name": "VENTAS",
            "icon": "ShoppingCart",
            "sequence": 10,
            "is_category": True,
            "action": "sale.order",
        },
        lookup_domain=[("name", "=", "VENTAS"), ("is_category", "=", True)],
    )

    await loader.ensure_menu(
        "menu_sales_orders",
        {
            "name": "Pedidos de Venta",
            "parent_id": cat_sales.id,
            "action": "sale.order",
            "sequence": 1,
            "icon": "FileText",
        },
        lookup_domain=[("name", "=", "Pedidos de Venta"), ("parent_id", "=", cat_sales.id)],
    )