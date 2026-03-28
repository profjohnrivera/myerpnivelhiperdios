# backend/app/core/kernel.py
import asyncio
import importlib
import pkgutil
import traceback
from typing import Any, Dict, List, Optional, Type

from app.core.env import Env
from app.core.event_bus import EventBus
from app.core.graph import Graph
from app.core.orm import Model
from app.core.registry import Registry
from app.core.worker import WorkerEngine


class Kernel:
    """
    Constitución única del núcleo.
    """

    def __init__(self, bus: Optional[EventBus] = None, graph: Optional[Graph] = None) -> None:
        self.bus = bus or EventBus()
        self.graph = graph or Graph()

        Model._graph = self.graph

        self.modules: Dict[str, Any] = {}
        self._module_order: List[str] = []
        self._prepared = False
        self._booted = False

    def load_modules(self, module_classes: List[Type]) -> None:
        """
        Recibe módulos YA ordenados por DAG y NO los reordena.
        """
        if self.modules:
            return

        print(f"🧠 Kernel: Initializing {len(module_classes)} modules...")

        for module_cls in module_classes:
            self._verify_module_contract(module_cls)
            self._verify_dependencies(module_cls)

            mod_name = module_cls.name
            instance = module_cls(kernel=self)

            # Importar models antes del register para que el módulo registre conscientemente
            self._import_optional_subpackage(mod_name, "models")

            self.modules[mod_name] = instance
            self._module_order.append(mod_name)

            instance.register()
            print(f"   🔹 Registered: {mod_name}")

    async def prepare(self) -> None:
        """
        Registry cerrado, schema sincronizado y metadata técnica persistida.
        """
        if self._prepared:
            return

        if not self.modules:
            raise RuntimeError("❌ No hay módulos cargados en el kernel.")

        # Garantía fundacional antes del freeze/sync
        self._ensure_foundational_models()

        Registry.freeze()

        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()

        print("🛠️ Kernel: Syncing physical schema...")
        await storage.sync_schema()

        print("🧠 Kernel: Syncing technical metadata...")
        await self._sync_registry_metadata()
        await self._sync_module_records()

        self._prepared = True

    async def load_data(self) -> None:
        """
        Carga vistas e init data después de tener registry y schema consistentes.
        """
        if not self._prepared:
            raise RuntimeError("❌ Kernel.prepare() debe ejecutarse antes de load_data().")

        print("💿 Kernel: Loading views and data...")
        for mod_name in self._module_order:
            self._import_optional_subpackage(mod_name, "views")
            await self._execute_init_data(mod_name)

    async def boot(self) -> None:
        """
        Pone módulos online y luego despierta servicios.
        """
        if self._booted:
            return

        if not self._prepared:
            raise RuntimeError("❌ Kernel.prepare() debe ejecutarse antes de boot().")

        print("🚀 Kernel: Putting modules online...")
        for mod_name in self._module_order:
            module = self.modules[mod_name]
            try:
                if asyncio.iscoroutinefunction(module.boot):
                    await module.boot()
                else:
                    result = module.boot()
                    if asyncio.iscoroutine(result):
                        await result
                print(f"   ✅ {mod_name} is online.")
            except Exception:
                print(f"   ⚠️ FAILED TO BOOT MODULE '{mod_name}':")
                print(traceback.format_exc())
                raise

        # Servicios al final, cuando el schema ya existe
        from app.core.auditor import AuditService
        await AuditService.bootstrap()
        asyncio.create_task(WorkerEngine.run())

        self._booted = True
        print("✨ Kernel: System is fully operational.")

    async def shutdown(self) -> None:
        print("🔌 Kernel: Initiating graceful shutdown...")

        for mod_name in reversed(self._module_order):
            module = self.modules[mod_name]
            try:
                if hasattr(module, "shutdown"):
                    if asyncio.iscoroutinefunction(module.shutdown):
                        await module.shutdown()
                    else:
                        result = module.shutdown()
                        if asyncio.iscoroutine(result):
                            await result
            except Exception:
                print(f"⚠️ Error during shutdown of module '{mod_name}'")

        WorkerEngine.stop()
        self._booted = False
        print("🔌 Kernel: Offline.")

    def get_module(self, name: str) -> Any:
        if name not in self.modules:
            raise ValueError(f"Module '{name}' not loaded.")
        return self.modules[name]

    def _verify_module_contract(self, module_cls: Type) -> None:
        if not getattr(module_cls, "name", None):
            raise RuntimeError(f"❌ Módulo inválido: {module_cls} no define 'name'.")
        depends = getattr(module_cls, "depends", [])
        if not isinstance(depends, list):
            raise RuntimeError(f"❌ El módulo '{module_cls.name}' debe definir depends como lista.")

    def _verify_dependencies(self, module_cls: Type) -> None:
        deps = getattr(module_cls, "depends", []) or []
        for dep in deps:
            if dep not in self.modules:
                raise RuntimeError(
                    f"❌ No se puede registrar '{module_cls.name}': "
                    f"la dependencia '{dep}' aún no está cargada."
                )

    def _import_optional_subpackage(self, module_name: str, subpackage: str) -> bool:
        """
        Solo tolera el caso 'subpackage no existe'.
        Si existe y falla, aborta.
        """
        full_package_path = f"modules.{module_name}.{subpackage}"

        try:
            package = importlib.import_module(full_package_path)
        except ModuleNotFoundError as e:
            if e.name == full_package_path:
                return False
            raise RuntimeError(
                f"❌ Fallo importando dependencias internas de {full_package_path}: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"❌ Error importando {full_package_path}: {e}") from e

        if hasattr(package, "__path__"):
            for _, name, _ in pkgutil.iter_modules(package.__path__):
                child_module = f"{full_package_path}.{name}"
                try:
                    importlib.import_module(child_module)
                except Exception as e:
                    raise RuntimeError(f"❌ Error importando {child_module}: {e}") from e

        return True

    def _ensure_foundational_models(self) -> None:
        """
        Garantiza que modelos base y técnicos existan en Registry
        antes de freeze/sync/init_data.
        """

        # =========================
        # CORE BASE
        # =========================
        if "core_base" in self.modules:
            try:
                from modules.core_base.models.res_partner import ResPartner
                from modules.core_base.models.res_company import ResCompany
                from modules.core_base.models.res_users import ResUsers
                from modules.core_base.models.res_groups import ResGroups
            except Exception as e:
                raise RuntimeError(f"❌ No se pudieron importar los modelos base de core_base: {e}") from e

            base_models = {
                "res.partner": ResPartner,
                "res.company": ResCompany,
                "res.users": ResUsers,
                "res.groups": ResGroups,
            }

            for tech_name, model_cls in base_models.items():
                try:
                    Registry.get_model(tech_name)
                except Exception:
                    Registry.register_model(model_cls, owner_module="core_base")

        # =========================
        # CORE SYSTEM
        # =========================
        if "core_system" in self.modules:
            try:
                from modules.core_system.models.ir_model import IrModel
                from modules.core_system.models.ir_model_fields import IrModelFields
                from modules.core_system.models.ir_rule import IrRule
                from modules.core_system.models.ir_sequence import IrSequence
                from modules.core_system.models.ir_model_data import IrModelData
                from modules.core_system.models.ir_model_access import IrModelAccess
                from modules.core_system.models.ir_ui_view import IrUiView
                from modules.core_system.models.ir_ui_menu import IrUiMenu
                from modules.core_system.models.ir_module import IrModule, IrModuleDependency
                from modules.core_system.models.ir_config_parameter import IrConfigParameter
                from modules.core_system.models.ir_actions import IrActionsServer, IrActionsActWindow
                from modules.core_system.models.ir_queue import IrQueue
            except Exception as e:
                raise RuntimeError(f"❌ No se pudieron importar los modelos técnicos de core_system: {e}") from e

            core_models = {
                "ir.model": IrModel,
                "ir.model.fields": IrModelFields,
                "ir.rule": IrRule,
                "ir.sequence": IrSequence,
                "ir.model.data": IrModelData,
                "ir.model.access": IrModelAccess,
                "ir.ui.view": IrUiView,
                "ir.ui.menu": IrUiMenu,
                "ir.module": IrModule,
                "ir.module.dependency": IrModuleDependency,
                "ir.config_parameter": IrConfigParameter,
                "ir.actions.server": IrActionsServer,
                "ir.actions.act_window": IrActionsActWindow,
                "ir.queue": IrQueue,
            }

            for tech_name, model_cls in core_models.items():
                try:
                    Registry.get_model(tech_name)
                except Exception:
                    Registry.register_model(model_cls, owner_module="core_system")

    async def _execute_init_data(self, module_name: str):
        data_package_path = f"modules.{module_name}.data"

        try:
            data_package = importlib.import_module(data_package_path)
        except ModuleNotFoundError as e:
            if e.name == data_package_path:
                return
            raise RuntimeError(f"❌ Error importando {data_package_path}: {e}") from e

        env = Env(user_id="system", graph=self.graph)

        if hasattr(data_package, "__path__"):
            for _, sub_name, _ in pkgutil.iter_modules(data_package.__path__):
                sub_mod = importlib.import_module(f"{data_package_path}.{sub_name}")
                for func_name in dir(sub_mod):
                    if func_name.startswith("init_"):
                        func = getattr(sub_mod, func_name)
                        print(f"   💿 [INGESTOR] {module_name} -> {sub_name}.{func_name}")
                        if asyncio.iscoroutinefunction(func):
                            await func(env)
                        else:
                            result = func(env)
                            if asyncio.iscoroutine(result):
                                await result

        if hasattr(data_package, "init_data"):
            func = getattr(data_package, "init_data")
            if asyncio.iscoroutinefunction(func):
                await func(env)
            else:
                result = func(env)
                if asyncio.iscoroutine(result):
                    await result

    async def _sync_registry_metadata(self):
        """
        Ejecuta el sincronizador técnico oficial del registry si existe.
        """
        try:
            sync_mod = importlib.import_module("modules.core_system.data.registry_sync")
            sync_func = getattr(sync_mod, "sync_models_and_fields", None)
            if sync_func:
                env = Env(user_id="system", graph=self.graph)
                if asyncio.iscoroutinefunction(sync_func):
                    await sync_func(env)
                else:
                    result = sync_func(env)
                    if asyncio.iscoroutine(result):
                        await result
        except ModuleNotFoundError:
            return

    async def _sync_module_records(self):
        try:
            IrModule = Registry.get_model("ir.module")
            Env(user_id="system", graph=self.graph)

            for mod_name in self._module_order:
                existing = await IrModule.search([("name", "=", mod_name)])
                if not existing:
                    await IrModule.create({
                        "name": mod_name,
                        "state": "installed",
                        "shortdesc": mod_name.replace("_", " ").title(),
                        "version": "1.0.0",
                    })
        except Exception as e:
            print(f"⚠️ Module sync skipped: {e}")