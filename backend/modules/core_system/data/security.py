# backend/modules/core_system/data/security.py
# ============================================================
# SEGURIDAD ENTERPRISE — ARQUITECTURA DEFINITIVA
#
# CIERRE DEL TEMA ADMIN:
# - La única verdad para admin es res.groups.is_system_admin = TRUE
# - Este bootstrap converge datos legacy al nuevo criterio
# - Nunca deja el sistema dependiendo del nombre visible del grupo
#   como criterio final de seguridad
# ============================================================


async def _exec(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, "acquire"):
        async with pool_or_conn.acquire() as conn:
            return await conn.execute(query, *args)
    return await pool_or_conn.execute(query, *args)


async def _fetch(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, "acquire"):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetch(query, *args)
    return await pool_or_conn.fetch(query, *args)


async def _fetchrow(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, "acquire"):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetchrow(query, *args)
    return await pool_or_conn.fetchrow(query, *args)


async def _fetchval(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, "acquire"):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetchval(query, *args)
    return await pool_or_conn.fetchval(query, *args)


async def _ensure_admin_group(storage, now):
    """
    Garantiza que exista un único grupo admin técnico y que quede
    normalizado con is_system_admin = TRUE.

    Estrategia:
    1. Buscar por flag técnico
    2. Fallback de migración por nombre
    3. Crear si no existe
    4. Reparar siempre el flag a TRUE
    """
    admin_group_id = None

    # 1) Buscar por criterio correcto
    try:
        admin_group_id = await _fetchval(
            storage,
            'SELECT id FROM "res_groups" WHERE is_system_admin = TRUE ORDER BY id LIMIT 1',
        )
    except Exception:
        # Columna faltante en una BD desfasada
        admin_group_id = None

    # 2) Fallback de migración por nombre visible
    if not admin_group_id:
        try:
            admin_group_id = await _fetchval(
                storage,
                'SELECT id FROM "res_groups" WHERE name = $1 ORDER BY id LIMIT 1',
                "Administración / Ajustes",
            )
        except Exception:
            admin_group_id = None

    # 3) Crear si no existe
    if not admin_group_id:
        try:
            admin_group_id = await _fetchval(
                storage,
                """
                INSERT INTO "res_groups"
                    (name, description, is_system_admin, active, write_version, create_date, write_date)
                VALUES ($1, $2, TRUE, TRUE, 1, $3, $3)
                RETURNING id
                """,
                "Administración / Ajustes",
                "Acceso total al sistema. Bypass de ACL y RLS.",
                now,
            )
        except Exception:
            # Compatibilidad defensiva si la columna aún no existe
            admin_group_id = await _fetchval(
                storage,
                """
                INSERT INTO "res_groups"
                    (name, description, active, write_version, create_date, write_date)
                VALUES ($1, $2, TRUE, 1, $3, $3)
                RETURNING id
                """,
                "Administración / Ajustes",
                "Acceso total al sistema. Bypass de ACL y RLS.",
                now,
            )
        print("   ✨ [SEGURIDAD] Grupo Administrador creado.")

    # 4) Reparación convergente: si existe, lo normalizamos
    try:
        await _exec(
            storage,
            """
            UPDATE "res_groups"
            SET is_system_admin = TRUE
            WHERE id = $1
            """,
            admin_group_id,
        )
    except Exception:
        # Si la columna aún no existe, no bloqueamos el boot
        pass

    return admin_group_id


async def _ensure_base_user_group(storage, now):
    """
    Garantiza que exista el grupo base de usuarios autenticados.
    """
    sales_group_id = await _fetchval(
        storage,
        'SELECT id FROM "res_groups" WHERE name = $1 ORDER BY id LIMIT 1',
        "Ventas / Usuario",
    )

    if not sales_group_id:
        try:
            sales_group_id = await _fetchval(
                storage,
                """
                INSERT INTO "res_groups"
                    (name, description, is_system_admin, active, write_version, create_date, write_date)
                VALUES ($1, $2, FALSE, TRUE, 1, $3, $3)
                RETURNING id
                """,
                "Ventas / Usuario",
                "Grupo base. Todo usuario autenticado pertenece a este grupo.",
                now,
            )
        except Exception:
            sales_group_id = await _fetchval(
                storage,
                """
                INSERT INTO "res_groups"
                    (name, description, active, write_version, create_date, write_date)
                VALUES ($1, $2, TRUE, 1, $3, $3)
                RETURNING id
                """,
                "Ventas / Usuario",
                "Grupo base. Todo usuario autenticado pertenece a este grupo.",
                now,
            )
        print("   ✨ [SEGURIDAD] Grupo Ventas / Usuario creado.")

    # Convergencia: este grupo nunca debe ser admin
    try:
        await _exec(
            storage,
            """
            UPDATE "res_groups"
            SET is_system_admin = FALSE
            WHERE id = $1
            """,
            sales_group_id,
        )
    except Exception:
        pass

    return sales_group_id


async def _ensure_public_and_admin_acl(storage, admin_group_id, now):
    """
    Crea/actualiza ACL públicos y ACL admin para todos los modelos.
    """
    technical_models = {
        "ir.rule",
        "ir.model",
        "ir.model.fields",
        "ir.model.access",
        "ir.ui.menu",
        "ir.ui.view",
        "ir.sequence",
        "ir.config_parameter",
        "ir.module",
        "ir.module.dependency",
        "ir.model.data",
        "ir.actions.act_window",
        "ir.actions.server",
        "res.groups",
    }

    all_models = await _fetch(storage, 'SELECT id, model FROM "ir_model"')
    acl_public = 0
    acl_admin = 0

    for row in all_models:
        model_id = row["id"]
        model_name = row["model"]

        if not model_name:
            continue

        is_technical = model_name in technical_models
        perm_read = True
        perm_write = not is_technical
        perm_create = not is_technical
        perm_unlink = not is_technical

        # ACL pública
        exists_public = await _fetchval(
            storage,
            'SELECT id FROM "ir_model_access" WHERE model_id = $1 AND group_id IS NULL LIMIT 1',
            model_id,
        )

        if not exists_public:
            await _exec(
                storage,
                """
                INSERT INTO "ir_model_access"
                    (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink,
                     active, write_version, create_date, write_date)
                VALUES ($1, $2, NULL, $3, $4, $5, $6, TRUE, 1, $7, $7)
                """,
                f"Public: {model_name}",
                model_id,
                perm_read,
                perm_write,
                perm_create,
                perm_unlink,
                now,
            )
            acl_public += 1
        else:
            await _exec(
                storage,
                """
                UPDATE "ir_model_access"
                SET perm_read = $1,
                    perm_write = $2,
                    perm_create = $3,
                    perm_unlink = $4,
                    active = TRUE
                WHERE model_id = $5
                  AND group_id IS NULL
                """,
                perm_read,
                perm_write,
                perm_create,
                perm_unlink,
                model_id,
            )

        # ACL admin
        exists_admin = await _fetchval(
            storage,
            'SELECT id FROM "ir_model_access" WHERE model_id = $1 AND group_id = $2 LIMIT 1',
            model_id,
            admin_group_id,
        )

        if not exists_admin:
            await _exec(
                storage,
                """
                INSERT INTO "ir_model_access"
                    (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink,
                     active, write_version, create_date, write_date)
                VALUES ($1, $2, $3, TRUE, TRUE, TRUE, TRUE, TRUE, 1, $4, $4)
                """,
                f"Admin: {model_name}",
                model_id,
                admin_group_id,
                now,
            )
            acl_admin += 1
        else:
            await _exec(
                storage,
                """
                UPDATE "ir_model_access"
                SET perm_read = TRUE,
                    perm_write = TRUE,
                    perm_create = TRUE,
                    perm_unlink = TRUE,
                    active = TRUE
                WHERE model_id = $1
                  AND group_id = $2
                """,
                model_id,
                admin_group_id,
            )

    return acl_public, acl_admin


async def _assign_base_group_to_existing_users(storage, sales_group_id):
    """
    Todo usuario autenticado debe pertenecer al grupo base.
    """
    all_users = await _fetch(
        storage,
        'SELECT id FROM "res_users" WHERE active = TRUE',
    )

    retroactive = 0

    for u in all_users:
        uid = u["id"]
        already = await _fetchval(
            storage,
            'SELECT 1 FROM "res_users_group_ids_rel" WHERE base_id = $1 AND rel_id = $2',
            uid,
            sales_group_id,
        )
        if not already:
            await _exec(
                storage,
                'INSERT INTO "res_users_group_ids_rel" (base_id, rel_id) VALUES ($1, $2)',
                uid,
                sales_group_id,
            )
            retroactive += 1

    return retroactive


async def _reset_sales_rls(storage, now):
    """
    Reglas RLS de ventas.
    El admin ve todo porque bypassa en ir.rule._is_admin_user().
    """
    await _exec(
        storage,
        """
        DELETE FROM "ir_rule"
        WHERE model_name IN ('sale.order', 'sale.order.line')
        """,
    )

    await _exec(
        storage,
        """
        INSERT INTO "ir_rule"
            (name, model_name, domain_force, group_id,
             perm_read, perm_write, perm_create, perm_unlink,
             active, write_version, create_date, write_date)
        VALUES ($1, $2, $3, NULL, TRUE, TRUE, TRUE, FALSE, TRUE, 1, $4, $4)
        """,
        "Sale Order: ver solo propios",
        "sale.order",
        '[["create_uid","=","{user_id}"]]',
        now,
    )

    await _exec(
        storage,
        """
        INSERT INTO "ir_rule"
            (name, model_name, domain_force, group_id,
             perm_read, perm_write, perm_create, perm_unlink,
             active, write_version, create_date, write_date)
        VALUES ($1, $2, $3, NULL, TRUE, TRUE, TRUE, TRUE, TRUE, 1, $4, $4)
        """,
        "Sale Order Line: ver solo propias",
        "sale.order.line",
        '[["create_uid","=","{user_id}"]]',
        now,
    )


async def init_base_security(env):
    """
    🛡️ SEGURIDAD ENTERPRISE — SQL DIRECTO

    Principio:
    - los registros críticos de seguridad se materializan directamente en PostgreSQL
    - bootstrap idempotente
    - convergencia automática de datos legacy al criterio técnico correcto
    """
    print("   🛡️ [SEGURIDAD] Generando Matriz de Accesos Global...")

    import datetime
    from app.core.storage.postgres_storage import PostgresGraphStorage

    storage = PostgresGraphStorage()
    now = datetime.datetime.utcnow()

    # 1. Grupos base
    admin_group_id = await _ensure_admin_group(storage, now)
    sales_group_id = await _ensure_base_user_group(storage, now)

    # 2. ACL
    acl_public, acl_admin = await _ensure_public_and_admin_acl(
        storage=storage,
        admin_group_id=admin_group_id,
        now=now,
    )

    # 3. Grupo base para usuarios existentes
    retroactive = await _assign_base_group_to_existing_users(
        storage=storage,
        sales_group_id=sales_group_id,
    )

    # 4. RLS de ventas
    await _reset_sales_rls(storage=storage, now=now)

    print(
        f"      ✅ Seguridad en BD: "
        f"{acl_public} ACL públicos, "
        f"{acl_admin} ACL admin, "
        f"{retroactive} usuarios → grupo base, "
        f"grupo admin convergido a is_system_admin=TRUE, "
        f"RLS de ventas activas."
    )