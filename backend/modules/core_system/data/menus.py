# backend/modules/core_system/data/menus.py

async def init_admin_menus(env):
    """
    ⚙️ MENÚ TÉCNICO
    Ahora cargado por XML-ID estable, no por create() ciego.
    """
    loader = env.data

    cat_admin = await loader.ensure_menu(
        "menu_technical_root",
        {
            "name": "AJUSTES TÉCNICOS",
            "icon": "Settings",
            "sequence": 100,
            "is_category": True,
        },
        lookup_domain=[("name", "=", "AJUSTES TÉCNICOS"), ("is_category", "=", True)],
    )

    m_users = await loader.ensure_menu(
        "menu_technical_users_root",
        {
            "name": "Usuarios y empresas",
            "parent_id": cat_admin.id,
            "sequence": 10,
            "icon": "Users",
        },
        lookup_domain=[("name", "=", "Usuarios y empresas"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_users",
        {
            "name": "Usuarios",
            "parent_id": m_users.id,
            "action": "res.users",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Usuarios"), ("parent_id", "=", m_users.id)],
    )
    await loader.ensure_menu(
        "menu_technical_groups",
        {
            "name": "Grupos de acceso",
            "parent_id": m_users.id,
            "action": "res.groups",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Grupos de acceso"), ("parent_id", "=", m_users.id)],
    )
    await loader.ensure_menu(
        "menu_technical_companies",
        {
            "name": "Empresas",
            "parent_id": m_users.id,
            "action": "res.company",
            "sequence": 3,
        },
        lookup_domain=[("name", "=", "Empresas"), ("parent_id", "=", m_users.id)],
    )

    m_security = await loader.ensure_menu(
        "menu_technical_security_root",
        {
            "name": "Seguridad",
            "parent_id": cat_admin.id,
            "sequence": 20,
            "icon": "ShieldCheck",
        },
        lookup_domain=[("name", "=", "Seguridad"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_model_access",
        {
            "name": "Permisos de acceso",
            "parent_id": m_security.id,
            "action": "ir.model.access",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Permisos de acceso"), ("parent_id", "=", m_security.id)],
    )
    await loader.ensure_menu(
        "menu_technical_rules",
        {
            "name": "Reglas de registro (RLS)",
            "parent_id": m_security.id,
            "action": "ir.rule",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Reglas de registro (RLS)"), ("parent_id", "=", m_security.id)],
    )

    m_ui = await loader.ensure_menu(
        "menu_technical_ui_root",
        {
            "name": "Interfaz de usuario",
            "parent_id": cat_admin.id,
            "sequence": 30,
            "icon": "LayoutTemplate",
        },
        lookup_domain=[("name", "=", "Interfaz de usuario"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_ui_menus",
        {
            "name": "Elementos de menú",
            "parent_id": m_ui.id,
            "action": "ir.ui.menu",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Elementos de menú"), ("parent_id", "=", m_ui.id)],
    )
    await loader.ensure_menu(
        "menu_technical_ui_views",
        {
            "name": "Vistas (SDUI)",
            "parent_id": m_ui.id,
            "action": "ir.ui.view",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Vistas (SDUI)"), ("parent_id", "=", m_ui.id)],
    )

    m_actions = await loader.ensure_menu(
        "menu_technical_actions_root",
        {
            "name": "Acciones",
            "parent_id": cat_admin.id,
            "sequence": 40,
            "icon": "Zap",
        },
        lookup_domain=[("name", "=", "Acciones"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_actions_window",
        {
            "name": "Acciones de ventana",
            "parent_id": m_actions.id,
            "action": "ir.actions.act_window",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Acciones de ventana"), ("parent_id", "=", m_actions.id)],
    )
    await loader.ensure_menu(
        "menu_technical_actions_server",
        {
            "name": "Acciones del servidor",
            "parent_id": m_actions.id,
            "action": "ir.actions.server",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Acciones del servidor"), ("parent_id", "=", m_actions.id)],
    )

    m_db = await loader.ensure_menu(
        "menu_technical_db_root",
        {
            "name": "Estructura de la base de datos",
            "parent_id": cat_admin.id,
            "sequence": 50,
            "icon": "Database",
        },
        lookup_domain=[("name", "=", "Estructura de la base de datos"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_models",
        {
            "name": "Modelos",
            "parent_id": m_db.id,
            "action": "ir.model",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Modelos"), ("parent_id", "=", m_db.id)],
    )
    await loader.ensure_menu(
        "menu_technical_fields",
        {
            "name": "Campos",
            "parent_id": m_db.id,
            "action": "ir.model.fields",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Campos"), ("parent_id", "=", m_db.id)],
    )
    await loader.ensure_menu(
        "menu_technical_xmlids",
        {
            "name": "Datos de modelo (XML ID)",
            "parent_id": m_db.id,
            "action": "ir.model.data",
            "sequence": 3,
        },
        lookup_domain=[("name", "=", "Datos de modelo (XML ID)"), ("parent_id", "=", m_db.id)],
    )
    await loader.ensure_menu(
        "menu_technical_audit",
        {
            "name": "Registros de Auditoría",
            "parent_id": m_db.id,
            "action": "ir.audit.log",
            "sequence": 4,
        },
        lookup_domain=[("name", "=", "Registros de Auditoría"), ("parent_id", "=", m_db.id)],
    )

    m_seq = await loader.ensure_menu(
        "menu_technical_sequences_root",
        {
            "name": "Secuencias e identificadores",
            "parent_id": cat_admin.id,
            "sequence": 60,
            "icon": "ListOrdered",
        },
        lookup_domain=[("name", "=", "Secuencias e identificadores"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_sequences",
        {
            "name": "Secuencias",
            "parent_id": m_seq.id,
            "action": "ir.sequence",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Secuencias"), ("parent_id", "=", m_seq.id)],
    )

    m_params = await loader.ensure_menu(
        "menu_technical_params_root",
        {
            "name": "Parámetros",
            "parent_id": cat_admin.id,
            "sequence": 70,
            "icon": "Sliders",
        },
        lookup_domain=[("name", "=", "Parámetros"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_system_params",
        {
            "name": "Parámetros del sistema",
            "parent_id": m_params.id,
            "action": "ir.config_parameter",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Parámetros del sistema"), ("parent_id", "=", m_params.id)],
    )

    m_mods = await loader.ensure_menu(
        "menu_technical_modules_root",
        {
            "name": "Aplicaciones / Módulos",
            "parent_id": cat_admin.id,
            "sequence": 80,
            "icon": "Package",
        },
        lookup_domain=[("name", "=", "Aplicaciones / Módulos"), ("parent_id", "=", cat_admin.id)],
    )
    await loader.ensure_menu(
        "menu_technical_modules",
        {
            "name": "Módulos instalados",
            "parent_id": m_mods.id,
            "action": "ir.module",
            "sequence": 1,
        },
        lookup_domain=[("name", "=", "Módulos instalados"), ("parent_id", "=", m_mods.id)],
    )
    await loader.ensure_menu(
        "menu_technical_module_dependencies",
        {
            "name": "Dependencias",
            "parent_id": m_mods.id,
            "action": "ir.module.dependency",
            "sequence": 2,
        },
        lookup_domain=[("name", "=", "Dependencias"), ("parent_id", "=", m_mods.id)],
    )