# backend/app/core/event_bus.py
import asyncio
import inspect
from typing import Type, Dict, List, Callable, Awaitable, Union, Any
from app.core.events import Event
from app.core.registry import Registry

# El handler puede ser síncrono o asíncrono.
# Usamos Any para soportar tanto objetos Event como kwargs directos.
EventHandler = Callable[[Any], Union[None, Awaitable[None]]]

class EventBus:
    """
    📡 SISTEMA NERVIOSO CENTRAL (Unified Event Bus)
    Maneja eventos de dominio (Clases) y señales del sistema (Strings).
    Implementa Patrón Singleton para acceso universal.
    """
    _instance = None

    def __new__(cls):
        # 💎 PATRÓN SINGLETON: Garantiza que solo exista un bus en toda la app
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: Union[Type[Event], str], handler: EventHandler) -> None:
        """Suscribe un handler a un tipo de evento (Clase) o señal (String)."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
            
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            
        name = getattr(event_type, '__name__', event_type)
        print(f"   👂 Bus: Handler '{handler.__name__}' suscrito a '{name}'")

    async def publish(self, event: Union[Event, str], **kwargs) -> None:
        """
        Publica un evento y ejecuta sus handlers concurrentemente.
        """
        # La clave del diccionario es la clase (si es un objeto Event) o el string
        event_key = type(event) if isinstance(event, Event) else event
        handlers = self._subscribers.get(event_key, [])
        
        if not handlers:
            return

        tasks = []
        # Copiamos la lista por si un handler modifica la suscripción durante la iteración
        for handler in list(handlers):
            try:
                # Soporte híbrido: Si es un objeto Event se lo pasamos, si es String pasamos los kwargs
                if isinstance(event, Event):
                    result = handler(event)
                else:
                    result = handler(**kwargs)

                # Si el resultado es una corrutina (async def), la preparamos
                if inspect.isawaitable(result):
                    tasks.append(result)
            except Exception as e:
                print(f"❌ Error síncrono en EventBus handler for {getattr(event_key, '__name__', event_key)}: {e}")

        # 🚀 Ejecución Concurrente: Disparamos todas las tareas asíncronas en paralelo
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    print(f"🔥 Error asíncrono en ejecución de evento: {res}")

    # =========================================================================
    # --- 🔥 MÉTODOS DE UI (Síncronos, usados durante la fase de Boot) ---
    # =========================================================================
    
    def publish_meta(self, module: str, icon: str, label: str) -> None:
        """
        Registra metadatos del módulo en el Registry (Síncrono).
        Usado durante la fase 'register' del arranque.
        """
        Registry.register_module(name=module, icon=icon, label=label)

    def publish_menu(self, parent: str, action: str, label: str, sequence: int = 10) -> None:
        """
        Registra un ítem de menú en el Registry (Síncrono).
        """
        Registry.register_menu(parent=parent, action=action, label=label, sequence=sequence)