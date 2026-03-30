# backend/modules/core_system/data/security.py
# ============================================================
# SEGURIDAD ENTERPRISE — ARQUITECTURA DEFINITIVA
#
# PROBLEMA RAÍZ de todos los fallos anteriores:
#   El ORM crea registros en el Graph (RAM).
#   storage.save() es necesario para persistirlos en PostgreSQL.
#   check_access() y get_domain() usan SQL DIRECTO — no el Graph.
#   Si storage.save() no se llama, los ACL y reglas existen solo
#   en RAM y mueren con el proceso. Próximo request → sin ACL → bloqueado.
#
# SOLUCIÓN DEFINITIVA:
#   Usar SQL directo para las operaciones críticas de seguridad.
#   No depende del Graph, no depende de storage.save(), no hay ambigüedad.
#   Las mismas consultas que usa check_access() son las que insertamos.
# ============================================================

import json


async def _get_conn(storage):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, 'acquire'):
        return pool_or_conn, True   # (pool, needs_context_manager)
    return pool_or_conn, False      # (conn, direct use)


async def _exec(storage, query, *args):
    """Ejecuta SQL directo, compatible con pool o conexión directa."""
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, 'acquire'):
        async with pool_or_conn.acquire() as conn:
            return await conn.execute(query, *args)
    else:
        return await pool_or_conn.execute(query, *args)


async def _fetch(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, 'acquire'):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetch(query, *args)
    else:
        return await pool_or_conn.fetch(query, *args)


async def _fetchrow(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, 'acquire'):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetchrow(query, *args)
    else:
        return await pool_or_conn.fetchrow(query, *args)


async def _fetchval(storage, query, *args):
    pool_or_conn = await storage.get_connection()
    if hasattr(pool_or_conn, 'acquire'):
        async with pool_or_conn.acquire() as conn:
            return await conn.fetchval(query, *args)
    else:
        return await pool_or_conn.fetchval(query, *args)


async def init_base_security(env):
    """
    🛡️ SEGURIDAD ENTERPRISE — SQL DIRECTO
    Usa SQL directo para garantizar que los registros críticos
    llegan a PostgreSQL inmediatamente, sin depender del Graph ni
    de storage.save(). Idempotente en cada reinicio.
    """
    print("   🛡️ [SEGURIDAD] Generando Matriz de Accesos Global...")

    from app.core.storage.postgres_storage import PostgresGraphStorage
    import datetime

    storage = PostgresGraphStorage()
    now = datetime.datetime.utcnow()  # asyncpg requires datetime object, NOT isoformat() string

    # =========================================================
    # 1. GRUPOS BASE
    # =========================================================

    # Grupo admin (is_system_admin=True)
    # Buscar grupo admin: primero por is_system_admin (si existe la columna),
    # fallback por nombre. Robusto ante columna faltante (res_groups.py no actualizado).
    admin_group_id = None
    try:
        admin_group_id = await _fetchval(storage,
            'SELECT id FROM "res_groups" WHERE is_system_admin = TRUE LIMIT 1')
    except Exception:
        # Columna is_system_admin no existe aún → buscar por nombre
        pass
    if not admin_group_id:
        try:
            admin_group_id = await _fetchval(storage,
                "SELECT id FROM res_groups WHERE name = 'Administración / Ajustes' LIMIT 1")
        except Exception:
            pass
    if not admin_group_id:
        # Crear sin is_system_admin (puede que la columna no exista)
        try:
            admin_group_id = await _fetchval(storage, """
                INSERT INTO "res_groups"
                    (name, description, is_system_admin, active, write_version, create_date, write_date)
                VALUES ($1, $2, TRUE, TRUE, 1, $3, $3)
                RETURNING id
            """, "Administración / Ajustes",
                "Acceso total al sistema. Bypass de ACL y RLS.", now)
        except Exception:
            # is_system_admin column doesn't exist, insert without it
            admin_group_id = await _fetchval(storage, """
                INSERT INTO "res_groups"
                    (name, description, active, write_version, create_date, write_date)
                VALUES ($1, $2, TRUE, TRUE, $3, $3)
                RETURNING id
            """, "Administración / Ajustes",
                "Acceso total al sistema. Bypass de ACL y RLS.", now)
        print("   ✨ [SEGURIDAD] Grupo Administrador creado.")

    # Grupo base de todos los usuarios autenticados
    sales_group_id = await _fetchval(storage,
        'SELECT id FROM "res_groups" WHERE name = $1 LIMIT 1', "Ventas / Usuario")
    if not sales_group_id:
        sales_group_id = await _fetchval(storage, """
            INSERT INTO "res_groups"
                (name, description, is_system_admin, active, write_version, create_date, write_date)
            VALUES ($1, $2, FALSE, TRUE, 1, $3, $3)
            RETURNING id
        """, "Ventas / Usuario",
            "Grupo base. Todo usuario autenticado pertenece a este grupo.", now)
        print("   ✨ [SEGURIDAD] Grupo Ventas / Usuario creado.")

    # =========================================================
    # 2. ACL PÚBLICOS — todos los modelos, group_id=NULL
    # =========================================================
    # group_id IS NULL → aplica a todo usuario autenticado
    # (ver check_access SQL: WHERE group_id IS NULL OR rug.base_id = $2)
    #
    # Modelos técnicos: solo lectura
    # Modelos de negocio: CRUD completo
    # La restricción de QUÉ FILAS = ir.rule (CAPA RLS)

    technical_models = {
        "ir.rule", "ir.model", "ir.model.fields", "ir.model.access",
        "ir.ui.menu", "ir.ui.view", "ir.sequence", "ir.config_parameter",
        "ir.module", "ir.module.dependency", "ir.model.data",
        "ir.actions.act_window", "ir.actions.server", "res.groups",
    }

    all_models = await _fetch(storage, 'SELECT id, model FROM "ir_model"')
    acl_public = 0
    acl_admin = 0

    for row in all_models:
        model_id = row['id']
        model_name = row['model']
        if not model_name:
            continue

        is_technical = model_name in technical_models
        perm_read   = True
        perm_write  = not is_technical
        perm_create = not is_technical
        perm_unlink = not is_technical

        # PUBLIC ACL (group_id = NULL)
        exists_public = await _fetchval(storage,
            'SELECT id FROM "ir_model_access" WHERE model_id=$1 AND group_id IS NULL LIMIT 1',
            model_id)
        if not exists_public:
            await _exec(storage, """
                INSERT INTO "ir_model_access"
                    (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink,
                     active, write_version, create_date, write_date)
                VALUES ($1, $2, NULL, $3, $4, $5, $6, TRUE, 1, $7, $7)
            """, f"Public: {model_name}", model_id,
                perm_read, perm_write, perm_create, perm_unlink, now)
            acl_public += 1
        else:
            # UPDATE existing to ensure correct permissions
            await _exec(storage, """
                UPDATE "ir_model_access"
                SET perm_read=$1, perm_write=$2, perm_create=$3, perm_unlink=$4
                WHERE model_id=$5 AND group_id IS NULL
            """, perm_read, perm_write, perm_create, perm_unlink, model_id)

        # ADMIN ACL (group_id = admin_group_id)
        exists_admin = await _fetchval(storage,
            'SELECT id FROM "ir_model_access" WHERE model_id=$1 AND group_id=$2 LIMIT 1',
            model_id, admin_group_id)
        if not exists_admin:
            await _exec(storage, """
                INSERT INTO "ir_model_access"
                    (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink,
                     active, write_version, create_date, write_date)
                VALUES ($1, $2, $3, TRUE, TRUE, TRUE, TRUE, TRUE, 1, $4, $4)
            """, f"Admin: {model_name}", model_id, admin_group_id, now)
            acl_admin += 1

    # =========================================================
    # 3. ASIGNACIÓN RETROACTIVA DE GRUPO BASE A USUARIOS
    # =========================================================
    all_users = await _fetch(storage,
        'SELECT id FROM "res_users" WHERE active = TRUE')
    retroactive = 0
    for u in all_users:
        uid = u['id']
        already = await _fetchval(storage,
            'SELECT 1 FROM "res_users_group_ids_rel" WHERE base_id=$1 AND rel_id=$2',
            uid, sales_group_id)
        if not already:
            await _exec(storage,
                'INSERT INTO "res_users_group_ids_rel" (base_id, rel_id) VALUES ($1, $2)',
                uid, sales_group_id)
            retroactive += 1

    # =========================================================
    # 4. RLS — REGLAS DE AISLAMIENTO POR USUARIO
    # =========================================================
    # ARQUITECTURA DEFINITIVA: group_id = NULL
    #
    # POR QUÉ NULL y no sales_group_id:
    # La asignación retroactiva de usuarios al grupo ocurre en el paso 3,
    # ANTES de que demo data cree a Alpha y Beta. Cuando Alpha y Beta
    # se crean (mod_sales/demo.py), ya no hay nadie que los asigne al grupo.
    # Resultado: _user_group_ids(alpha) = [] → regla con group_id saltada
    # → combined_domain=[] → sin filtro → todos ven los registros de todos.
    #
    # Con group_id=NULL la regla aplica a CUALQUIER usuario autenticado.
    # El admin sigue viendo todo vía _is_admin_user() (bypass).
    # El dominio {user_id} filtra correctamente en cada request.

    # Borrar TODAS las reglas anteriores de estos modelos (limpieza total)
    await _exec(storage, """
        DELETE FROM "ir_rule"
        WHERE model_name IN ('sale.order', 'sale.order.line')
    """)

    # Crear regla sale.order con group_id=NULL → aplica a todos
    await _exec(storage, """
        INSERT INTO "ir_rule"
            (name, model_name, domain_force, group_id,
             perm_read, perm_write, perm_create, perm_unlink,
             active, write_version, create_date, write_date)
        VALUES ($1, $2, $3, NULL, TRUE, TRUE, TRUE, FALSE, TRUE, 1, $4, $4)
    """, "Sale Order: ver solo propios", "sale.order",
        '[["create_uid","=","{user_id}"]]', now)

    # Crear regla sale.order.line con group_id=NULL → aplica a todos
    await _exec(storage, """
        INSERT INTO "ir_rule"
            (name, model_name, domain_force, group_id,
             perm_read, perm_write, perm_create, perm_unlink,
             active, write_version, create_date, write_date)
        VALUES ($1, $2, $3, NULL, TRUE, TRUE, TRUE, TRUE, TRUE, 1, $4, $4)
    """, "Sale Order Line: ver solo propias", "sale.order.line",
        '[["create_uid","=","{user_id}"]]', now)

    print(
        f"      ✅ Seguridad en BD: "
        f"{acl_public} ACL públicos, {acl_admin} ACL admin, "
        f"{retroactive} usuarios → grupo base, "
        f"reglas RLS sale.order activas."
    )