# backend/app/core/graph.py
import time
import asyncio
import fnmatch
import inspect 
from typing import Any, Callable, Dict, Set, List, Optional, Union, Tuple
import logging
from collections import ChainMap
from cachetools import LRUCache

# Configuración de logging para monitoreo de performance en tiempo real
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GraphEngine")

# Type Aliases para claridad de contrato
NodeEvaluator = Callable[[Dict[str, Any]], Any]
ContextLoader = Callable[[str], Any]
Modifier = Callable[[Any, Dict[str, Any]], Any]

class Graph:
    def __init__(self, is_clone: bool = False) -> None:
        # Lógica y Estructura (Compartida estáticamente entre clones)
        self._nodes: Dict[Union[str, Tuple], NodeEvaluator] = {}
        self._dependencies: Dict[Union[str, Tuple], Set[Union[str, Tuple]]] = {}
        self._loader: Optional[ContextLoader] = None
        self._modifiers: Dict[str, List[Modifier]] = {}
        
        # 🛡️ Umbral del OOM Killer (Límite de nodos en memoria local por transacción)
        self._gc_threshold = 20000 
        
        # Diferenciamos el Grafo Maestro del Clon
        if not is_clone:
            # El Maestro actúa como una Caché inteligente. Los nodos más viejos o menos 
            # usados se destruyen si se supera el límite, salvando la RAM del servidor.
            self._values: Union[Dict[Union[str, Tuple], Any], LRUCache, ChainMap] = LRUCache(maxsize=100000)
            self._versions: Union[Dict[Union[str, Tuple], int], LRUCache, ChainMap] = LRUCache(maxsize=100000) 
        else:
            # Los clones inicializan vacío, pero se reemplazarán por ChainMap al instanciarse
            self._values = {}
            self._versions = {}
            
            # Cachés de Sesión para RLS (Nivel de Petición)
            self._rls_cache = {}
            self._admin_cache = {}
        
        # Rastreador de cambios ("Dirty Set") para recálculo incremental y persistencia
        self._dirty_nodes: Set[Union[str, Tuple]] = set()

    # =========================================================================
    # 💎 OPTIMIZACIÓN DE MEMORIA (TUPLE PARSER)
    # =========================================================================
    def _parse_key(self, key: Union[str, Tuple]) -> Union[str, Tuple]:
        """
        Convierte claves String (Legacy) a Tuplas ultraligeras para ahorrar RAM.
        'data:sale.order:1:name' -> ('sale.order', 1, 'name')
        """
        if isinstance(key, str) and key.startswith("data:"):
            parts = key.split(":")
            if len(parts) >= 4:
                # parts[1] = modelo, parts[2] = id, parts[3] = campo
                r_id = int(parts[2]) if parts[2].isdigit() else parts[2]
                return (parts[1], r_id, parts[3])
        return key

    # =========================================================================
    # 🛡️ PROTECCIÓN ANTI-OOM (Garbage Collector)
    # =========================================================================
    def garbage_collect(self) -> None:
        """
        🧹 OOM SHIELD (Garbage Collector Cuántico): 
        Libera memoria RAM de la transacción actual. Destruye nodos 'limpios' (solo lectura)
        preservando matemáticamente los 'sucios' (modificados) y el Grafo Maestro intacto.
        """
        if not isinstance(self._values, ChainMap): 
            return # El Grafo Maestro se gestiona solo vía LRUCache
            
        local_vals = self._values.maps[0]
        if len(local_vals) < self._gc_threshold: 
            return

        local_vers = self._versions.maps[0] if isinstance(self._versions, ChainMap) else {}
        
        # Identificamos la basura: Nodos en RAM local que NO han sido modificados
        keys_to_purge = [k for k in local_vals.keys() if k not in self._dirty_nodes]
        
        for k in keys_to_purge:
            del local_vals[k]
            if k in local_vers: 
                del local_vers[k]
                
        logger.warning(f"🛡️ [ANTI-OOM] Límite superado. Purga de RAM ejecutada: {len(keys_to_purge)} nodos liberados.")

    def set_loader(self, loader: ContextLoader) -> None:
        self._loader = loader

    async def load_context(self, prefix: str) -> None:
        """Carga datos maestros (Lazy Loading) desde el almacenamiento persistente."""
        if self._loader:
            logger.info(f"📥 Lazy Loading context: '{prefix}...'")
            loaded_data = await self._loader(prefix)
            
            for key, item in loaded_data.items():
                # Forzamos tuplas si vienen como strings
                parsed_key = self._parse_key(key)
                self._values[parsed_key] = item["value"]
                self._versions[parsed_key] = item["version"]

    def has_node(self, name: Union[str, Tuple]) -> bool:
        parsed_name = self._parse_key(name)
        return parsed_name in self._nodes

    def add_node(self, name: Union[str, Tuple], evaluator: NodeEvaluator, depends_on: Set[Union[str, Tuple]]) -> None:
        """Registra una fórmula o nodo de cálculo en el grafo."""
        parsed_name = self._parse_key(name)
        parsed_deps = {self._parse_key(d) for d in depends_on}
        
        if parsed_name in self._nodes:
            logger.info(f"♻️  Updating logic for node: '{parsed_name}'")
        self._nodes[parsed_name] = evaluator
        self._dependencies[parsed_name] = parsed_deps

    def add_modifier(self, pattern: str, modifier: Modifier) -> None:
        """Registra un Hook (inyector) que modifica el resultado de nodos que coincidan con el patrón."""
        if pattern not in self._modifiers:
            self._modifiers[pattern] = []
        if modifier in self._modifiers[pattern]:
            return
        logger.info(f"💉 Registering modifier hook for pattern: '{pattern}'")
        self._modifiers[pattern].append(modifier)

    def set_fact(self, name: Union[str, Tuple], value: Any) -> None:
        """Setea un valor manual. Si el valor cambia, marca el nodo como 'sucio' para propagar."""
        parsed_name = self._parse_key(name)
        current = self._values.get(parsed_name)
        
        if current != value:
            self._values[parsed_name] = value
            self._dirty_nodes.add(parsed_name)
            
            # 🚀 Auto-regulación de RAM
            if isinstance(self._values, ChainMap) and len(self._values.maps[0]) >= self._gc_threshold:
                self.garbage_collect()

    def get(self, name: Union[str, Tuple]) -> Any:
        parsed_name = self._parse_key(name)
        return self._values.get(parsed_name)
    
    def get_dirty_items(self) -> Dict[Union[str, Tuple], Any]:
        """Extrae solo los datos modificados en esta sesión para persistencia en BD."""
        return {k: self._values[k] for k in self._dirty_nodes if k in self._values}
    
    def clear_dirty(self, keys: Optional[List[Union[str, Tuple]]] = None) -> None:
        """Limpieza granular de estados de cambio."""
        if keys is None:
            self._dirty_nodes.clear()
        else:
            for k in keys:
                parsed_k = self._parse_key(k)
                self._dirty_nodes.discard(parsed_k)
        
        # Una vez limpiados (guardados en BD), ejecutamos el GC para liberar la RAM
        self.garbage_collect()

    async def recalculate(self) -> None:
        """
        🚀 MOTOR DE REACTIVIDAD:
        Calcula nodos en orden topológico procesando solo lo que ha cambiado.
        Soporta evaluadores síncronos y asíncronos.
        """
        if not self._dirty_nodes:
            return

        start_time = time.perf_counter()
        
        try:
            ordered = self._topological_order()
        except RuntimeError as e:
            logger.error(f"❌ Cycle detected: {e}")
            return

        recalculated_count = 0
        
        for name in ordered:
            evaluator = self._nodes.get(name)
            if evaluator is None: continue
            
            deps = self._dependencies.get(name, set())
            
            # Solo recalculamos si hay impacto directo o indirecto
            needs_update = bool(deps & self._dirty_nodes) or (name in self._dirty_nodes)
            
            if not needs_update:
                continue

            inputs = {dep: self._values.get(dep) for dep in deps}
            
            try:
                # Ejecución con detección de corrutinas (Async/Sync agnostic)
                result = evaluator(inputs)
                if inspect.isawaitable(result):
                    result = await result
                
                # Aplicación de Modificadores dinámicos
                # (Actualmente los modificadores usan strings, si name es tupla lo saltamos temporalmente)
                if isinstance(name, str):
                    for pattern, modifiers in self._modifiers.items():
                        if fnmatch.fnmatch(name, pattern):
                            for mod in modifiers:
                                result = mod(result, inputs)

                # Comparación para evitar propagación innecesaria
                current_val = self._values.get(name)
                if current_val != result:
                    self._values[name] = result
                    self._dirty_nodes.add(name) 
                    recalculated_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error calculating '{name}': {e}")
                import traceback
                traceback.print_exc()
        
        # 🚀 Verificamos la RAM después de recálculos masivos
        if isinstance(self._values, ChainMap) and len(self._values.maps[0]) >= self._gc_threshold:
            self.garbage_collect()
            
        duration_ms = (time.perf_counter() - start_time) * 1000
        if recalculated_count > 0:
            logger.info(f"⚡ Graph Update: {recalculated_count} nodes recalculated in {duration_ms:.4f}ms")

    def _topological_order(self) -> List[Union[str, Tuple]]:
        """Algoritmo DFS para asegurar que las dependencias se calculen antes que los dependientes."""
        resolved = []
        unresolved = set()
        visited = set()

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
        📸 FOTO DE MEMORIA ATÓMICA (Checkpoint)
        Extrae estrictamente los datos locales modificados en esta sesión sin copiar el Maestro.
        """
        if isinstance(self._values, ChainMap):
            # Extraemos SOLO la capa 0 (La burbuja actual)
            return self._values.maps[0].copy()
        # Fallback genérico para instanciaciones que no sean clones
        return dict(self._values)

    def rollback(self, snapshot_data: Dict[Union[str, Tuple], Any]) -> None:
        """
        ⏪ REVERSIÓN QUIRÚRGICA
        Restaura el estado local a partir del snapshot respetando la conexión al Grafo Maestro.
        """
        if isinstance(self._values, ChainMap):
            self._values.maps[0].clear()
            self._values.maps[0].update(snapshot_data)
        else:
            self._values.clear()
            self._values.update(snapshot_data)
            
        self._dirty_nodes.clear()
        logger.warning("⏪ Graph Rollback: Estado local de transacción revertido con éxito.")

    # =====================================================================
    # 🧬 EL CLONADOR DE SESIÓN (ZERO-COPY / ANTI-OOM)
    # =====================================================================
    def clone_for_session(self) -> 'Graph':
        """
        Crea un clon del grafo para una petición HTTP tomando 0 Milisegundos y 0 Bytes.
        Utiliza el patrón Copy-On-Write mediante `collections.ChainMap`.
        """
        new_graph = Graph(is_clone=True)
        
        # Inteligencia compartida (Punteros directos, cero clonación profunda)
        new_graph._nodes = self._nodes
        new_graph._dependencies = self._dependencies
        new_graph._loader = self._loader
        new_graph._modifiers = self._modifiers
        new_graph._gc_threshold = self._gc_threshold # Hereda el límite de OOM
        
        # 🛡️ LA MAGIA ANTI-COLAPSO: ChainMap
        # Diccionario local {} en índice 0 (Donde escribirá esta Request)
        # Diccionario Maestro `self._values` en índice 1 (Solo lectura rápida de respaldo)
        new_graph._values = ChainMap({}, self._values) 
        new_graph._versions = ChainMap({}, self._versions)
        
        # El estado 'sucio' comienza de cero para la nueva transacción
        new_graph._dirty_nodes = set()
        
        return new_graph