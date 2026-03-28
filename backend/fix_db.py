# backend/fix_db.py
import asyncio

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.env import Env


async def reset_db():
    print("🔌 Iniciando Protocolo de Reseteo (Multi-Usuario + RBAC)...")

    app = Application()
    pool = await app.storage.get_pool()

    # 🧹 Limpieza nuclear de la base de datos
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE;")
        await conn.execute("CREATE SCHEMA public;")
        await conn.execute("GRANT ALL ON SCHEMA public TO postgres;")
        await conn.execute("GRANT ALL ON SCHEMA public TO public;")

    # 💎 BOOT CONSTITUCIONAL ÚNICO
    modules = discover_modules("modules")
    await app.boot(modules)

    # Entorno técnico del sembrado: sin auditoría y con privilegios de sistema
    env_system = Env(
        user_id="system",
        graph=app.graph,
        su=True,
        context={"disable_audit": True},
    )

    # ==========================================================
    # 🏢 FASE 0: COMPAÑÍA BASE
    # ==========================================================
    Company = env_system["res.company"]
    companies = await Company.search([], limit=1)
    if companies:
        company_id = companies[0].id
    else:
        new_company = await Company.create({"name": "HiperDios Corp"})
        id_map = await app.storage.save(app.graph)
        company_id = id_map.get(str(new_company.id), new_company.id)

    # ==========================================================
    # 🎭 FASE 1: CREACIÓN DE ROLES Y MATRIZ DE ACCESO (RBAC)
    # ==========================================================
    print("\n--- 🎭 Forjando Matriz de Accesos (RBAC) ---")
    ResGroups = env_system["res.groups"]
    IrModel = env_system["ir.model"]
    IrModelAccess = env_system["ir.model.access"]

    role_admin = await ResGroups.create({"name": "Administración / Ajustes"})
    role_ventas = await ResGroups.create({"name": "Ventas / Operativo"})
    role_gerencia = await ResGroups.create({"name": "Ventas / Gerencia"})

    id_map = await app.storage.save(app.graph)
    r_admin_id = id_map.get(str(role_admin.id), role_admin.id)
    r_ventas_id = id_map.get(str(role_ventas.id), role_ventas.id)
    r_gerencia_id = id_map.get(str(role_gerencia.id), role_gerencia.id)

    sale_models = await IrModel.search([("model", "=", "sale.order")])
    partner_models = await IrModel.search([("model", "=", "res.partner")])

    sale_model_id = sale_models[0].id if sale_models else None
    partner_model_id = partner_models[0].id if partner_models else None

    if sale_model_id and partner_model_id:
        await IrModelAccess.create({
            "name": "Vendedores - Ventas",
            "model_id": sale_model_id,
            "group_id": r_ventas_id,
            "perm_read": True,
            "perm_write": True,
            "perm_create": True,
            "perm_unlink": False,
        })
        await IrModelAccess.create({
            "name": "Vendedores - Clientes",
            "model_id": partner_model_id,
            "group_id": r_ventas_id,
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        })
        await IrModelAccess.create({
            "name": "Gerencia - Ventas Totales",
            "model_id": sale_model_id,
            "group_id": r_gerencia_id,
            "perm_read": True,
            "perm_write": True,
            "perm_create": True,
            "perm_unlink": True,
        })

        all_models = await IrModel.search([])
        for m in all_models:
            await IrModelAccess.create({
                "name": f"Admin - {m.model}",
                "model_id": m.id,
                "group_id": r_admin_id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            })

    await app.storage.save(app.graph)

    # ==========================================================
    # 👥 FASE 2: USUARIOS
    # ==========================================================
    print("\n--- 👥 Asignando Gafetes de Seguridad ---")
    UserModel = env_system["res.users"]

    admin = await UserModel.create({
        "name": "Mitchell Admin",
        "login": "admin",
        "password": "admin",
        "group_ids": [r_admin_id],
        "company_id": company_id,
    })
    alpha = await UserModel.create({
        "name": "Vendedor Alpha",
        "login": "alpha",
        "password": "admin",
        "group_ids": [r_ventas_id],
        "company_id": company_id,
    })
    beta = await UserModel.create({
        "name": "Gerente Beta",
        "login": "beta",
        "password": "admin",
        "group_ids": [r_gerencia_id],
        "company_id": company_id,
    })

    id_map = await app.storage.save(app.graph)
    alpha_id = id_map.get(str(alpha.id), alpha.id)
    beta_id = id_map.get(str(beta.id), beta.id)

    # ==========================================================
    # 🛡️ FASE 3: PRIVACIDAD DE DATOS (RLS)
    # ==========================================================
    print("\n--- 🛡️ Creando Privacidad de Filas (RLS) ---")
    IrRule = env_system["ir.rule"]
    await IrRule.create({
        "name": "Privacidad de Ventas (Solo mis pedidos)",
        "model_name": "sale.order",
        "domain_force": '[["create_uid", "=", "{user_id}"]]',
    })

    await app.storage.save(app.graph)

    # ==========================================================
    # 🛒 FASE 4: SIMULACIÓN DE TRABAJO
    # ==========================================================
    print("\n--- 🛒 Simulando operaciones de la empresa ---")
    Partner = env_system["res.partner"]
    cliente1 = await Partner.create({"name": "Corporación Stark"})

    id_map = await app.storage.save(app.graph)
    c1_id = id_map.get(str(cliente1.id), cliente1.id)

    # El vendedor Alpha crea su pedido
    env_alpha = Env(
        user_id=alpha_id,
        graph=app.graph,
        context={"company_id": company_id},
    )
    await env_alpha["sale.order"].create({
        "partner_id": c1_id,
        "company_id": company_id,
    })
    print("      ✅ [Alpha] Pedido creado exitosamente.")

    # El gerente Beta crea su pedido
    env_beta = Env(
        user_id=beta_id,
        graph=app.graph,
        context={"company_id": company_id},
    )
    await env_beta["sale.order"].create({
        "partner_id": c1_id,
        "company_id": company_id,
    })
    print("      ✅ [Beta] Pedido creado exitosamente.")

    await app.storage.save(app.graph)

    print("✅ ¡Arquitectura de BIGSERIAL Completa! RLS + RBAC Operativos y Tipados.")

    # 🔌 Apagado limpio
    await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(reset_db())
    except KeyboardInterrupt:
        pass