# backend/app/core/application.py
from typing import List, Type, Any
from app.core.kernel import Kernel
from app.core.event_bus import EventBus
from app.core.graph import Graph
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.env import Context 

class Application:
    """
    🏗️ LA NAVE NODRIZA (Application)
    Orquesta la integración entre la Infraestructura (DB), la Memoria (Graph) 
    y la Lógica (Kernel). Es el punto de entrada único para el ciclo de vida del ERP.
    """
    def __init__(self) -> None:
        # 1. Infraestructura Base
        self.bus = EventBus()
        self.storage = PostgresGraphStorage()
        
        # 2. El Grafo (Memoria RAM del Sistema)
        self.graph = Graph()
        # Conectamos el loader de la DB al grafo para Lazy Loading inteligente
        self.graph.set_loader(self.storage.load_context) 

        # 3. El Kernel (El Cerebro)
        self.kernel = Kernel(bus=self.bus, graph=self.graph)

    async def boot(self, modules: List[Type]) -> None:
        """
        🚀 SECUENCIA DE ARRANQUE (Nivel HiperDios)
        Asegura que la realidad física y la memoria estén sincronizadas.
        """
        print("🔌 Application: Initializing Infrastructure...")
        
        # A. Inicializar la Base de Datos (Tablas y Esquema)
        await self.storage.init_db()
        
        # 🔥 RESTAURACIÓN DE MEMORIA
        # Recuperamos los valores y versiones guardados para que el ERP 
        # tenga continuidad entre reinicios.
        print("🧠 Restaurando memoria del Grafo desde Base de Datos...")
        saved_graph = await self.storage.load()
        if saved_graph:
            self.graph._values = saved_graph._values
            self.graph._versions = saved_graph._versions
            print("   ✅ Memoria recuperada con éxito.")
        
        # B. Carga Topológica de Módulos
        # Esto registra modelos, campos y resuelve dependencias.
        self.kernel.load_modules(modules)
        
        # C. Encender Motores
        # 💎 EL FIX: Agregamos el 'await' para que el Kernel pueda despertar al Worker y servicios.
        await self.kernel.boot()

    async def emit(self, event: Any) -> None:
        """
        📡 Interface pública para main.py y APIs.
        Maneja la publicación del evento y garantiza la persistencia atómica post-proceso.
        """
        try:
            # 1. Ejecutar el evento (Handlers / Business Logic)
            await self.bus.publish(event)
            
            # 2. Persistencia Automática
            # Si el evento fluyó bien, consolidamos los cambios en Postgres.
            await self.storage.save(self.graph)
            
        except Exception as e:
            # 🛡️ Red de Seguridad Crítica
            print(f"🔥 CRITICAL SYSTEM FAILURE: Event processing failed: {e}")
            # Aquí podrías implementar un sistema de alertas o logs de emergencia
            raise e

    async def shutdown(self) -> None:
        """🔌 APAGADO GRACIOSO (Graceful Shutdown)"""
        print("🔌 Application: Initiating graceful shutdown...")
        await self.kernel.shutdown()
        if hasattr(self.storage, 'pool'):
            await self.storage.pool.close()
        print("🔌 Application: Offline.")