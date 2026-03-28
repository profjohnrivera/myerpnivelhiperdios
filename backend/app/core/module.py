# backend/app/core/module.py
from typing import Type, Optional, List, Any

from app.core.registry import Registry
from app.core.event_bus import EventBus


class Module:
    """
    🧩 CONSTITUCIÓN BASE DE MÓDULOS
    Todos los módulos del ERP deben heredar de aquí.

    Reglas:
    - `name` es obligatorio
    - `depends` es la lista constitucional de dependencias
    - `register()` declara metadata, modelos, vistas y menús
    - `boot()` enciende servicios vivos del módulo
    """
    name: str = "base_module"
    depends: List[str] = []
    icon: str = "cube"
    label: str = "Módulo"

    def __init__(self, kernel=None):
        self.kernel = kernel
        self.bus = EventBus()

    # =========================================================================
    # 🧬 HELPERS DE REGISTRO
    # =========================================================================

    def register_model(self, model_cls: Type):
        """
        Registro idempotente.
        Si la clase ya fue registrada automáticamente por __init_subclass__,
        aquí solo consolidamos ownership del módulo.
        """
        Registry.register_model(model_cls, owner_module=self.name)

    def register_models(self, *model_classes: Type):
        for model_cls in model_classes:
            self.register_model(model_cls)

    def register_view(self, view_obj: Any):
        Registry.register_view(view_obj)

    def register_menu(self, menu_obj: Any = None, **kwargs):
        Registry.register_menu(menu_obj, **kwargs)

    def publish_meta(self, icon: Optional[str] = None, label: Optional[str] = None):
        self.bus.publish_meta(
            module=self.name,
            icon=icon or getattr(self, "icon", "cube"),
            label=label or getattr(self, "label", self.name.replace("_", " ").title()),
        )

    # =========================================================================
    # 🌱 CICLO DE VIDA
    # =========================================================================

    def register(self):
        """
        Debe ser sobrescrito por cada módulo.
        Aquí se registran app launcher, modelos, vistas y menús.
        """
        self.publish_meta()

    async def boot(self):
        """
        Hook opcional de arranque vivo.
        """
        return None

    async def shutdown(self):
        """
        Hook opcional de apagado.
        """
        return None