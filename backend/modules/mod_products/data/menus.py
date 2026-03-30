# backend/modules/mod_products/data/menus.py

async def init_products_menus(env):
    """
    📦 MENÚS DE PRODUCTOS
    Fuente única de verdad: ir.ui.menu persistido.
    """
    Menu = env["ir.ui.menu"]

    cat_products = await Menu.create({
        "name": "PRODUCTOS",
        "icon": "Package",
        "sequence": 15,
        "is_category": True,
        "action": "product.product",
    })

    await Menu.create({
        "name": "Catálogo",
        "parent_id": cat_products.id,
        "action": "product.product",
        "sequence": 1,
        "icon": "PackageSearch",
    })

    await Menu.create({
        "name": "Categorías",
        "parent_id": cat_products.id,
        "action": "product.category",
        "sequence": 2,
        "icon": "Tags",
    })