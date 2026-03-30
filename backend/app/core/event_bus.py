# backend/app/core/event_bus.py

import asyncio
import inspect
import fnmatch
from typing import Type, Dict, List, Callable, Awaitable, Union, Any, Optional

from app.core.events import Event
from app.core.registry import Registry
from app.core.payloads import normalize_payload

EventHandler = Callable[[Any], Union[None, Awaitable[None]]]


class EventBus:
    """
    📡 SISTEMA NERVIOSO CENTRAL

    Reglas finales:
    - Application crea y activa la instancia oficial
    - módulos usan self.bus
    - servicios sin acceso al runtime usan EventBus.get_instance()
    - NO usar EventBus() directo como patrón de acceso
    """

    _active_instance: Optional["EventBus"] = None

    def __init__(self):
        self._subscribers: Dict[Union[Type[Event], str], List[EventHandler]] = {}

    # =========================================================================
    # CICLO DE VIDA
    # =========================================================================

    @classmethod
    def get_instance(cls) -> "EventBus":
        """
        Devuelve la instancia activa de producción.
        Si no existe, crea una temporal para tests/scripts.
        """
        if cls._active_instance is None:
            cls._active_instance = cls()
        return cls._active_instance

    @classmethod
    def set_active(cls, instance: "EventBus"):
        cls._active_instance = instance

    @classmethod
    def clear_active(cls):
        if cls._active_instance:
            cls._active_instance.clear()
        cls._active_instance = None

    def clear(self) -> None:
        self._subscribers = {}
        print("   🧹 [EventBus] Todos los handlers limpiados.")

    # =========================================================================
    # SUBSCRIPCIÓN
    # =========================================================================

    def subscribe(self, event_type: Union[Type[Event], str], handler: EventHandler) -> None:
        """
        Idempotente: no duplica el mismo handler.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        existing = self._subscribers[event_type]
        handler_func = getattr(handler, "__wrapped__", handler)

        for existing_handler in existing:
            existing_func = getattr(existing_handler, "__wrapped__", existing_handler)
            if existing_func is handler_func or existing_handler is handler:
                return

        existing.append(handler)

        name = getattr(event_type, "__name__", event_type)
        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        print(f"   👂 Bus: Handler '{handler_name}' suscrito a '{name}'")

    def unsubscribe(self, event_type: Union[Type[Event], str], handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
        if not handlers and event_type in self._subscribers:
            del self._subscribers[event_type]

    def _get_string_handlers(self, event_name: str) -> List[EventHandler]:
        handlers: List[EventHandler] = []
        seen = set()

        for handler in self._subscribers.get(event_name, []):
            if id(handler) not in seen:
                handlers.append(handler)
                seen.add(id(handler))

        for key, key_handlers in self._subscribers.items():
            if isinstance(key, str) and ("*" in key or "?" in key or "[" in key):
                if fnmatch.fnmatch(event_name, key):
                    for handler in key_handlers:
                        if id(handler) not in seen:
                            handlers.append(handler)
                            seen.add(id(handler))

        return handlers

    # =========================================================================
    # PUBLICACIÓN
    # =========================================================================

    @staticmethod
    def _build_payload_snapshot(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Snapshot forense serializable del evento.
        No reemplaza los objetos vivos; solo añade una vista segura.
        """
        snapshot = {}
        for key, value in kwargs.items():
            if key in {"record", "env", "graph"}:
                continue
            snapshot[key] = normalize_payload(value)
        return snapshot

    async def publish(self, event: Union[Event, str], **kwargs) -> None:
        """
        Publica un evento y ejecuta handlers concurrentemente.

        Soporte:
        - Event object -> handlers reciben el objeto
        - String event  -> handlers reciben kwargs enriquecidos
        - Wildcards     -> "*.created", "*.updated", etc.

        P2-B:
        - añade payload_snapshot serializable para auditoría/forense
        - preserva record/env/graph vivos para handlers de negocio
        """
        if isinstance(event, Event):
            event_key = type(event)
            handlers = list(self._subscribers.get(event_key, []))
            payload_kwargs = {
                **kwargs,
                "payload_snapshot": self._build_payload_snapshot(kwargs),
            }
        else:
            event_key = str(event)
            handlers = self._get_string_handlers(event_key)

            model_name = kwargs.get("model_name")
            action_name = kwargs.get("action")

            if "." in event_key:
                parts = event_key.split(".")
                if len(parts) >= 2:
                    inferred_action = parts[-1]
                    inferred_model = ".".join(parts[:-1])
                    model_name = model_name or inferred_model
                    action_name = action_name or inferred_action

            payload_kwargs = {
                **kwargs,
                "event_name": event_key,
                "model_name": model_name,
                "action": action_name,
                "payload_snapshot": self._build_payload_snapshot({
                    **kwargs,
                    "event_name": event_key,
                    "model_name": model_name,
                    "action": action_name,
                }),
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
    # METADATA DE UI
    # =========================================================================

    def publish_meta(self, module: str, icon: str, label: str) -> None:
        Registry.register_module(name=module, icon=icon, label=label)

    def publish_menu(self, *args, **kwargs) -> None:
        raise RuntimeError(
            "❌ EventBus.publish_menu() está deshabilitado por arquitectura. "
            "Usa ir.ui.menu persistido desde modules/<mod>/data/menus.py."
        )