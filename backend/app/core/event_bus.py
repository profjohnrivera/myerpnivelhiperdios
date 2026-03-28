# backend/app/core/event_bus.py
import asyncio
import inspect
import fnmatch
from typing import Type, Dict, List, Callable, Awaitable, Union, Any
from app.core.events import Event
from app.core.registry import Registry

EventHandler = Callable[[Any], Union[None, Awaitable[None]]]


class EventBus:
    """
    📡 SISTEMA NERVIOSO CENTRAL (Unified Event Bus)
    Soporta:
    - eventos de dominio por Clase
    - señales del sistema por String
    - wildcards estilo '*.created'
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: Union[Type[Event], str], handler: EventHandler) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

        name = getattr(event_type, "__name__", event_type)
        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        print(f"   👂 Bus: Handler '{handler_name}' suscrito a '{name}'")

    def clear(self) -> None:
        self._subscribers = {}

    def _get_string_handlers(self, event_name: str) -> List[EventHandler]:
        handlers: List[EventHandler] = []
        seen = set()

        # exact match
        for handler in self._subscribers.get(event_name, []):
            if handler not in seen:
                handlers.append(handler)
                seen.add(handler)

        # wildcard matches
        for key, key_handlers in self._subscribers.items():
            if isinstance(key, str) and ("*" in key or "?" in key or "[" in key):
                if fnmatch.fnmatch(event_name, key):
                    for handler in key_handlers:
                        if handler not in seen:
                            handlers.append(handler)
                            seen.add(handler)

        return handlers

    async def publish(self, event: Union[Event, str], **kwargs) -> None:
        """
        Publica un evento y ejecuta sus handlers concurrentemente.
        """
        if isinstance(event, Event):
            event_key = type(event)
            handlers = list(self._subscribers.get(event_key, []))
            payload_kwargs = kwargs
        else:
            event_key = event
            handlers = self._get_string_handlers(event_key)

            model_name = kwargs.get("model_name")
            action = kwargs.get("action")

            if isinstance(event_key, str) and "." in event_key:
                parts = event_key.split(".")
                if len(parts) >= 2:
                    inferred_action = parts[-1]
                    inferred_model = ".".join(parts[:-1])
                    model_name = model_name or inferred_model
                    action = action or inferred_action

            payload_kwargs = {
                **kwargs,
                "event_name": event_key,
                "model_name": model_name,
                "action": action,
            }

        if not handlers:
            return

        tasks = []
        event_name_str = getattr(event_key, "__name__", event_key)

        for handler in list(handlers):
            try:
                if isinstance(event, Event):
                    result = handler(event)
                else:
                    result = handler(**payload_kwargs)

                if inspect.isawaitable(result):
                    tasks.append(result)
            except Exception as e:
                print(f"❌ Error síncrono en EventBus handler para {event_name_str}: {e}")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    print(f"🔥 Error asíncrono en ejecución de evento '{event_name_str}': {res}")

    # =========================================================================
    # --- 🔥 MÉTODOS DE UI (Síncronos, usados durante la fase de Boot) ---
    # =========================================================================

    def publish_meta(self, module: str, icon: str, label: str) -> None:
        Registry.register_module(name=module, icon=icon, label=label)

    def publish_menu(self, parent: str, action: str, label: str, sequence: int = 10) -> None:
        Registry.register_menu(parent=parent, action=action, label=label, sequence=sequence)