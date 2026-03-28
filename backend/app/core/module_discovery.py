# backend/app/core/module_discovery.py
import pkgutil
import importlib
import inspect
import os
import sys
from typing import List, Type
from app.core.module import Module

def sort_modules_topologically(modules: List[Type[Module]]) -> List[Type[Module]]:
    """
    🧠 KERNEL DAG (Directed Acyclic Graph)
    Ordena los módulos matemáticamente basándose en sus dependencias.
    Garantiza que ningún módulo 'hijo' cargue antes que su 'padre'.
    """
    # 1. Crear diccionario de módulos usando su atributo 'name'
    modules_dict = {mod.name: mod for mod in modules if hasattr(mod, 'name')}
    
    in_degree = {name: 0 for name in modules_dict}
    adj_list = {name: [] for name in modules_dict}

    # 2. Construir el Grafo de Adyacencia
    for name, mod_cls in modules_dict.items():
        depends = getattr(mod_cls, 'depends', [])
        for dep in depends:
            if dep in modules_dict:
                adj_list[dep].append(name)
                in_degree[name] += 1
            else:
                print(f"⚠️ Warning Kernel: La dependencia '{dep}' requerida por '{name}' no existe o falló al cargar.")

    # 3. Inicializar la cola con los módulos base (que no dependen de nadie, in_degree == 0)
    queue = [name for name in in_degree if in_degree[name] == 0]
    sorted_modules = []

    # 4. Ordenamiento Topológico (Algoritmo de Kahn)
    while queue:
        current = queue.pop(0)
        sorted_modules.append(modules_dict[current])
        
        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 5. Detección de Ciclos (Ej: A depende de B, y B depende de A)
    if len(sorted_modules) != len(modules_dict):
        raise Exception("❌ ERROR CRÍTICO DEL KERNEL: ¡Dependencia circular detectada entre los módulos! El ERP no puede arrancar.")

    return sorted_modules


def discover_modules(modules_dir_name: str = "modules") -> List[Type[Module]]:
    """
    Escanea la carpeta de forma robusta, descubre las clases Module y las devuelve ordenadas.
    """
    found_modules = []
    
    # 1. Resolver Rutas Absolutas (Para que funcione desde cualquier lado)
    current_file_path = os.path.abspath(__file__)
    app_core_dir = os.path.dirname(current_file_path)
    app_dir = os.path.dirname(app_core_dir)
    backend_dir = os.path.dirname(app_dir) # Raíz del backend
    
    # Ruta completa a la carpeta modules
    modules_path = os.path.join(backend_dir, modules_dir_name)

    # Aseguramos que el backend esté en el path para los imports
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    if not os.path.exists(modules_path):
        print(f"⚠️ Warning: Modules directory '{modules_path}' not found.")
        return []

    print(f"🔎 Scanning for modules in '{modules_path}'...")

    # 2. Iterar sobre los subdirectorios
    for _, name, is_pkg in pkgutil.iter_modules([modules_path]):
        if is_pkg:
            module_spec = f"{modules_dir_name}.{name}.module"
            
            try:
                # 3. Intentar importar
                lib = importlib.import_module(module_spec)

            except ModuleNotFoundError as e:
                if e.name == module_spec or e.name == module_spec.split(".")[-1]:
                    # No existe module.py en esta carpeta, seguimos.
                    continue
                else:
                    # El archivo existe, pero le falta una dependencia interna. ¡Error real!
                    print(f"   ❌ CRITICAL: Module '{name}' found but failed to load dependencies: {e}")
                    continue

            except Exception as e:
                # Cualquier otro error (SyntaxError, ValueError) dentro del módulo
                print(f"   ❌ CRITICAL: Error loading module '{name}': {e}")
                continue

            # 4. Buscar la clase
            loaded = False
            for attribute_name in dir(lib):
                attribute = getattr(lib, attribute_name)
                
                if (inspect.isclass(attribute) and 
                    issubclass(attribute, Module) and 
                    attribute is not Module):
                    
                    # Lo guardamos silenciosamente para ordenarlo después
                    found_modules.append(attribute)
                    loaded = True
                    break # Solo permitimos una clase Module por archivo
            
            if not loaded:
                pass

    # 💎 EL FIX: Pasamos los módulos descubiertos por el motor matemático
    sorted_modules = sort_modules_topologically(found_modules)
    
    # Imprimimos el orden real de carga para confirmar que el DAG funcionó
    print("🧬 Secuencia de Carga Topológica Resuelta:")
    for mod in sorted_modules:
        print(f"   ✅ {mod.name}")

    return sorted_modules