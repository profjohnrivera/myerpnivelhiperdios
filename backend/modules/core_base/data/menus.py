# backend/modules/core_base/data/menus.py
async def init_base_menus(env):
    """
    👥 MENÚS DE IDENTIDAD Y CONTACTOS
    Solo modelos res.* (Partners, Companies, Users)
    """
    Menu = env['ir.ui.menu']

    # ==========================================
    # 📖 APLICACIÓN: CONTACTOS
    # ==========================================
    cat_contacts = await Menu.create({
        'name': 'CONTACTOS',
        'icon': 'BookOpen',
        'sequence': 20,
        'is_category': True
    })

    await Menu.create({
        'name': 'Directorio',
        'icon': 'Users',
        'parent_id': cat_contacts.id,
        'action': 'res.partner', 
        'sequence': 1
    })

    await Menu.create({
        'name': 'Empresas',
        'icon': 'Building',
        'parent_id': cat_contacts.id,
        'action': 'res.company', 
        'sequence': 2
    })

    # ==========================================
    # ⚙️ INYECCIÓN EN ADMINISTRACIÓN
    # ==========================================
    # core_base busca el menú 'ADMINISTRACIÓN' que core_system creó momentos antes.
    admin_menus = await Menu.search([('name', '=', 'ADMINISTRACIÓN')])
    
    if admin_menus:
        # Inyectamos nuestro modelo 'res.users' en la casa del padre
        await Menu.create({
            'name': 'Usuarios del Sistema',
            'icon': 'UserCheck',
            'parent_id': admin_menus[0].id,
            'action': 'res.users',
            'sequence': 10
        })