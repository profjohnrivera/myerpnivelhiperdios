# backend/app/core/policies.py
from typing import Set, Dict, Any
from app.core.graph import Graph

class Policy:
    """
    Clase base para reglas de negocio reactivas.
    """
    def __init__(self):
        # Inicializamos por instancia para evitar compartir memoria entre políticas
        self.name: str = ""
        self.depends_on: Set[str] = set()

    def evaluate(self, inputs: Dict[str, Any]) -> bool:
        """
        Recibe los valores actuales de los nodos en 'depends_on'.
        Debe devolver True (pasa) o False (falla).
        """
        raise NotImplementedError

class PolicyRegistry:
    def __init__(self, graph: Graph):
        self.graph = graph

    def register(self, policy: Policy) -> None:
        """
        Convierte la política en un nodo vivo del grafo.
        """
        if not policy.name:
            raise RuntimeError(f"Policy {policy.__class__.__name__} must define a unique node name")

        # Inyectamos la lógica en el cerebro (Grafo)
        self.graph.add_node(
            name=policy.name,
            evaluator=policy.evaluate,
            depends_on=policy.depends_on
        )
        
        # Opcional: Podrías loguear el registro para debug
        # print(f"🛡️ Policy Registered: {policy.name}")