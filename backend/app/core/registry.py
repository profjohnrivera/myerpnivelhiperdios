# backend/app/core/registry.py
from typing import Dict, Type, Any, List, Optional
import re


class Registry:
    """
    🧠 EL CEREBRO DE METADATOS (Registry Constitucional)

    Reglas duras:
    - Re-registrar la MISMA clase es idempotente.
    - Registrar OTRA clase distinta con el mismo nombre técnico rompe.
    - Después de freeze(), ya no se permiten cambios de schema
      (modelos, _inherit, campos técnicos).
    - El plano UI (views/menus) sigue abierto después de freeze()
      porque se carga en Kernel.load_data().
    """

    _models: Dict[str, Type] = {}
    _model_map: Dict[str, str] = {}
    _fields: Dict[str, Dict[str, Any]] = {}
    _model_behaviors: Dict[str, List[str]] = {}
    _model_owner: Dict[str, str] = {}

    _views: Dict[str, Dict[str, Any]] = {}
    _menus: Dict[str, Dict[str, Any]] = {}
    _modules: Dict[str, Dict[str, Any]] = {}

    _frozen: bool = False

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
        cls._frozen = False

    # =========================================================================
    # 🔒 CICLO DE VIDA CONSTITUCIONAL
    # =========================================================================

    @classmethod
    def freeze(cls):
        """Sella únicamente la capa de schema/metamodelo."""
        cls._frozen = True

    @classmethod
    def unfreeze(cls):
        """Solo para tests, bootstrap controlado o reset explícito."""
        cls._frozen = False

    @classmethod
    def is_frozen(cls) -> bool:
        return cls._frozen

    @classmethod
    def _ensure_schema_mutable(cls, action: str):
        if cls._frozen:
            raise RuntimeError(
                f"❌ Registry sellado: no se puede {action} después de Kernel.prepare()."
            )

    # =========================================================================
    # 🧬 MODELOS
    # =========================================================================

    @classmethod
    def register_model(cls, model_cls: Type, owner_module: Optional[str] = None):
        class_name = model_cls.__name__
        inherit_target = getattr(model_cls, "_inherit", None)
        tech_name = getattr(model_cls, "_name", None) or cls._resolve_name(class_name)

        # -------------------------
        # HERENCIA TÉCNICA (_inherit)
        # -------------------------
        if inherit_target:
            target_tech = cls._resolve_name(inherit_target)

            if target_tech not in cls._models:
                raise RuntimeError(
                    f"❌ Herencia inválida: '{class_name}' declara _inherit='{inherit_target}' "
                    f"pero el modelo base '{target_tech}' aún no existe en Registry."
                )

            cls._ensure_schema_mutable(
                f"mutar ADN del modelo '{target_tech}' con '{class_name}'"
            )

            base_class = cls._models[target_tech]
            print(f"   🧬 Mutando ADN: [{target_tech}] asimilando genes de {class_name}...")

            for attr, val in model_cls.__dict__.items():
                if not attr.startswith("__") and attr not in ["_inherit", "_name"]:
                    setattr(base_class, attr, val)

                    if hasattr(val, "get_meta"):
                        cls.register_field(target_tech, attr, val.get_meta())

            if owner_module and target_tech not in cls._model_owner:
                cls._model_owner[target_tech] = owner_module

            cls._model_map[class_name] = target_tech
            cls._fields.setdefault(target_tech, {})
            cls._scan_behaviors(target_tech, base_class)
            return

        # -------------------------
        # REGISTRO DE MODELO BASE
        # -------------------------
        if tech_name in cls._models:
            existing_cls = cls._models[tech_name]

            same_class = (
                existing_cls is model_cls or
                (
                    getattr(existing_cls, "__module__", None) == getattr(model_cls, "__module__", None)
                    and getattr(existing_cls, "__name__", None) == getattr(model_cls, "__name__", None)
                )
            )

            if same_class:
                if owner_module and tech_name not in cls._model_owner:
                    cls._model_owner[tech_name] = owner_module

                cls._model_map[class_name] = tech_name
                cls._fields.setdefault(tech_name, {})
                return

            previous_owner = cls._model_owner.get(tech_name, "desconocido")
            incoming_owner = owner_module or "desconocido"
            raise RuntimeError(
                f"❌ Colisión de modelo: '{tech_name}' ya fue registrado por otra clase. "
                f"Owner actual: {previous_owner}. Nuevo owner: {incoming_owner}. "
                f"Clase actual: {existing_cls.__module__}.{existing_cls.__name__} | "
                f"Nueva clase: {model_cls.__module__}.{model_cls.__name__}"
            )

        cls._ensure_schema_mutable(f"registrar modelo '{tech_name}'")

        cls._models[tech_name] = model_cls
        cls._model_map[class_name] = tech_name
        cls._fields.setdefault(tech_name, {})

        if owner_module:
            cls._model_owner[tech_name] = owner_module

        cls._scan_behaviors(tech_name, model_cls)

        behaviors = cls._model_behaviors.get(tech_name, [])
        behaviors_str = f"| Behaviors: {behaviors}" if behaviors else ""
        print(f"   🧠 Registrado: {tech_name} {behaviors_str}")

    @classmethod
    def _scan_behaviors(cls, tech_name: str, model_cls: Type):
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
        return list(cls._model_behaviors.get(tech_name, []))

    @classmethod
    def register_field(cls, model_name: str, field_name: str, metadata: Dict):
        tech_name = cls._resolve_name(model_name)
        cls._fields.setdefault(tech_name, {})

        existing = cls._fields[tech_name].get(field_name)
        if existing == metadata:
            return

        if existing is not None:
            cls._ensure_schema_mutable(
                f"redefinir campo '{field_name}' en modelo '{tech_name}'"
            )
        else:
            cls._ensure_schema_mutable(
                f"registrar campo '{field_name}' en modelo '{tech_name}'"
            )

        cls._fields[tech_name][field_name] = metadata

    @classmethod
    def register_module(cls, name: str, icon: str, label: str):
        cls._modules[name] = {"id": name, "icon": icon, "label": label}
        print(f"   🚀 App Launcher: {label} [{name}] inicializado.")

    # =========================================================================
    # 🎨 UI
    # =========================================================================

    @classmethod
    def register_view(cls, view_obj: Any):
        compiled = view_obj.compile()
        cls._views[compiled["id"]] = compiled

    @classmethod
    def register_menu(cls, menu_obj: Any = None, **kwargs):
        raise RuntimeError(
            "❌ Registry.register_menu() está deshabilitado por arquitectura. "
            "Usa ir.ui.menu persistido desde modules/<mod>/data/menus.py."
        )

    # =========================================================================
    # 🔍 CONSULTAS
    # =========================================================================

    @classmethod
    def get_all_models(cls) -> Dict[str, Type]:
        return dict(cls._models)

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
        return dict(cls._fields.get(tech_name, {}))

    @classmethod
    def get_all_fields(cls):
        return {model: dict(fields) for model, fields in cls._fields.items()}

    @classmethod
    def get_all_menus(cls) -> List[Dict[str, Any]]:
        """
        Menús en memoria desactivados.
        La única fuente de verdad es ir.ui.menu en BD.
        """
        return []

    @classmethod
    def get_all_views(cls):
        return {k: dict(v) for k, v in cls._views.items()}

    @classmethod
    def get_all_modules(cls):
        return {k: dict(v) for k, v in cls._modules.items()}

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