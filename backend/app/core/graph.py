# backend/app/core/graph.py

import time
import fnmatch
import inspect
import logging
from collections import ChainMap
from typing import Any, Callable, Dict, Set, List, Optional, Union, Tuple

from cachetools import LRUCache


# Configuración de logging sin pisar handlers globales existentes
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

logger = logging.getLogger("GraphEngine")


# Type Aliases para claridad de contrato
NodeEvaluator = Callable[[Dict[str, Any]], Any]
ContextLoader = Callable[[str], Any]
Modifier = Callable[[Any, Dict[str, Any]], Any]


class Graph:
    def __init__(self, is_clone: bool = False) -> None:
        # Lógica y estructura reactiva
        self._nodes: Dict[Union[str, Tuple], NodeEvaluator] = {}
        self._dependencies: Dict[Union[str, Tuple], Set[Union[str, Tuple]]] = {}
        self._loader: Optional[ContextLoader] = None
        self._modifiers: Dict[str, List[Modifier]] = {}

        # Protección anti-recursión / cargas repetidas
        self._loading_prefixes: Set[str] = set()

        # 🛡️ Umbral del OOM Killer (Límite de nodos en memoria local por transacción)
        self._gc_threshold = 20000

        # Diferenciamos el Grafo Maestro del Clon
        if not is_clone:
            # Grafo maestro con caché LRU
            self._values: Union[Dict[Union[str, Tuple], Any], LRUCache, ChainMap] = LRUCache(maxsize=100000)
            self._versions: Union[Dict[Union[str, Tuple], int], LRUCache, ChainMap] = LRUCache(maxsize=100000)
        else:
            # Clon de sesión (luego reemplazado con ChainMap)
            self._values = {}
            self._versions = {}

        # Cachés de sesión / petición
        self._rls_cache = {}
        self._admin_cache = {}
        self._acl_cache = {}

        # Rastreador de cambios
        self._dirty_nodes: Set[Union[str, Tuple]] = set()

    # =========================================================================
    # 💎 OPTIMIZACIÓN DE MEMORIA (TUPLE PARSER)
    # =========================================================================
    def _parse_key(self, key: Union[str, Tuple]) -> Union[str, Tuple]:
        """
        Convierte claves legacy string a tuplas compactas.
        'data:sale.order:1:name' -> ('sale.order', 1, 'name')
        """
        if isinstance(key, str) and key.startswith("data:"):
            parts = key.split(":")
            if len(parts) >= 4:
                rec_id = int(parts[2]) if parts[2].isdigit() else parts[2]
                return (parts[1], rec_id, parts[3])
        return key

    # =========================================================================
    # 🛡️ PROTECCIÓN ANTI-OOM (Garbage Collector)
    # =========================================================================
    def garbage_collect(self) -> None:
        """
        Libera memoria local de sesión sin tocar el maestro ni los nodos sucios.
        """
        if not isinstance(self._values, ChainMap):
            return

        local_vals = self._values.maps[0]
        if len(local_vals) < self._gc_threshold:
            return

        local_vers = self._versions.maps[0] if isinstance(self._versions, ChainMap) else {}
        keys_to_purge = [k for k in list(local_vals.keys()) if k not in self._dirty_nodes]

        for key in keys_to_purge:
            local_vals.pop(key, None)
            if isinstance(local_vers, dict):
                local_vers.pop(key, None)

        logger.warning(
            f"🛡️ [ANTI-OOM] Límite superado. Purga de RAM ejecutada: {len(keys_to_purge)} nodos liberados."
        )

    def set_loader(self, loader: ContextLoader) -> None:
        self._loader = loader

    async def load_context(self, prefix: str) -> None:
        """
        Carga datos maestros (Lazy Loading) desde almacenamiento persistente.
        No pisa nodos sucios de la sesión actual.
        """
        if not self._loader or not prefix:
            return

        if prefix in self._loading_prefixes:
            return

        self._loading_prefixes.add(prefix)
        try:
            logger.info(f"📥 Lazy Loading context: '{prefix}...'")

            loaded_data = self._loader(prefix)
            if inspect.isawaitable(loaded_data):
                loaded_data = await loaded_data

            if not loaded_data:
                return

            for key, item in loaded_data.items():
                parsed_key = self._parse_key(key)

                # Nunca sobrescribimos cambios locales aún no persistidos
                if parsed_key in self._dirty_nodes:
                    continue

                if isinstance(item, dict) and "value" in item:
                    self._values[parsed_key] = item["value"]
                    self._versions[parsed_key] = int(item.get("version", 1) or 1)
                else:
                    self._values[parsed_key] = item
                    self._versions[parsed_key] = 1
        finally:
            self._loading_prefixes.discard(prefix)

    def has_node(self, name: Union[str, Tuple]) -> bool:
        parsed_name = self._parse_key(name)
        return parsed_name in self._nodes

    def add_node(
        self,
        name: Union[str, Tuple],
        evaluator: NodeEvaluator,
        depends_on: Set[Union[str, Tuple]],
    ) -> None:
        """
        Registra un nodo calculado.
        """
        parsed_name = self._parse_key(name)
        parsed_deps = {self._parse_key(dep) for dep in depends_on}

        if parsed_name in self._nodes:
            logger.info(f"♻️ Updating logic for node: '{parsed_name}'")

        self._nodes[parsed_name] = evaluator
        self._dependencies[parsed_name] = parsed_deps

    def add_modifier(self, pattern: str, modifier: Modifier) -> None:
        """
        Registra un hook de modificación del resultado.
        """
        if pattern not in self._modifiers:
            self._modifiers[pattern] = []

        if modifier in self._modifiers[pattern]:
            return

        logger.info(f"💉 Registering modifier hook for pattern: '{pattern}'")
        self._modifiers[pattern].append(modifier)

    def set_fact(self, name: Union[str, Tuple], value: Any) -> None:
        """
        Setea un valor manual.
        Si cambia, marca el nodo como sucio y aumenta versión.
        """
        parsed_name = self._parse_key(name)
        current = self._values.get(parsed_name)

        if current != value:
            self._values[parsed_name] = value
            self._dirty_nodes.add(parsed_name)

            current_version = self._versions.get(parsed_name, 0) or 0
            self._versions[parsed_name] = int(current_version) + 1

            if isinstance(self._values, ChainMap) and len(self._values.maps[0]) >= self._gc_threshold:
                self.garbage_collect()

    def get(self, name: Union[str, Tuple]) -> Any:
        parsed_name = self._parse_key(name)
        return self._values.get(parsed_name)

    def get_dirty_items(self) -> Dict[Union[str, Tuple], Any]:
        """
        Extrae solo los datos modificados en esta sesión.
        """
        return {
            key: self._values[key]
            for key in self._dirty_nodes
            if key in self._values
        }

    def clear_dirty(self, keys: Optional[List[Union[str, Tuple]]] = None) -> None:
        """
        Limpieza granular o total del estado sucio.
        """
        if keys is None:
            self._dirty_nodes.clear()
        else:
            for key in keys:
                parsed_key = self._parse_key(key)
                self._dirty_nodes.discard(parsed_key)

        self.garbage_collect()

    async def recalculate(self) -> None:
        """
        🚀 MOTOR DE REACTIVIDAD
        Recalcula nodos afectados por cambios directos o transitivos.
        """
        if not self._dirty_nodes:
            return

        start_time = time.perf_counter()

        try:
            ordered = self._topological_order()
        except RuntimeError as e:
            logger.error(f"❌ Cycle detected: {e}")
            return

        dirty_frontier = set(self._dirty_nodes)
        recalculated_count = 0

        for name in ordered:
            evaluator = self._nodes.get(name)
            if evaluator is None:
                continue

            deps = self._dependencies.get(name, set())
            needs_update = bool(deps & dirty_frontier) or (name in dirty_frontier)

            if not needs_update:
                continue

            inputs = {dep: self._values.get(dep) for dep in deps}

            try:
                result = evaluator(inputs)
                if inspect.isawaitable(result):
                    result = await result

                # Aplicación de modificadores también para tuplas, usando representación string
                name_for_match = name if isinstance(name, str) else ":".join(map(str, name))
                for pattern, modifiers in self._modifiers.items():
                    if fnmatch.fnmatch(name_for_match, pattern):
                        for mod in modifiers:
                            maybe = mod(result, inputs)
                            result = await maybe if inspect.isawaitable(maybe) else maybe

                current_val = self._values.get(name)
                if current_val != result:
                    self._values[name] = result
                    self._dirty_nodes.add(name)
                    dirty_frontier.add(name)

                    current_version = self._versions.get(name, 0) or 0
                    self._versions[name] = int(current_version) + 1

                    recalculated_count += 1

            except Exception as e:
                logger.error(f"❌ Error calculating '{name}': {e}")
                import traceback
                traceback.print_exc()

        if isinstance(self._values, ChainMap) and len(self._values.maps[0]) >= self._gc_threshold:
            self.garbage_collect()

        duration_ms = (time.perf_counter() - start_time) * 1000
        if recalculated_count > 0:
            logger.info(f"⚡ Graph Update: {recalculated_count} nodes recalculated in {duration_ms:.4f}ms")

    def _topological_order(self) -> List[Union[str, Tuple]]:
        """
        DFS topológico para asegurar dependencias antes que dependientes.
        """
        resolved: List[Union[str, Tuple]] = []
        unresolved: Set[Union[str, Tuple]] = set()
        visited: Set[Union[str, Tuple]] = set()

        def visit(name: Union[str, Tuple]) -> None:
            if name in unresolved:
                raise RuntimeError(f"Circular dependency at '{name}'")
            if name in visited:
                return

            unresolved.add(name)
            for dep in self._dependencies.get(name, set()):
                if dep in self._nodes or dep in self._values:
                    visit(dep)

            unresolved.remove(name)
            visited.add(name)
            resolved.append(name)

        for name in self._nodes:
            visit(name)

        return resolved

    def snapshot(self) -> Dict[Union[str, Tuple], Any]:
        """
        📸 FOTO DE MEMORIA ATÓMICA
        Extrae la capa local modificada sin copiar el maestro.
        """
        if isinstance(self._values, ChainMap):
            return self._values.maps[0].copy()
        return dict(self._values)

    def rollback(self, snapshot_data: Dict[Union[str, Tuple], Any]) -> None:
        """
        ⏪ REVERSIÓN QUIRÚRGICA
        Restaura el estado local respetando la conexión al grafo maestro.
        """
        if isinstance(self._values, ChainMap):
            self._values.maps[0].clear()
            self._values.maps[0].update(snapshot_data)
            if isinstance(self._versions, ChainMap):
                self._versions.maps[0].clear()
        else:
            self._values.clear()
            self._values.update(snapshot_data)
            if hasattr(self._versions, "clear"):
                self._versions.clear()

        self._dirty_nodes.clear()
        logger.warning("⏪ Graph Rollback: Estado local de transacción revertido con éxito.")

    # =====================================================================
    # 🧬 CLONADOR DE SESIÓN (ZERO-COPY / ANTI-OOM)
    # =====================================================================
    def clone_for_session(self) -> "Graph":
        """
        Crea un clon zero-copy con ChainMap para la petición actual.
        """
        new_graph = Graph(is_clone=True)

        # Inteligencia compartida
        new_graph._nodes = self._nodes
        new_graph._dependencies = self._dependencies
        new_graph._loader = self._loader
        new_graph._modifiers = self._modifiers
        new_graph._gc_threshold = self._gc_threshold

        # Copy-on-write
        new_graph._values = ChainMap({}, self._values)
        new_graph._versions = ChainMap({}, self._versions)

        # Caches de sesión nuevas
        new_graph._rls_cache = {}
        new_graph._admin_cache = {}
        new_graph._acl_cache = {}

        new_graph._dirty_nodes = set()
        return new_graph