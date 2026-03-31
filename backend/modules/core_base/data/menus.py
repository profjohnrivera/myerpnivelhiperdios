# backend/modules/core_base/data/menus.py

async def init_base_menus(env):
    """
    👥 MENÚS DE IDENTIDAD Y CONTACTOS
    Idempotentes por XML-ID.
    """
    loader = env.data

    cat_contacts = await loader.ensure_menu(
        "menu_contacts_root",
        {
            "name": "CONTACTOS",
            "icon": "BookOpen",
            "sequence": 20,
            "is_category": True,
        },
        lookup_domain=[("name", "=", "CONTACTOS"), ("is_category", "=", True)],
    )

    await loader.ensure_menu(
        "menu_contacts_directory",
        {
            "name": "Directorio",
            "icon": "Users",
            "parent_id": cat_contacts.id,
            "action": "res.partner",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Directorio"), ("parent_id", "=", cat_contacts.id)],
    )

    await loader.ensure_menu(
        "menu_contacts_companies",
        {
            "name": "Empresas",
            "icon": "Building",
            "parent_id": cat_contacts.id,
            "action": "res.company",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Empresas"), ("parent_id", "=", cat_contacts.id)],
    )