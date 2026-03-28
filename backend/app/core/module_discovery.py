# backend/app/core/module_discovery.py
import importlib
import inspect
import os
import pkgutil
import sys
from typing import Dict, List, Type

from app.core.module import Module


def _resolve_backend_and_modules_path(modules_dir_name: str = "modules") -> tuple[str, str]:
    current_file_path = os.path.abspath(__file__)
    app_core_dir = os.path.dirname(current_file_path)
    app_dir = os.path.dirname(app_core_dir)
    backend_dir = os.path.dirname(app_dir)
    modules_path = os.path.join(backend_dir, modules_dir_name)
    return backend_dir, modules_path


def sort_modules_topologically(modules: List[Type[Module]]) -> List[Type[Module]]:
    modules_dict: Dict[str, Type[Module]] = {}

    for mod in modules:
        mod_name = getattr(mod, "name", None)
        if not mod_name:
            raise RuntimeError(f"❌ Módulo sin atributo 'name': {mod}")
        if mod_name in modules_dict:
            raise RuntimeError(f"❌ Nombre de módulo duplicado detectado: '{mod_name}'")
        modules_dict[mod_name] = mod

    in_degree = {name: 0 for name in modules_dict}
    adj_list = {name: [] for name in modules_dict}

    for name, mod_cls in modules_dict.items():
        depends = getattr(mod_cls, "depends", []) or []
        if not isinstance(depends, list):
            raise RuntimeError(f"❌ El módulo '{name}' debe declarar depends como lista.")

        for dep in depends:
            if dep not in modules_dict:
                raise RuntimeError(
                    f"❌ Dependencia faltante: '{name}' requiere '{dep}', "
                    f"pero '{dep}' no fue descubierto."
                )
            adj_list[dep].append(name)
            in_degree[name] += 1

    queue = [name for name, degree in in_degree.items() if degree == 0]
    ordered: List[Type[Module]] = []

    while queue:
        current = queue.pop(0)
        ordered.append(modules_dict[current])

        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(modules_dict):
        raise RuntimeError("❌ Dependencia circular detectada entre módulos.")

    return ordered


def discover_modules(modules_dir_name: str = "modules") -> List[Type[Module]]:
    backend_dir, modules_path = _resolve_backend_and_modules_path(modules_dir_name)

    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    if not os.path.exists(modules_path):
        raise RuntimeError(f"❌ No existe el directorio de módulos: '{modules_path}'")

    print(f"🔎 Scanning for modules in '{modules_path}'...")
    found_modules: List[Type[Module]] = []

    for _, folder_name, is_pkg in pkgutil.iter_modules([modules_path]):
        if not is_pkg:
            continue

        module_spec = f"{modules_dir_name}.{folder_name}.module"

        try:
            lib = importlib.import_module(module_spec)
        except ModuleNotFoundError as e:
            if e.name == module_spec:
                continue
            raise RuntimeError(
                f"❌ El módulo '{folder_name}' existe pero falló cargando dependencias internas: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"❌ Error cargando '{module_spec}': {e}") from e

        module_class = None
        for attribute_name in dir(lib):
            attribute = getattr(lib, attribute_name)
            if inspect.isclass(attribute) and issubclass(attribute, Module) and attribute is not Module:
                module_class = attribute
                break

        if module_class is None:
            raise RuntimeError(f"❌ '{module_spec}' no expone una clase Module válida.")

        found_modules.append(module_class)

    ordered = sort_modules_topologically(found_modules)

    print("🧬 Secuencia de carga constitucional:")
    for mod in ordered:
        print(f"   ✅ {mod.name}")

    return ordered