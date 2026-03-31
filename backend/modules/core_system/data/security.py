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

from app.core.clock import utc_now_naive


async def _exec(conn, query, *args):
    return await conn.execute(query, *args)


async def _fetch(conn, query, *args):
    return await conn.fetch(query, *args)


async def _fetchrow(conn, query, *args):
    return await conn.fetchrow(query, *args)


async def _fetchval(conn, query, *args):
    return await conn.fetchval(query, *args)


async def _ensure_admin_group(conn, now):
    admin_group_id = None

    try:
        admin_group_id = await _fetchval(
            conn,
            'SELECT id FROM "res_groups" WHERE is_system_admin = TRUE ORDER BY id LIMIT 1',
        )
    except Exception:
        admin_group_id = None

    if not admin_group_id:
        try:
            admin_group_id = await _fetchval(
                conn,
                'SELECT id FROM "res_groups" WHERE name = $1 ORDER BY id LIMIT 1',
                "Administración / Ajustes",
            )
        except Exception:
            admin_group_id = None

    if not admin_group_id:
        try:
            admin_group_id = await _fetchval(
                conn,
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
            admin_group_id = await _fetchval(
                conn,
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

    try:
        await _exec(
            conn,
            """
            UPDATE "res_groups"
            SET is_system_admin = TRUE
            WHERE id = $1
            """,
            admin_group_id,
        )
    except Exception:
        pass

    return admin_group_id


async def _ensure_base_user_group(conn, now):
    sales_group_id = await _fetchval(
        conn,
        'SELECT id FROM "res_groups" WHERE name = $1 ORDER BY id LIMIT 1',
        "Ventas / Usuario",
    )

    if not sales_group_id:
        try:
            sales_group_id = await _fetchval(
                conn,
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
                conn,
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

    try:
        await _exec(
            conn,
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


async def _ensure_public_and_admin_acl(conn, admin_group_id, now):
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

    all_models = await _fetch(conn, 'SELECT id, model FROM "ir_model"')
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

        exists_public = await _fetchval(
            conn,
            'SELECT id FROM "ir_model_access" WHERE model_id = $1 AND group_id IS NULL LIMIT 1',
            model_id,
        )

        if not exists_public:
            await _exec(
                conn,
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
                conn,
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

        exists_admin = await _fetchval(
            conn,
            'SELECT id FROM "ir_model_access" WHERE model_id = $1 AND group_id = $2 LIMIT 1',
            model_id,
            admin_group_id,
        )

        if not exists_admin:
            await _exec(
                conn,
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
                conn,
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


async def _assign_base_group_to_existing_users(conn, sales_group_id):
    all_users = await _fetch(
        conn,
        'SELECT id FROM "res_users" WHERE active = TRUE',
    )

    retroactive = 0

    for u in all_users:
        uid = u["id"]
        already = await _fetchval(
            conn,
            'SELECT 1 FROM "res_users_group_ids_rel" WHERE base_id = $1 AND rel_id = $2',
            uid,
            sales_group_id,
        )
        if not already:
            await _exec(
                conn,
                'INSERT INTO "res_users_group_ids_rel" (base_id, rel_id) VALUES ($1, $2)',
                uid,
                sales_group_id,
            )
            retroactive += 1

    return retroactive


async def _reset_sales_rls(conn, now):
    await _exec(
        conn,
        """
        DELETE FROM "ir_rule"
        WHERE model_name IN ('sale.order', 'sale.order.line')
        """,
    )

    await _exec(
        conn,
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
        conn,
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
    print("   🛡️ [SEGURIDAD] Generando Matriz de Accesos Global...")

    from app.core.storage.postgres_storage import PostgresGraphStorage

    storage = PostgresGraphStorage()
    conn = await storage.get_connection()
    now = utc_now_naive()

    admin_group_id = await _ensure_admin_group(conn, now)
    sales_group_id = await _ensure_base_user_group(conn, now)

    acl_public, acl_admin = await _ensure_public_and_admin_acl(
        conn=conn,
        admin_group_id=admin_group_id,
        now=now,
    )

    retroactive = await _assign_base_group_to_existing_users(
        conn=conn,
        sales_group_id=sales_group_id,
    )

    await _reset_sales_rls(conn=conn, now=now)

    print(
        f"      ✅ Seguridad en BD: "
        f"{acl_public} ACL públicos, "
        f"{acl_admin} ACL admin, "
        f"{retroactive} usuarios → grupo base, "
        f"grupo admin convergido a is_system_admin=TRUE, "
        f"RLS de ventas activas."
    )