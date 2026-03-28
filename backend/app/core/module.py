# backend/app/core/module.py
from typing import TYPE_CHECKING, List, Type

if TYPE_CHECKING:
    from app.core.kernel import Kernel

class Module:
    """
    Clase base para todos los módulos del ERP Nivel Dios.
    Define el ciclo de vida: Carga -> Registro -> Boot.
    """
    name: str = "unknown"
    dependencies: List[str] = []

    def __init__(self, kernel: "Kernel") -> None:
        """
        Inyección de Dependencia: El Kernel es la ÚNICA fuente de verdad.
        """
        self.kernel = kernel
        # 🔥 NUEVO: Lista para rastrear los modelos de este módulo
        self.models: List[Type] = [] 

    @property
    def bus(self):
        return self.kernel.bus

    @property
    def graph(self):
        return self.kernel.graph

    def register(self) -> None:
        """
        Fase 1: Definición.
        Aquí declaras tus Políticas, Nodos del Grafo y Hooks de UI.
        """
        pass

    def boot(self) -> None:
        """
        Fase 2: Ejecución.
        Aquí te suscribes a eventos, inicias tareas cron, o conectas a APIs externas.
        """
        pass

    # 🔥 ESTE ES EL MÉTODO QUE FALTABA Y CAUSABA EL ERROR CRÍTICO 🔥
    def register_model(self, model_cls: Type) -> None:
        """
        Vincula explícitamente un modelo a este módulo.
        Permite que el módulo 'sepa' qué tablas le pertenecen.
        """
        self.models.append(model_cls)
        # Opcional: Podríamos inyectar metadata en el modelo aquí si fuera necesario
        # print(f"   🔧 Registrando modelo {model_cls.__name__} en módulo {self.name}")