# backend/modules/mod_sales/data/menus.py

async def init_sales_menus(env):
    """
    🛒 MAPA DE NAVEGACIÓN: VENTAS
    Define cómo se verá la App de Ventas en el Dashboard.
    """
    Menu = env['ir.ui.menu']

    # 1. Menú Raíz (Categoría principal)
    # 🔥 CRÍTICO: is_category=True le dice a React que esto es un bloque principal
    # ⚡ FIX: Añadimos 'action': 'sale.order' para que el Dashboard sepa qué abrir
    cat_sales = await Menu.create({
        'name': 'VENTAS',
        'icon': 'ShoppingCart',
        'sequence': 10,
        'is_category': True,
        'action': 'sale.order'
    })

    # 2. Submenú de Pedidos
    await Menu.create({
        'name': 'Pedidos de Venta',
        'parent_id': cat_sales.id,
        'action': 'sale.order', # 💎 Debe ser el modelo exacto
        'sequence': 1,
        'icon': 'FileText'
    })

    # 3. Submenú de Categorías de Producto
    await Menu.create({
        'name': 'Cat. de Productos',
        'parent_id': cat_sales.id,
        'action': 'product.category', # 💎 Debe ser el modelo exacto
        'sequence': 2,
        'icon': 'Tags'
    })