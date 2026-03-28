# backend/app/core/registry.py
from typing import Dict, Type, Any, List, Optional
import re


class Registry:
    """
    🧠 EL CEREBRO DE METADATOS (Registry Constitucional)
    Fuente de verdad absoluta. Gestiona ADN, herencia técnica, vistas,
    menús, ownership de modelos y comportamientos.

    💎 REGLA CLAVE:
    - Registrar dos veces LA MISMA clase NO debe romper.
    - Registrar OTRA clase distinta con el mismo nombre técnico SÍ debe romper.
    """
    _models: Dict[str, Type] = {}
    _model_map: Dict[str, str] = {}
    _fields: Dict[str, Dict[str, Any]] = {}
    _model_behaviors: Dict[str, List[str]] = {}
    _model_owner: Dict[str, str] = {}

    _views: Dict[str, Dict[str, Any]] = {}
    _menus: Dict[str, Dict[str, Any]] = {}
    _modules: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def reset(cls):
        cls._models = {}
        cls._model_map = {}
        cls._fields = {}
        cls._model_behaviors = {}
        cls._model_owner = {}
        cls._views = {}
        cls._menus = {}
        cls._modules = {}

    @classmethod
    def register_model(cls, model_cls: Type, owner_module: Optional[str] = None):
        """
        🧬 ASIMILACIÓN DE ADN (Pattern: Odoo Class Mutation)
        Registra el modelo en el cerebro y maneja la herencia técnica (_inherit).

        owner_module:
            nombre lógico del módulo dueño del modelo (core_base, mod_sales, etc.)
        """
        class_name = model_cls.__name__
        inherit_target = getattr(model_cls, "_inherit", None)

        tech_name = getattr(model_cls, "_name", None) or cls._resolve_name(inherit_target or class_name)

        # =========================================================================
        # 1. HERENCIA TÉCNICA (_inherit)
        # =========================================================================
        if inherit_target:
            target_tech = cls._resolve_name(inherit_target)
            if target_tech in cls._models:
                base_class = cls._models[target_tech]
                print(f"   🧬 Mutando ADN: [{target_tech}] asimilando genes de {class_name}...")

                for attr, val in model_cls.__dict__.items():
                    if not attr.startswith("__") and attr not in ["_inherit", "_name"]:
                        setattr(base_class, attr, val)

                        if hasattr(val, "get_meta"):
                            cls.register_field(target_tech, attr, val.get_meta())

                if owner_module and target_tech not in cls._model_owner:
                    cls._model_owner[target_tech] = owner_module
            return

        # =========================================================================
        # 2. REGISTRO DE NUEVA ESPECIE (Modelo Base)
        # =========================================================================
        if tech_name in cls._models:
            existing_cls = cls._models[tech_name]

            # 💎 FIX DEFINITIVO:
            # Si es la misma clase (o la misma identidad lógica), el registro repetido es inocuo.
            same_class = (
                existing_cls is model_cls or
                (
                    getattr(existing_cls, "__module__", None) == getattr(model_cls, "__module__", None)
                    and getattr(existing_cls, "__name__", None) == getattr(model_cls, "__name__", None)
                )
            )

            if same_class:
                # Actualizamos owner si antes no estaba definido
                if owner_module and tech_name not in cls._model_owner:
                    cls._model_owner[tech_name] = owner_module

                # Refrescamos alias de clase -> técnico
                cls._model_map[class_name] = tech_name

                # Aseguramos estructura de campos
                if tech_name not in cls._fields:
                    cls._fields[tech_name] = {}

                return

            # Colisión real: otra clase distinta intenta usar el mismo _name
            previous_owner = cls._model_owner.get(tech_name, "desconocido")
            incoming_owner = owner_module or "desconocido"
            raise RuntimeError(
                f"❌ Colisión de modelo: '{tech_name}' ya fue registrado por otra clase. "
                f"Owner actual: {previous_owner}. Nuevo owner: {incoming_owner}. "
                f"Clase actual: {existing_cls.__module__}.{existing_cls.__name__} | "
                f"Nueva clase: {model_cls.__module__}.{model_cls.__name__}"
            )

        cls._models[tech_name] = model_cls
        cls._model_map[class_name] = tech_name

        if tech_name not in cls._fields:
            cls._fields[tech_name] = {}

        if owner_module:
            cls._model_owner[tech_name] = owner_module

        cls._scan_behaviors(tech_name, model_cls)

        behaviors = cls._model_behaviors.get(tech_name, [])
        behaviors_str = f"| Behaviors: {behaviors}" if behaviors else ""
        print(f"   🧠 Registrado: {tech_name} {behaviors_str}")

    @classmethod
    def _scan_behaviors(cls, tech_name: str, model_cls: Type):
        """
        Escanea la jerarquía de la clase para detectar Mixins conocidos.
        """
        behaviors = []
        parents = [c.__name__ for c in model_cls.__mro__]

        if "TrazableMixin" in parents:
            behaviors.append("trazable")
        if "AprobableMixin" in parents:
            behaviors.append("aprobable")
        if "SecuenciableMixin" in parents:
            behaviors.append("secuenciable")

        manual = getattr(model_cls, "_behaviors", [])
        behaviors.extend([b for b in manual if b not in behaviors])

        if behaviors:
            cls._model_behaviors[tech_name] = behaviors

    @classmethod
    def get_behaviors(cls, model_name: str) -> List[str]:
        tech_name = cls._resolve_name(model_name)
        return cls._model_behaviors.get(tech_name, [])

    @classmethod
    def register_field(cls, model_name: str, field_name: str, metadata: Dict):
        tech_name = cls._resolve_name(model_name)
        if tech_name not in cls._fields:
            cls._fields[tech_name] = {}
        cls._fields[tech_name][field_name] = metadata

    @classmethod
    def register_module(cls, name: str, icon: str, label: str):
        """
        Registra el lanzador de la aplicación en el Dashboard.
        """
        cls._modules[name] = {"id": name, "icon": icon, "label": label}
        print(f"   🚀 App Launcher: {label} [{name}] inicializado.")

    # =========================================================================
    # 🎨 MOTOR DE UI
    # =========================================================================

    @classmethod
    def register_view(cls, view_obj: Any):
        compiled = view_obj.compile()
        cls._views[compiled["id"]] = compiled

    @classmethod
    def register_menu(cls, menu_obj: Any = None, **kwargs):
        if menu_obj and hasattr(menu_obj, "compile"):
            compiled = menu_obj.compile()
        else:
            from app.core.ui import Menu
            m = Menu(
                id=kwargs.get("id") or f"menu_{kwargs.get('action') or 'root'}_{uuid_short()}",
                name=kwargs.get("label") or kwargs.get("name", "Menu"),
                parent_id=kwargs.get("parent") or kwargs.get("parent_id"),
                action=kwargs.get("action"),
                icon=kwargs.get("icon"),
                sequence=kwargs.get("sequence", 10),
            )
            compiled = m.compile()

        cls._menus[compiled["id"]] = compiled

    # =========================================================================
    # 🔍 CONSULTAS
    # =========================================================================

    @classmethod
    def get_all_models(cls) -> Dict[str, Type]:
        return cls._models

    @classmethod
    def get_model(cls, name: str) -> Type:
        if name == "self":
            return None
        tech_name = cls._resolve_name(name)
        if tech_name in cls._models:
            return cls._models[tech_name]
        raise ValueError(f"❌ Modelo '{name}' no encontrado.")

    @classmethod
    def get_model_owner(cls, name: str) -> Optional[str]:
        tech_name = cls._resolve_name(name)
        return cls._model_owner.get(tech_name)

    @classmethod
    def get_fields_for_model(cls, tech_name: str):
        tech_name = cls._resolve_name(tech_name)
        return cls._fields.get(tech_name, {})

    @classmethod
    def get_all_fields(cls):
        return cls._fields

    @classmethod
    def get_all_menus(cls):
        return sorted(cls._menus.values(), key=lambda x: x.get("sequence", 10))

    @classmethod
    def get_all_views(cls):
        return cls._views

    @classmethod
    def _resolve_name(cls, name: str) -> str:
        if not name:
            return ""
        if name in cls._model_map:
            return cls._model_map[name]
        if name in cls._models:
            return name
        return re.sub(r"(?<!^)(?=[A-Z])", ".", name).lower()


def uuid_short():
    import uuid
    return str(uuid.uuid4())[:8]