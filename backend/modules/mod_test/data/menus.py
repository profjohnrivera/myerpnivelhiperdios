# backend/modules/mod_test/data/menus.py

async def init_test_menus(env):
    """
    🧪 MENÚS DEL LABORATORIO
    Idempotentes por XML-ID.
    """
    loader = env.data

    cat_test = await loader.ensure_menu(
        "menu_test_root",
        {
            "name": "LABORATORIO",
            "icon": "Beaker",
            "sequence": 50,
            "is_category": True,
        },
        lookup_domain=[("name", "=", "LABORATORIO"), ("is_category", "=", True)],
    )

    await loader.ensure_menu(
        "menu_test_records",
        {
            "name": "Registros de Prueba",
            "parent_id": cat_test.id,
            "action": "test.record",
            "sequence": 1,
            "icon": "Database",
        },
        lookup_domain=[("name", "=", "Registros de Prueba"), ("parent_id", "=", cat_test.id)],
    )

    await loader.ensure_menu(
        "menu_test_advanced_records",
        {
            "name": "Registros Avanzados",
            "parent_id": cat_test.id,
            "action": "test.advanced.record",
            "sequence": 2,
            "icon": "FlaskConical",
        },
        lookup_domain=[("name", "=", "Registros Avanzados"), ("parent_id", "=", cat_test.id)],
    )