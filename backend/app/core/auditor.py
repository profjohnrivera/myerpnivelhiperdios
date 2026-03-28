# backend/app/core/auditor.py
from typing import Any, Dict, Optional
from app.core.event_bus import EventBus
from app.core.worker import WorkerEngine
from app.core.env import Context


class AuditService:
    """
    👁️ SERVICIO DE TRAZABILIDAD AUTOMÁTICA
    Escucha al EventBus y genera logs forenses sin bloquear el hilo principal.
    """

    _bootstrapped: bool = False

    EXCLUDED_MODELS = {
        "ir.audit.log",
        "ir.queue",
    }

    @classmethod
    async def bootstrap(cls):
        if cls._bootstrapped:
            return

        bus = EventBus()
        bus.subscribe("*.created", cls.on_record_created)
        bus.subscribe("*.updated", cls.on_record_updated)
        bus.subscribe("*.unlinked", cls.on_record_unlinked)

        cls._bootstrapped = True
        print("🕵️ Auditor Universal: Conectado y vigilando mutaciones.")

    @classmethod
    def _should_skip(cls, model_name: Optional[str]) -> bool:
        if not model_name:
            return True

        # Nunca auditar modelos autoreferenciales/técnicos de cola/log
        if model_name in cls.EXCLUDED_MODELS:
            return True

        # Nunca auditar modelos técnicos ir.*
        if model_name.startswith("ir."):
            return True

        env = Context.get_env()

        # No auditar bootstrap, system jobs o contextos explícitamente silenciados
        if env:
            if getattr(env, "su", False):
                return True

            if str(getattr(env, "uid", "")) == "system":
                return True

            if getattr(env, "context", {}).get("disable_audit"):
                return True

        return False

    @staticmethod
    def _normalize_action(action: Optional[str]) -> str:
        if action in ("created", "create"):
            return "create"
        if action in ("updated", "write"):
            return "write"
        if action in ("unlinked", "unlink"):
            return "unlink"
        if action == "error":
            return "error"
        return "write"

    @classmethod
    async def on_record_created(
        cls,
        model_name: str = None,
        record: Any = None,
        action: str = None,
        **kwargs,
    ):
        if cls._should_skip(model_name):
            return
        if record is None:
            return

        res_id = int(record.id) if str(record.id).isdigit() else record.id

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "action": cls._normalize_action(action or "create"),
                "changes": None,
                "message": None,
            },
        )

    @classmethod
    async def on_record_updated(
        cls,
        model_name: str = None,
        record: Any = None,
        changes: Dict = None,
        action: str = None,
        **kwargs,
    ):
        if cls._should_skip(model_name):
            return
        if record is None:
            return

        clean_changes = changes or {}
        if not clean_changes:
            return

        res_id = int(record.id) if str(record.id).isdigit() else record.id

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "action": cls._normalize_action(action or "write"),
                "changes": clean_changes,
                "message": None,
            },
        )

    @classmethod
    async def on_record_unlinked(
        cls,
        model_name: str = None,
        record_id: Any = None,
        action: str = None,
        **kwargs,
    ):
        if cls._should_skip(model_name):
            return
        if record_id is None:
            return

        res_id = int(record_id) if str(record_id).isdigit() else record_id

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "action": cls._normalize_action(action or "unlink"),
                "changes": None,
                "message": None,
            },
        )