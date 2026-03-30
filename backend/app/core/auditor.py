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
    def _clean_changes(changes: Optional[Dict]) -> Optional[Dict]:
        """
        Normaliza el dict de changes a formato {campo: {old, new}}.
        Compatible con formato nuevo y legacy.
        """
        if not changes:
            return None

        skip_fields = {
            "write_version", "write_date", "write_uid",
            "create_date", "create_uid", "id",
        }

        cleaned = {}
        for field, value in changes.items():
            if field in skip_fields:
                continue

            if isinstance(value, dict) and "old" in value and "new" in value:
                old_val = value["old"]
                new_val = value["new"]
                if old_val != new_val:
                    cleaned[field] = {"old": old_val, "new": new_val}
            else:
                cleaned[field] = {"old": None, "new": value}

        return cleaned if cleaned else None

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

        res_id = int(record.id) if str(record.id).isdigit() else record.id
        cleaned_changes = cls._clean_changes(changes)

        await WorkerEngine.enqueue(
            model_name="ir.audit.log",
            method_name="create_from_queue",
            kwargs={
                "res_model": model_name,
                "res_id": res_id,
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