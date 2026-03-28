# backend/app/core/view_engine.py
from typing import List, Dict, Any, Optional
from app.core.registry import Registry
from app.core.ui import Node

class ViewEngine:
    """
    🧬 THE EVOLUTION ENGINE (ViewEngine)
    Gestiona el ciclo de vida de la UI: Registro, Herencia y Parcheo.
    Permite que un módulo modifique la vista de otro sin tocar el código original.
    """

    @classmethod
    async def get_view_arch(cls, view_id: str) -> dict:
        """
        Obtiene la arquitectura final de una vista tras aplicar todas las herencias.
        """
        # 1. Buscar la vista base en el Registry
        base_view = Registry.get_ui_view(view_id)
        if not base_view:
            raise ValueError(f"❌ Vista '{view_id}' no encontrada en el Registry.")

        # 2. Si la vista es una extensión (tiene _inherit), buscamos su padre primero
        # Pero aquí implementamos la lógica inversa: buscar quién hereda de MÍ.
        arch_dict = base_view.arch.compile()

        # 3. Buscar extensiones (parches) registradas para esta vista
        extensions = Registry.get_view_extensions(view_id)
        
        # Ordenamos las extensiones por prioridad (opcional)
        for ext in extensions:
            print(f"   🧬 Aplicando parche de ADN: {ext.id} -> {view_id}")
            arch_dict = cls._apply_patch(arch_dict, ext.patch_logic)

        return {
            "id": base_view.id,
            "model": base_view.model,
            "name": base_view.name,
            "arch": arch_dict
        }

    @classmethod
    def _apply_patch(cls, arch: dict, patch_logic: List[Dict]) -> dict:
        """
        Aplica lógica tipo 'XPath' sobre el diccionario compilado.
        Ejemplo de patch_logic:
        [{"action": "insert", "tag": "Field", "target": "partner_id", "position": "after", "node": Node}]
        """
        for patch in patch_logic:
            action = patch.get("action")
            target_name = patch.get("target")
            new_node = patch.get("node")
            
            # Buscamos el nodo objetivo recursivamente y aplicamos la mutación
            cls._find_and_mutate(arch, target_name, action, new_record=new_node.compile())
            
        return arch

    @classmethod
    def _find_and_mutate(cls, parent: dict, target_name: str, action: str, new_record: dict):
        """Navega por el árbol compilado para inyectar o modificar nodos."""
        if "children" in parent:
            for idx, child in enumerate(parent["children"]):
                if child.get("name") == target_name:
                    if action == "after":
                        parent["children"].insert(idx + 1, new_record)
                        return True
                    elif action == "before":
                        parent["children"].insert(idx, new_record)
                        return True
                    elif action == "replace":
                        parent["children"][idx] = new_record
                        return True
                # Seguir buscando en profundidad
                if cls._find_and_mutate(child, target_name, action, new_record):
                    return True
        
        # Soporte para Notebooks (pages)
        if "pages" in parent:
            for page in parent["pages"]:
                if cls._find_and_mutate(page, target_name, action, new_record):
                    return True
        return False