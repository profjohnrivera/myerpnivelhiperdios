# backend/app/core/auditor.py

from typing import Any, Dict, Optional

from app.core.event_bus import EventBus
from app.core.worker import WorkerEngine
from app.core.env import Context
from app.core.payloads import normalize_changes, normalize_payload


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

        bus = EventBus.get_instance()
        bus.subscribe("*.created", cls.on_record_created)
        bus.subscribe("*.updated", cls.on_record_updated)
        bus.subscribe("*.unlinked", cls.on_record_unlinked)

        cls._bootstrapped = True
        print("🕵️ Auditor Universal: Conectado y vigilando mutaciones.")

    @classmethod
    def _should_skip(cls, model_name: Optional[str]) -> bool:
        if not model_name:
            return True
        if model_name in cls.EXCLUDED_MODELS:
            return True
        if model_name.startswith("ir."):
            return True

        env = Context.get_env()
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

    @staticmethod
    def _resolve_user_id() -> Optional[int]:
        env = Context.get_env()
        if env and str(getattr(env, "uid", "")).isdigit():
            return int(env.uid)
        return None

    @staticmethod
    def _resolve_res_id(record: Any = None, record_id: Any = None) -> Any:
        raw = record_id
        if raw is None and record is not None:
            raw = getattr(record, "id", None)
        return int(raw) if str(raw).isdigit() else raw

    @staticmethod
    def _clean_changes(changes: Optional[Dict]) -> Optional[Dict]:
        """
        Normalización canónica:
        - formato {field: {old, new}}
        - JSON-safe
        - sin campos de sistema irrelevantes
        """
        return normalize_changes(changes)

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

        res_id = cls._resolve_res_id(record=record)
        user_id = cls._resolve_user_id()

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "user_id": user_id,
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
        payload_snapshot: Dict = None,
        **kwargs,
    ):
        if cls._should_skip(model_name):
            return
        if record is None:
            return

        res_id = cls._resolve_res_id(record=record)
        user_id = cls._resolve_user_id()

        cleaned_changes = cls._clean_changes(changes)

        # Si el change set queda vacío tras limpiar ruido técnico, no auditar basura.
        if not cleaned_changes:
            return

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "user_id": user_id,
                "action": cls._normalize_action(action or "write"),
                "changes": cleaned_changes,
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

        res_id = cls._resolve_res_id(record_id=record_id)
        user_id = cls._resolve_user_id()

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
                "user_id": user_id,
                "action": cls._normalize_action(action or "unlink"),
                "changes": None,
                "message": None,
            },
        )

    @classmethod
    async def enqueue_error(
        cls,
        *,
        res_model: str,
        res_id: Any = 0,
        message: Any = None,
        changes: Optional[Dict] = None,
        user_id: Optional[int] = None,
    ):
        """
        Entrada explícita para errores forenses futuros.
        """
        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": res_model,
                "res_id": int(res_id) if str(res_id).isdigit() else res_id,
                "user_id": user_id if user_id is not None else cls._resolve_user_id(),
                "action": "error",
                "changes": normalize_changes(changes),
                "message": normalize_payload(message) if message is not None else None,
            },
        )