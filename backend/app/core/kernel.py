# backend/app/core/kernel.py
import asyncio
import traceback
import importlib
import pkgutil
import os
from typing import Dict, Type, List, Any, Optional
from app.core.event_bus import EventBus
from app.core.graph import Graph
from app.core.orm import Model
from app.core.worker import WorkerEngine
from app.core.registry import Registry
from app.core.env import Context

class Kernel:
    """
    🧠 EL NÚCLEO (BIOS) DEL ERP.
    Orquesta la vida, seguridad y comunicación de todos los módulos.
    Gestiona el ciclo de vida asíncrono y la integridad del ecosistema.
    """
    def __init__(self, bus: Optional[EventBus] = None, graph: Optional[Graph] = None) -> None:
        self.bus = bus or EventBus()
        self.graph = graph or Graph()
        
        # Inyección global para que el ORM opere sobre la misma instancia de memoria
        Model._graph = self.graph
        
        self.modules: Dict[str, Any] = {}
        self._booted = False

    def load_modules(self, module_classes: List[Type]) -> None:
        """
        Fase 1: CARGA Y REGISTRO
        Inyecta el kernel en cada módulo para permitir la comunicación inter-modular.
        """
        # Ordenar: core_system siempre primero para garantizar infraestructura base
        ordered_classes = sorted(
            module_classes, 
            key=lambda x: 0 if getattr(x, 'name', '') == 'core_system' else 1
        )

        print(f"🧠 Kernel: Initializing {len(ordered_classes)} modules...")

        for module_cls in ordered_classes:
            mod_name = getattr(module_cls, 'name', 'unknown')
            
            if mod_name in self.modules:
                continue

            try:
                # 💎 EL FIX: Pasamos 'self' (el kernel) a la instancia del módulo
                instance = module_cls(kernel=self) 
                
                self._verify_dependencies(module_cls)
                
                self.modules[mod_name] = instance
                instance.register() # Registro de clases en el Registry
                print(f"   🔹 Registered: {mod_name}")
                
            except Exception as e:
                print(f"   ❌ CRITICAL ERROR registering module '{mod_name}': {e}")
                if mod_name == 'core_system':
                    raise RuntimeError("🔥 Failed to load Core System. Shutdown sequence initiated.")

    async def boot(self) -> None:
        """
        Fase 2: ARRANQUE VIVO (Asíncrono)
        Activa los servicios de fondo y pone a los módulos en línea mediante autodescubrimiento.
        """
        if self._booted:
            return

        print("🚀 Kernel: Booting services...")
        
        # 1. Despertar al Obrero (Worker Engine) para tareas pesadas
        asyncio.create_task(WorkerEngine.run())
        
        # 2. Despertar al Auditor Universal (Ojo de Sauron)
        from app.core.auditor import AuditService
        await AuditService.bootstrap()
        
        # 3. 💎 AUTODESCUBRIMIENTO PROFUNDO (Models -> DB -> Data -> Views)
        # Primero cargamos el ADN de todos para que el Registry esté completo
        for mod_name in self.modules.keys():
            await self._load_subpackage(mod_name, "models")

        # Sincronizamos el esquema físico de PostgreSQL con el Registry completo
        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        await storage.sync_schema()

        # Inyectamos datos de configuración y vistas (Data-as-Code)
        for mod_name in self.modules.keys():
            # El Ingestor ahora escanea toda la carpeta data/
            await self._execute_init_data(mod_name)
            await self._load_subpackage(mod_name, "views")

        # 4. Sincronizar ADN de módulos (Mapeo Disco -> DB en ir.module)
        await self._sync_module_records()

        print("🚀 Kernel: Putting modules online...")
        for name, module in self.modules.items():
            try:
                if asyncio.iscoroutinefunction(module.boot):
                    await module.boot()
                else:
                    module.boot()
                print(f"   ✅ {name} is online.")
            except Exception:
                print(f"   ⚠️  FAILED TO BOOT MODULE '{name}':")
                print(traceback.format_exc())

        self._booted = True
        print("✨ Kernel: System is fully operational.")

    async def _load_subpackage(self, module_name: str, subpackage: str):
        """
        🧬 ESCANER DE ADN
        Importa dinámicamente subpaquetes (models, views, etc.).
        """
        try:
            full_package_path = f"modules.{module_name}.{subpackage}"
            package = importlib.import_module(full_package_path)
            
            if hasattr(package, "__path__"):
                for _, name, _ in pkgutil.iter_modules(package.__path__):
                    importlib.import_module(f"{full_package_path}.{name}")
        except ImportError:
            pass

    async def _execute_init_data(self, module_name: str):
        """
        💿 INGESTIÓN DATA-AS-CODE RECURSIVA
        Escanea la carpeta data/ y ejecuta cualquier función que empiece con 'init_'.
        """
        try:
            data_package_path = f"modules.{module_name}.data"
            try:
                data_package = importlib.import_module(data_package_path)
            except ImportError:
                return # Sin carpeta de datos, saltamos

            from app.core.env import Env
            env = Env(user_id="system", graph=self.graph) # Entorno de sistema

            # 🔎 ESCANEO DINÁMICO DE ARCHIVOS EN /data/
            if hasattr(data_package, "__path__"):
                for _, sub_name, _ in pkgutil.iter_modules(data_package.__path__):
                    sub_mod = importlib.import_module(f"{data_package_path}.{sub_name}")
                    
                    # Buscamos funciones de inicialización (ej. init_menus, init_rules)
                    for func_name in dir(sub_mod):
                        if func_name.startswith("init_"):
                            func = getattr(sub_mod, func_name)
                            if asyncio.iscoroutinefunction(func):
                                print(f"   💿 [INGESTOR] {module_name} -> {sub_name}.{func_name}")
                                await func(env)
            
            # Ejecución de init_data principal si existe en __init__.py
            if hasattr(data_package, 'init_data'):
                await data_package.init_data(env)

        except Exception as e:
            print(f"   ⚠️  Error in data ingestion for {module_name}: {e}")

    async def _sync_module_records(self):
        """
        🧬 SINCRONIZACIÓN DE REGISTROS TÉCNICOS
        Registra la instalación física de los módulos en el Grafo.
        """
        try:
            IrModule = Registry.get_model('ir.module')
            for mod_name in self.modules.keys():
                existing = await IrModule.search([('name', '=', mod_name)])
                if not existing:
                    await IrModule.create({
                        'name': mod_name,
                        'state': 'installed',
                        'shortdesc': mod_name.replace('_', ' ').title(),
                        'version': '1.0.0'
                    })
        except Exception as e:
            print(f"   ⚠️  Module Sync: {e} (Ignoring during cold boot)")

    def _verify_dependencies(self, module_cls: Type) -> None:
        deps = getattr(module_cls, 'dependencies', [])
        for dep in deps:
            if dep not in self.modules:
                print(f"   ⚠️  Warning: Module '{module_cls.name}' depends on '{dep}' which is not yet registered.")

    def get_module(self, name: str) -> Any:
        if name not in self.modules:
            raise ValueError(f"Module '{name}' not loaded.")
        return self.modules[name]

    def shutdown(self) -> None:
        print("🔌 Kernel: Initiating graceful shutdown...")
        WorkerEngine.stop()
        self._booted = False
        print("🔌 Kernel: Offline.")