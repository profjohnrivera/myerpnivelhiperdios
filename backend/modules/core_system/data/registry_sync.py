# backend/modules/core_system/data/registry_sync.py

from app.core.registry import Registry


async def sync_models_and_fields(env):
    """
    🧠 SINCRONIZADOR CONSTITUCIONAL DEL REGISTRY
    ---------------------------------------------------------
    Vuelca la arquitectura viva del Registry hacia:
      - ir.model
      - ir.model.fields

    P3-B:
    - usa technical_fields, no schema_fields
    - ir.model.fields representa catálogo técnico del modelo,
      no solo columnas físicas
    """
    print("   🧠 [SYNC] Volcando Arquitectura del Registry a la Base de Datos...")

    IrModel = env["ir.model"]
    IrModelFields = env["ir.model.fields"]

    from app.core.storage.postgres_storage import PostgresGraphStorage
    storage = PostgresGraphStorage()

    models_dict = Registry.get_all_models()

    modelos_creados = 0
    modelos_actualizados = 0
    campos_creados = 0
    campos_actualizados = 0

    model_records = {}

    # =========================================================
    # FASE 1: SINCRONIZAR MODELOS
    # =========================================================
    for tech_name, model_class in models_dict.items():
        human_name = (
            getattr(model_class, "_description", None)
            or getattr(model_class, "__name__", None)
            or tech_name
        )

        owner_module = None
        try:
            owner_module = Registry.get_model_owner(tech_name)
        except Exception:
            owner_module = None

        values = {
            "name": str(human_name)[:255],
            "model": tech_name,
            "state": "base",
            "module": owner_module,
            "transient": bool(getattr(model_class, "_transient", False)),
            "abstract": bool(getattr(model_class, "_abstract", False)),
            "active": True,
        }

        existing = await IrModel.search([("model", "=", tech_name)], limit=1)

        if existing:
            rec = existing[0]
            await rec.write(values)
            modelos_actualizados += 1
        else:
            rec = await IrModel.create(values)
            modelos_creados += 1

        model_records[tech_name] = rec

    # =========================================================
    # FASE 2: SINCRONIZAR CAMPOS TÉCNICOS
    # =========================================================
    for tech_name, model_class in models_dict.items():
        model_rec = model_records.get(tech_name)
        if not model_rec:
            print(f"   ⚠️ [SYNC] No se pudo resolver record técnico para: {tech_name}")
            continue

        model_id = model_rec.id
        fields_meta = Registry.get_technical_fields_for_model(tech_name) or {}

        for field_name, meta in fields_meta.items():
            label = meta.get("label") or meta.get("string") or field_name
            ttype = meta.get("type") or meta.get("ttype") or "string"
            relation = meta.get("relation") or meta.get("target") or ""

            values = {
                "name": field_name,
                "field_description": str(label)[:255],
                "model": tech_name,
                "model_id": model_id,
                "ttype": ttype,
                "relation": relation,
                "required": bool(meta.get("required", False)),
                "readonly": bool(meta.get("readonly", False)),
                "index": bool(meta.get("index", False)),
                "store": bool(meta.get("store", True)),
                "translate": bool(meta.get("translate", False)),
                "active": True,
            }

            existing_field = await IrModelFields.search([
                ("model", "=", tech_name),
                ("name", "=", field_name),
            ], limit=1)

            if existing_field:
                await existing_field[0].write(values)
                campos_actualizados += 1
            else:
                await IrModelFields.create(values)
                campos_creados += 1

    # =========================================================
    # FASE 3: PERSISTENCIA FINAL ÚNICA
    # =========================================================
    await storage.save(env.graph)

    print(
        "      ✅ Sincronización completa: "
        f"{modelos_creados} modelos creados, "
        f"{modelos_actualizados} modelos actualizados, "
        f"{campos_creados} campos creados, "
        f"{campos_actualizados} campos actualizados."
    )