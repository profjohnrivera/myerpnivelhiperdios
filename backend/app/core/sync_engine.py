# backend/app/core/sync_engine.py
from app.core.registry import Registry
from app.core.storage.postgres_storage import PostgresGraphStorage
from modules.core_system.models import IrModel, IrModelFields
import logging

logger = logging.getLogger("SyncEngine")

class SchemaSynchronizer:
    """
    🔄 MOTOR DE INTROSPECCIÓN (REFLEXIÓN)
    Sincroniza la estructura de clases Python con el Diccionario de Datos (ir.*)
    y materializa las tablas físicas en la base de datos.
    """
    
    @staticmethod
    async def sync_all():
        print("\n🧠 CEREBRO: Iniciando auto-análisis (Introspección)...")
        storage = PostgresGraphStorage()
        
        # 💎 PASO 1: Sincronización Física (Materialización)
        # Esto crea las tablas res_partner, sale_order, etc. en Postgres
        # basándose en lo que hay en el Registry.
        await storage.sync_schema() 
        
        # 2. Obtenemos la lista de modelos desde el Registry
        models = Registry.get_all_models()
        
        total_models = 0
        total_fields = 0

        for tech_name, model_cls in models.items():
            # Saltamos modelos base para evitar recursión en el arranque
            if tech_name in ['ir.model', 'ir.model.fields']:
                continue

            # --- FASE 1: Sincronizar MODELO (ir.model) ---
            # Buscamos si el modelo ya existe en el diccionario de datos
            existing_model_ids = await storage.search_by_field('ir.model', 'model', tech_name)
            
            if not existing_model_ids:
                description = model_cls.__doc__.strip().split('\n')[0] if model_cls.__doc__ else tech_name
                print(f"   ✨ Aprendiendo concepto: {tech_name}")
                
                ir_model = await IrModel.create({
                    "name": description,
                    "model": tech_name,
                    "state": "base",
                    # Guardamos el campo de representación (rec_name)
                    "info": getattr(model_cls, '_rec_name', 'name') 
                })
                # Guardado inmediato para asegurar ID relacional
                await storage.save(ir_model.graph, model_filter='ir.model')
                ir_model_id = ir_model.id
                total_models += 1
            else:
                ir_model_id = existing_model_ids[0]

            # --- FASE 2: Sincronizar CAMPOS (ir.model.fields) ---
            fields_meta = Registry.get_fields_for_model(tech_name)
            
            for field_name, meta in fields_meta.items():
                # 🔥 BUSQUEDA QUIRÚRGICA:
                # Buscamos campos que pertenezcan a ESTE modelo específico
                # Para evitar conflictos entre modelos con campos de igual nombre.
                fields_of_model = await IrModelFields.search([
                    ('model_id', '=', ir_model_id),
                    ('name', '=', field_name)
                ])

                if not fields_of_model:
                    await IrModelFields.create({
                        "model_id": ir_model_id,
                        "name": field_name,
                        "field_description": meta.get('label', field_name),
                        "ttype": meta.get('type', 'string'),
                        "required": meta.get('required', False),
                        "readonly": meta.get('readonly', False),
                        "index": meta.get('index', False),
                        "relation": meta.get('target', '')
                    })
                    total_fields += 1

        # 3. Persistencia de metadatos
        if total_fields > 0 or total_models > 0:
            dummy = IrModel() 
            await storage.save(dummy.graph)

        print(f"✅ CONCIENCIA EXPANDIDA: {total_models} Modelos nuevos, {total_fields} Campos indexados.")
        print("🚀 El esquema físico y lógico está sincronizado.\n")