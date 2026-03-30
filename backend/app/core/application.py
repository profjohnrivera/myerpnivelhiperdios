# backend/app/core/application.py

import os
from typing import Any, List, Type

from app.core.event_bus import EventBus
from app.core.graph import Graph
from app.core.kernel import Kernel
from app.core.storage.postgres_storage import PostgresGraphStorage


def _validate_production_secrets():
    secret_key = os.getenv("ERP_SECRET_KEY", "DEV_ONLY_CHANGE_ME_HIPERDIOS")
    db_password = os.getenv("ERP_DB_PASSWORD", "1234")
    env_mode = os.getenv("ERP_ENV", "development")

    if env_mode == "production":
        errors = []

        if "DEV_ONLY" in secret_key or secret_key == "DEV_ONLY_CHANGE_ME_HIPERDIOS":
            errors.append(
                "❌ ERP_SECRET_KEY tiene el valor por defecto de desarrollo. "
                "Define una clave segura de al menos 32 caracteres."
            )

        if db_password in ("1234", "postgres", "password", "admin", ""):
            errors.append(
                "❌ ERP_DB_PASSWORD tiene una contraseña trivial. "
                "Define una contraseña segura para la base de datos."
            )

        if errors:
            raise RuntimeError(
                "\n🛑 ARRANQUE BLOQUEADO — Credenciales inseguras detectadas:\n"
                + "\n".join(errors)
                + "\n\nDefine las variables de entorno correctas o cambia ERP_ENV a 'development'."
            )
    else:
        if "DEV_ONLY" in secret_key:
            print("⚠️  [SECURITY] ERP_SECRET_KEY usa el valor de desarrollo. NO usar en producción.")
        if db_password in ("1234", "postgres", "password", "admin"):
            print("⚠️  [SECURITY] ERP_DB_PASSWORD usa una contraseña débil. NO usar en producción.")


class Application:
    def __init__(self) -> None:
        _validate_production_secrets()

        self.bus = EventBus()
        EventBus.set_active(self.bus)

        self.storage = PostgresGraphStorage()

        self.graph = Graph()
        self.graph.set_loader(self.storage.load_context)

        self.kernel = Kernel(bus=self.bus, graph=self.graph)

    async def boot(self, modules: List[Type]) -> None:
        print("🔌 Application: Initializing infrastructure...")

        await self.storage.get_pool()
        self.kernel.load_modules(modules)
        await self.kernel.prepare()

        await self._warm_up_system_config()
        await self.kernel.load_data()
        await self.kernel.boot()

    async def _warm_up_system_config(self):
        """
        Carga SOLO ir.config_parameter en el graph maestro.

        Consume el contrato único de get_connection():
        siempre devuelve un objeto conexión-like.
        """
        try:
            conn = await self.storage.get_connection()
            rows = await conn.fetch('SELECT * FROM "ir_config_parameter" LIMIT 500')

            for row in rows:
                rec_id = row["id"]
                for col, val in row.items():
                    if col == "id":
                        continue
                    key = ("ir.config_parameter", rec_id, col)
                    self.graph._values[key] = self.storage._parse_db_value(val)
                    self.graph._versions[key] = 1

            print(f"   ✅ Sistema: {len(rows)} parámetros de configuración cargados en memoria.")

        except Exception:
            print("   ℹ️  ir_config_parameter aún no existe, se creará en prepare().")

    async def emit(self, event: Any) -> None:
        try:
            await self.bus.publish(event)
            await self.storage.save(self.graph)
        except Exception as e:
            print(f"🔥 CRITICAL SYSTEM FAILURE: Event processing failed: {e}")
            raise

    async def shutdown(self) -> None:
        print("🔌 Application: Initiating graceful shutdown...")
        await self.kernel.shutdown()

        pool = getattr(self.storage, "_conn_pool", None)
        if pool:
            await pool.close()

        EventBus.clear_active()
        print("🔌 Application: Offline.")