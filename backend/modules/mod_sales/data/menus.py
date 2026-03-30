# backend/modules/mod_sales/data/menus.py

async def init_sales_menus(env):
    """
    🛒 MENÚS DE VENTAS
    Solo navegación propia de ventas.
    """
    Menu = env["ir.ui.menu"]

    cat_sales = await Menu.create({
        "name": "VENTAS",
        "icon": "ShoppingCart",
        "sequence": 10,
        "is_category": True,
        "action": "sale.order",
    })

    await Menu.create({
        "name": "Pedidos de Venta",
        "parent_id": cat_sales.id,
        "action": "sale.order",
        "sequence": 1,
        "icon": "FileText",
    })