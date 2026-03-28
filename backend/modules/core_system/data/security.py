# backend/modules/core_system/data/security.py

async def init_base_security(env):
    """
    🛡️ AUTO-GENERADOR DE MATRIZ DE ACCESOS (HiperDios Security)
    Escanea todo el ADN del sistema y genera los permisos base.
    """
    print("   🛡️ [SEGURIDAD] Generando Matriz de Accesos Global...")
    
    ResGroups = env['res.groups']
    IrModel = env['ir.model']
    IrModelAccess = env['ir.model.access']

    # 1. Obtener el grupo administrador supremo
    admins = await ResGroups.search([('name', '=', 'Administración / Ajustes')])
    if not admins:
        admin_group = await ResGroups.create({
            'name': 'Administración / Ajustes',
            'description': 'Acceso total a la configuración técnica.'
        })
    else:
        admin_group = admins[0]

    # 2. Obtener ABSOLUTAMENTE TODOS los modelos registrados en el sistema
    all_models = await IrModel.search([])
    
    nuevos_permisos = 0
    # 3. Iterar e inyectar permisos masivamente
    for model in all_models:
        # Verificar si el permiso ya existe para no duplicarlo en cada reinicio
        existing = await IrModelAccess.search([
            ('model_id', '=', model.id),
            ('group_id', '=', admin_group.id)
        ])
        
        if not existing:
            await IrModelAccess.create({
                'name': f'Admin Access: {model.name or model.model}',
                'model_id': model.id,
                'group_id': admin_group.id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True
            })
            nuevos_permisos += 1
            
    print(f"      ✅ Matriz forjada: {nuevos_permisos} reglas de seguridad creadas.")