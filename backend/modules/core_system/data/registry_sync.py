# backend/modules/core_system/data/registry_sync.py
from app.core.registry import Registry

async def sync_models_and_fields(env):
    """
    🧠 SINCRONIZADOR DEL KERNEL (RAM -> DB)
    Estricto estándar Odoo 20: 2 Fases seguras (Modelos -> Guardado -> Campos)
    """
    print("   🧠 [SYNC] Volcando Arquitectura del Registry a la Base de Datos...")
    
    IrModel = env['ir.model']
    IrModelFields = env['ir.model.fields']
    from app.core.storage.postgres_storage import PostgresGraphStorage
    storage = PostgresGraphStorage()

    models_dict = Registry.get_all_models()
    modelos_creados = 0
    campos_creados = 0

    # --- FASE 1: Registro de Modelos ---
    for tech_name, model_class in models_dict.items():
        if hasattr(model_class, '_description') and model_class._description:
            human_name = model_class._description
        else:
            human_name = model_class.__name__
        
        existing_model = await IrModel.search([('model', '=', tech_name)])
        if not existing_model:
            await IrModel.create({
                'name': human_name[:50], 
                'model': tech_name,
                'state': 'base'
            })
            modelos_creados += 1
        else:
            await IrModel.write([existing_model[0].id], {'name': human_name[:50]})

    # 💎 Guardamos a disco ANTES de buscar campos. 
    # Esto materializa los IDs (convierte new_... en BIGSERIAL real)
    await storage.save(env.graph)

    # --- FASE 2: Registro de Campos ---
    for tech_name, model_class in models_dict.items():
        existing_model = await IrModel.search([('model', '=', tech_name)])
        if not existing_model: continue
        
        # El ID ya es numérico, no fallará.
        model_id = existing_model[0].id
        fields_meta = Registry.get_fields_for_model(tech_name)
        
        for f_name, f_meta in fields_meta.items():
            existing_field = await IrModelFields.search([
                ('name', '=', f_name), 
                ('model_id', '=', model_id)
            ])
            
            if not existing_field:
                await IrModelFields.create({
                    'name': f_name,
                    'field_description': f_meta.get('label', f_name)[:50],
                    'model_id': model_id,
                    'ttype': f_meta.get('type', 'string'),
                    'state': 'base'
                })
                campos_creados += 1

    print(f"      ✅ Sincronización completa: {modelos_creados} Modelos y {campos_creados} Campos estandarizados en BD.")