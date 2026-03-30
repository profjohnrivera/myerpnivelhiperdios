# backend/fix_db.py

import asyncio

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.env import Env


async def _save_and_resolve(app, *records):
    """
    Persiste el graph y devuelve una lista de IDs reales alineada con los records.
    """
    id_map = await app.storage.save(app.graph)
    resolved = []
    for record in records:
        real_id = id_map.get(str(record.id), record.id)
        resolved.append(real_id)
    return resolved


async def _get_or_create_company(env_system, app):
    """
    Garantiza que exista la compañía base.
    """
    Company = env_system["res.company"]
    companies = await Company.search([], limit=1)

    if companies:
        return companies[0].id

    new_company = await Company.create({"name": "HiperDios Corp"})
    [company_id] = await _save_and_resolve(app, new_company)
    return company_id


async def _get_or_create_group(env_system, app, name: str, description: str = "", is_system_admin: bool = False):
    """
    Garantiza grupos consistentes con la constitución nueva:
    - admin real = is_system_admin=True
    - grupos normales = is_system_admin=False
    """
    ResGroups = env_system["res.groups"]

    groups = await ResGroups.search([("name", "=", name)], limit=1)
    if groups:
        group = groups[0]
        await group.write({
            "description": description,
            "is_system_admin": is_system_admin,
        })
        await app.storage.save(app.graph)
        return group.id

    group = await ResGroups.create({
        "name": name,
        "description": description,
        "is_system_admin": is_system_admin,
    })
    [group_id] = await _save_and_resolve(app, group)
    return group_id


async def _get_or_create_user(
    env_system,
    app,
    *,
    login: str,
    name: str,
    password: str,
    company_id: int,
    group_ids: list[int],
):
    """
    Crea o actualiza un usuario demo.
    """
    UserModel = env_system["res.users"]

    users = await UserModel.search([("login", "=", login)], limit=1)
    if users:
        user = users[0]
        await user.write({
            "name": name,
            "password": password,
            "company_id": company_id,
            "group_ids": group_ids,
            "active": True,
        })
        await app.storage.save(app.graph)
        return user.id

    user = await UserModel.create({
        "name": name,
        "login": login,
        "password": password,
        "group_ids": group_ids,
        "company_id": company_id,
        "active": True,
    })
    [user_id] = await _save_and_resolve(app, user)
    return user_id


async def reset_db():
    print("🔌 Iniciando Protocolo de Reseteo Constitucional...")

    app = Application()
    pool = await app.storage.get_pool()

    # ==========================================================
    # 🧹 LIMPIEZA NUCLEAR
    # ==========================================================
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE;")
        await conn.execute("CREATE SCHEMA public;")
        await conn.execute("GRANT ALL ON SCHEMA public TO postgres;")
        await conn.execute("GRANT ALL ON SCHEMA public TO public;")

    # ==========================================================
    # 💎 BOOT CONSTITUCIONAL ÚNICO
    # - prepare()
    # - load_data()  -> aquí viven security.py, menus.py, demo.py
    # - boot()
    # ==========================================================
    modules = discover_modules("modules")
    await app.boot(modules)

    # Entorno técnico del sembrado
    env_system = Env(
        user_id="system",
        graph=app.graph,
        su=True,
        context={"disable_audit": True},
    )

    # ==========================================================
    # 🏢 FASE 0: COMPAÑÍA BASE
    # ==========================================================
    print("\n--- 🏢 Asegurando Compañía Base ---")
    company_id = await _get_or_create_company(env_system, app)

    # ==========================================================
    # 🎭 FASE 1: GRUPOS CONSTITUCIONALES
    # ----------------------------------------------------------
    # IMPORTANTE:
    # Ya NO duplicamos ACL/RLS aquí.
    # La seguridad global vive en:
    #   modules/core_system/data/security.py
    #
    # Aquí solo garantizamos que los grupos demo estén coherentes.
    # ==========================================================
    print("\n--- 🎭 Asegurando Grupos Constitucionales ---")

    r_admin_id = await _get_or_create_group(
        env_system,
        app,
        name="Administración / Ajustes",
        description="Acceso total al sistema. Bypass de ACL y RLS.",
        is_system_admin=True,
    )

    r_ventas_id = await _get_or_create_group(
        env_system,
        app,
        name="Ventas / Usuario",
        description="Grupo base de usuarios autenticados.",
        is_system_admin=False,
    )

    r_gerencia_id = await _get_or_create_group(
        env_system,
        app,
        name="Ventas / Gerencia",
        description="Perfil gerencial del módulo de ventas.",
        is_system_admin=False,
    )

    # ==========================================================
    # 👥 FASE 2: USUARIOS DEMO
    # ----------------------------------------------------------
    # Admin:
    #   - grupo admin técnico real
    #   - también pertenece al grupo base para compatibilidad de menús/ACL
    #
    # Alpha:
    #   - vendedor operativo
    #
    # Beta:
    #   - gerencia + base
    # ==========================================================
    print("\n--- 👥 Asegurando Usuarios Demo ---")

    admin_id = await _get_or_create_user(
        env_system,
        app,
        login="admin",
        name="Mitchell Admin",
        password="admin",
        company_id=company_id,
        group_ids=[r_admin_id, r_ventas_id],
    )

    alpha_id = await _get_or_create_user(
        env_system,
        app,
        login="alpha",
        name="Vendedor Alpha",
        password="admin",
        company_id=company_id,
        group_ids=[r_ventas_id],
    )

    beta_id = await _get_or_create_user(
        env_system,
        app,
        login="beta",
        name="Gerente Beta",
        password="admin",
        company_id=company_id,
        group_ids=[r_gerencia_id, r_ventas_id],
    )

    # ==========================================================
    # 🧪 FASE 3: VALIDACIÓN RÁPIDA DE COHERENCIA
    # ==========================================================
    print("\n--- 🧪 Validando Coherencia de Seguridad ---")

    ResGroups = env_system["res.groups"]
    admin_groups = await ResGroups.search([
        ("name", "=", "Administración / Ajustes")
    ], limit=1)

    if admin_groups:
        admin_group = admin_groups[0]
        try:
            is_admin_flag = bool(getattr(admin_group, "is_system_admin", False))
            print(f"   ✅ Grupo admin técnico: {admin_group.id} | is_system_admin={is_admin_flag}")
        except Exception:
            print("   ⚠️ No se pudo leer el flag is_system_admin del grupo admin.")

    print("\n==========================================================")
    print("✅ RESET CONSTITUCIONAL COMPLETADO")
    print("----------------------------------------------------------")
    print(f"🏢 Company ID: {company_id}")
    print(f"👤 Admin ID:   {admin_id}   | login=admin | password=admin")
    print(f"👤 Alpha ID:   {alpha_id}   | login=alpha | password=admin")
    print(f"👤 Beta ID:    {beta_id}    | login=beta  | password=admin")
    print("==========================================================\n")

    # Apagado limpio del kernel/app
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(reset_db())