# backend/modules/mod_products/data/menus.py

async def init_products_menus(env):
    """
    📦 MENÚS DE PRODUCTOS
    Idempotentes por XML-ID.
    """
    loader = env.data

    cat_products = await loader.ensure_menu(
        "menu_products_root",
        {
            "name": "PRODUCTOS",
            "icon": "Package",
            "sequence": 15,
            "is_category": True,
            "action": "product.product",
        },
        lookup_domain=[("name", "=", "PRODUCTOS"), ("is_category", "=", True)],
    )

    await loader.ensure_menu(
        "menu_products_catalog",
        {
            "name": "Catálogo",
            "parent_id": cat_products.id,
            "action": "product.product",
            "sequence": 1,
            "icon": "PackageSearch",
        },
        lookup_domain=[("name", "=", "Catálogo"), ("parent_id", "=", cat_products.id)],
    )

    await loader.ensure_menu(
        "menu_products_categories",
        {
            "name": "Categorías",
            "parent_id": cat_products.id,
            "action": "product.category",
            "sequence": 2,
            "icon": "Tags",
        },
        lookup_domain=[("name", "=", "Categorías"), ("parent_id", "=", cat_products.id)],
    )