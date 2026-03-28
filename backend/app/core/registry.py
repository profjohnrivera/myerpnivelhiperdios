# backend/app/core/registry.py
from typing import Dict, Type, Any, List, Optional
import re

class Registry:
    """
    🧠 EL CEREBRO DE METADATOS (Registry Mutante Nivel Dios)
    Fuente de verdad absoluta. Gestiona ADN, Herencia y Comportamientos (Mixins).
    """
    _models: Dict[str, Type] = {}
    _model_map: Dict[str, str] = {}
    _fields: Dict[str, Dict[str, Any]] = {}
    
    # 💎 NUEVO: Diccionario de Comportamientos (Behaviors)
    _model_behaviors: Dict[str, List[str]] = {} 
    
    _views: Dict[str, Dict[str, Any]] = {}
    _menus: Dict[str, Dict[str, Any]] = {}
    _modules: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_model(cls, model_cls: Type):
        """
        🧬 ASIMILACIÓN DE ADN (Pattern: Odoo Class Mutation)
        Registra el modelo en el cerebro y maneja la herencia técnica (_inherit).
        Permite que módulos externos extiendan modelos base sin modificar su código.
        """
        class_name = model_cls.__name__
        inherit_target = getattr(model_cls, '_inherit', None)
        
        # Resolvemos el nombre técnico (ej: 'res.users') usando el blindaje del Registry
        tech_name = getattr(model_cls, '_name', None) or cls._resolve_name(inherit_target or class_name)

        # 1. HERENCIA TÉCNICA (Mutación de Clase Odoo-Style)
        # Si detectamos _inherit, no creamos un modelo nuevo, sino que "parcheamos" el existente.
        if inherit_target:
            target_tech = cls._resolve_name(inherit_target)
            if target_tech in cls._models:
                base_class = cls._models[target_tech]
                print(f"   🧬 Mutando ADN: [{target_tech}] asimilando genes de {class_name}...")
                
                for attr, val in model_cls.__dict__.items():
                    # Evitamos sobreescribir atributos privados o descriptores de clase
                    if not attr.startswith('__') and attr not in ['_inherit', '_name']:
                        # Inyección de lógica/campos en la clase viva
                        setattr(base_class, attr, val)
                        
                        # Registro de metadatos en el diccionario de campos para el SyncEngine/SDUI
                        if hasattr(val, 'get_meta'):
                            cls.register_field(target_tech, attr, val.get_meta())
            return

        # 2. REGISTRO DE NUEVA ESPECIE (Modelo Base)
        if tech_name not in cls._models:
            cls._models[tech_name] = model_cls
            cls._model_map[class_name] = tech_name
            
            # Inicializamos el almacén de campos si es la primera vez que vemos el modelo
            if tech_name not in cls._fields: 
                cls._fields[tech_name] = {}
            
            # 💎 DETECCIÓN AUTOMÁTICA DE COMPORTAMIENTOS (Mixins)
            # El Registry escanea la jerarquía MRO para activar Auditoría, Estados o Secuencias.
            cls._scan_behaviors(tech_name, model_cls)
            
            # Log de sistema con los comportamientos asimilados
            behaviors = cls._model_behaviors.get(tech_name, [])
            behaviors_str = f"| Behaviors: {behaviors}" if behaviors else ""
            print(f"   🧠 Registrado: {tech_name} {behaviors_str}")

    @classmethod
    def _scan_behaviors(cls, tech_name: str, model_cls: Type):
        """Escanea la jerarquía de la clase para detectar Mixins conocidos."""
        behaviors = []
        # Obtenemos todos los nombres de las clases de las que hereda
        parents = [c.__name__ for c in model_cls.__mro__]
        
        if 'TrazableMixin' in parents: behaviors.append('trazable')
        if 'AprobableMixin' in parents: behaviors.append('aprobable')
        if 'SecuenciableMixin' in parents: behaviors.append('secuenciable')
        
        # También permitimos definición manual vía atributo
        manual = getattr(model_cls, '_behaviors', [])
        behaviors.extend([b for b in manual if b not in behaviors])
        
        if behaviors:
            cls._model_behaviors[tech_name] = behaviors

    @classmethod
    def get_behaviors(cls, model_name: str) -> List[str]:
        """Retorna la lista de comportamientos de un modelo."""
        tech_name = cls._resolve_name(model_name)
        return cls._model_behaviors.get(tech_name, [])

    @classmethod
    def register_field(cls, model_name: str, field_name: str, metadata: Dict):
        tech_name = cls._resolve_name(model_name)
        if tech_name not in cls._fields: cls._fields[tech_name] = {}
        cls._fields[tech_name][field_name] = metadata

    @classmethod
    def register_module(cls, name: str, icon: str, label: str):
        """Registra el lanzador de la aplicación en el Dashboard."""
        cls._modules[name] = {"id": name, "icon": icon, "label": label}
        print(f"   🚀 App Launcher: {label} [{name}] inicializado.")

    # =========================================================================
    # 🎨 MOTOR DE UI (Traductor Universal)
    # =========================================================================

    @classmethod
    def register_view(cls, view_obj: Any):
        """Registra vistas desde el DSL."""
        compiled = view_obj.compile()
        cls._views[compiled['id']] = compiled

    @classmethod
    def register_menu(cls, menu_obj: Any = None, **kwargs):
        """🗂️ REGISTRO DE MENÚS (Híbrido)"""
        if menu_obj and hasattr(menu_obj, 'compile'):
            compiled = menu_obj.compile()
        else:
            from app.core.ui import Menu
            m = Menu(
                id=kwargs.get('id') or f"menu_{kwargs.get('action') or 'root'}_{uuid_short()}",
                name=kwargs.get('label') or kwargs.get('name', 'Menu'),
                parent_id=kwargs.get('parent') or kwargs.get('parent_id'),
                action=kwargs.get('action'),
                icon=kwargs.get('icon'),
                sequence=kwargs.get('sequence', 10)
            )
            compiled = m.compile()
            
        cls._menus[compiled['id']] = compiled

    # =========================================================================
    # 🔍 CONSULTAS (SyncEngine & API)
    # =========================================================================

    @classmethod
    def get_all_models(cls) -> Dict[str, Type]:
        return cls._models

    @classmethod
    def get_model(cls, name: str) -> Type:
        if name == 'self': return None
        tech_name = cls._resolve_name(name)
        if tech_name in cls._models: return cls._models[tech_name]
        raise ValueError(f"❌ Modelo '{name}' no encontrado.")

    @classmethod
    def get_fields_for_model(cls, tech_name: str):
        return cls._fields.get(tech_name, {})

    @classmethod
    def _resolve_name(cls, name: str) -> str:
        if not name: return ""
        if name in cls._model_map: return cls._model_map[name]
        if name in cls._models: return name
        return re.sub(r'(?<!^)(?=[A-Z])', '.', name).lower()

    @classmethod
    def get_all_menus(cls):
        return sorted(cls._menus.values(), key=lambda x: x.get('sequence', 10))

def uuid_short():
    import uuid
    return str(uuid.uuid4())[:8]