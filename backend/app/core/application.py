# backend/app/core/application.py
from typing import Any, List, Type

from app.core.event_bus import EventBus
from app.core.graph import Graph
from app.core.kernel import Kernel
from app.core.storage.postgres_storage import PostgresGraphStorage


class Application:
    """
    Orquestador maestro.
    """

    def __init__(self) -> None:
        self.bus = EventBus()
        self.storage = PostgresGraphStorage()
        self.graph = Graph()
        self.graph.set_loader(self.storage.load_context)
        self.kernel = Kernel(bus=self.bus, graph=self.graph)

    async def boot(self, modules: List[Type]) -> None:
        print("🔌 Application: Initializing infrastructure...")

        # 1. Infra mínima: conexión/pool
        await self.storage.get_pool()

        # 2. Carga constitucional del kernel
        self.kernel.load_modules(modules)

        # 3. Registry cerrado + schema + metadata técnica
        await self.kernel.prepare()

        # 4. Recién ahora restauramos memoria persistida
        await self._restore_graph_state()

        # 5. Cargar data y vistas
        await self.kernel.load_data()

        # 6. Poner módulos y servicios online
        await self.kernel.boot()

    async def _restore_graph_state(self):
        print("🧠 Restoring persisted graph state...")
        saved_graph = await self.storage.load()
        if saved_graph:
            self.graph._values = saved_graph._values
            self.graph._versions = saved_graph._versions
            print("   ✅ Graph state restored.")

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
        print("🔌 Application: Offline.")