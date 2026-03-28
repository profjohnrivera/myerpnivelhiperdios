# backend/modules/mod_test/data/menus.py
async def init_test_menus(env):
    Menu = env['ir.ui.menu']

    cat_test = await Menu.create({
        'name': 'LABORATORIO',
        'icon': 'Beaker',
        'sequence': 50,
        'is_category': True
    })

    await Menu.create({
        'name': 'Registros de Prueba',
        'parent_id': cat_test.id,
        'action': 'test.record', 
        'sequence': 1,
        'icon': 'Database'
    })