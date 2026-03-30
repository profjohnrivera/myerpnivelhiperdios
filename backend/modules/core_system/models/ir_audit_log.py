# backend/app/core/models/ir_audit_log.py

import datetime

from app.core.orm import Model, Field
from app.core.payloads import normalize_changes, normalize_payload


def _utcnow() -> datetime.datetime:
    """
    Naive UTC datetime compatible con columnas Postgres TIMESTAMP.
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class IrAuditLog(Model):
    _name = "ir.audit.log"
    _description = "Registro de Auditoría"

    res_model = Field(type_="string", index=True, required=True)
    res_id = Field(type_="integer", index=True, required=True)
    user_id = Field(type_="integer", index=True)

    action = Field(
        type_="selection",
        options=[
            ("create", "Creación"),
            ("write", "Modificación"),
            ("unlink", "Eliminación"),
            ("error", "Error"),
        ],
        required=True,
    )

    changes = Field(type_="jsonb")
    message = Field(type_="text")
    timestamp = Field(type_="datetime", default=_utcnow)

    @classmethod
    async def create_from_queue(
        cls,
        res_model: str,
        res_id: int,
        action: str,
        changes: dict = None,
        message: str = None,
        user_id: int = None,
    ):
        """
        Segunda línea de defensa:
        aunque el caller mande payloads imperfectos, aquí vuelven a
        normalizarse antes de persistir.
        """
        from app.core.env import Context

        env = Context.get_env()

        resolved_user_id = user_id
        if resolved_user_id is None and env and str(env.uid).isdigit():
            resolved_user_id = int(env.uid)

        normalized_changes = normalize_changes(changes)
        normalized_message = normalize_payload(message) if message is not None else None

        allowed_actions = {"create", "write", "unlink", "error"}
        safe_action = action if action in allowed_actions else "write"

        return await cls.create({
            "res_model": str(res_model or "system"),
            "res_id": int(res_id) if str(res_id).isdigit() else 0,
            "user_id": resolved_user_id,
            "action": safe_action,
            "changes": normalized_changes or None,
            "message": normalized_message,
            "timestamp": _utcnow(),
        })