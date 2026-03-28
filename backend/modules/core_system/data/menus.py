# backend/modules/core_system/data/menus.py

async def init_admin_menus(env):
    """
    ⚙️ EL GRAN MENÚ TÉCNICO (Odoo 20 Enterprise Style + HiperDios Core)
    Construye la jerarquía exacta solicitada para el control total del motor.
    """
    Menu = env['ir.ui.menu']
    print("   ⚙️ [MENÚ] Generando Menú Técnico Nivel Dios...")

    # ==========================================
    # 0. CATEGORÍA RAÍZ (Aparece en el Sidebar Principal)
    # ==========================================
    cat_admin = await Menu.create({
        'name': 'AJUSTES TÉCNICOS',
        'icon': 'Settings',
        'sequence': 100,
        'is_category': True
    })

    # ==========================================
    # 1. USUARIOS Y EMPRESAS
    # ==========================================
    m_users = await Menu.create({
        'name': 'Usuarios y empresas', 'parent_id': cat_admin.id, 'sequence': 10, 'icon': 'Users'
    })
    await Menu.create({'name': 'Usuarios', 'parent_id': m_users.id, 'action': 'res.users', 'sequence': 1})
    await Menu.create({'name': 'Grupos de acceso', 'parent_id': m_users.id, 'action': 'res.groups', 'sequence': 2})
    await Menu.create({'name': 'Empresas', 'parent_id': m_users.id, 'action': 'res.company', 'sequence': 3})

    # ==========================================
    # 2. SEGURIDAD Y PRIVACIDAD
    # ==========================================
    m_security = await Menu.create({
        'name': 'Seguridad', 'parent_id': cat_admin.id, 'sequence': 20, 'icon': 'ShieldCheck'
    })
    await Menu.create({'name': 'Permisos de acceso', 'parent_id': m_security.id, 'action': 'ir.model.access', 'sequence': 1})
    await Menu.create({'name': 'Reglas de registro (RLS)', 'parent_id': m_security.id, 'action': 'ir.rule', 'sequence': 2})

    # ==========================================
    # 3. INTERFAZ DE USUARIO
    # ==========================================
    m_ui = await Menu.create({
        'name': 'Interfaz de usuario', 'parent_id': cat_admin.id, 'sequence': 30, 'icon': 'LayoutTemplate'
    })
    await Menu.create({'name': 'Elementos de menú', 'parent_id': m_ui.id, 'action': 'ir.ui.menu', 'sequence': 1})
    await Menu.create({'name': 'Vistas (SDUI)', 'parent_id': m_ui.id, 'action': 'ir.ui.view', 'sequence': 2})

    # ==========================================
    # 4. ACCIONES
    # ==========================================
    m_actions = await Menu.create({
        'name': 'Acciones', 'parent_id': cat_admin.id, 'sequence': 40, 'icon': 'Zap'
    })
    await Menu.create({'name': 'Acciones de ventana', 'parent_id': m_actions.id, 'action': 'ir.actions.act_window', 'sequence': 1})
    await Menu.create({'name': 'Acciones del servidor', 'parent_id': m_actions.id, 'action': 'ir.actions.server', 'sequence': 2})

    # ==========================================
    # 5. ESTRUCTURA DE LA BASE DE DATOS
    # ==========================================
    m_db = await Menu.create({
        'name': 'Estructura de la base de datos', 'parent_id': cat_admin.id, 'sequence': 50, 'icon': 'Database'
    })
    await Menu.create({'name': 'Modelos', 'parent_id': m_db.id, 'action': 'ir.model', 'sequence': 1})
    await Menu.create({'name': 'Campos', 'parent_id': m_db.id, 'action': 'ir.model.fields', 'sequence': 2})
    await Menu.create({'name': 'Datos de modelo (XML ID)', 'parent_id': m_db.id, 'action': 'ir.model.data', 'sequence': 3})
    await Menu.create({'name': 'Registros de Auditoría', 'parent_id': m_db.id, 'action': 'ir.audit.log', 'sequence': 4})

    # ==========================================
    # 6. SECUENCIAS E IDENTIFICADORES
    # ==========================================
    m_seq = await Menu.create({
        'name': 'Secuencias e identificadores', 'parent_id': cat_admin.id, 'sequence': 60, 'icon': 'ListOrdered'
    })
    await Menu.create({'name': 'Secuencias', 'parent_id': m_seq.id, 'action': 'ir.sequence', 'sequence': 1})

    # ==========================================
    # 7. PARÁMETROS Y MÓDULOS
    # ==========================================
    m_params = await Menu.create({
        'name': 'Parámetros', 'parent_id': cat_admin.id, 'sequence': 70, 'icon': 'Sliders'
    })
    await Menu.create({'name': 'Parámetros del sistema', 'parent_id': m_params.id, 'action': 'ir.config_parameter', 'sequence': 1})
    
    m_mods = await Menu.create({
        'name': 'Aplicaciones / Módulos', 'parent_id': cat_admin.id, 'sequence': 80, 'icon': 'Package'
    })
    await Menu.create({'name': 'Módulos instalados', 'parent_id': m_mods.id, 'action': 'ir.module', 'sequence': 1})
    await Menu.create({'name': 'Dependencias', 'parent_id': m_mods.id, 'action': 'ir.module.dependency', 'sequence': 2})