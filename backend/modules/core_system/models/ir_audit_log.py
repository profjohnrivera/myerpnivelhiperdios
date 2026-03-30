# backend/app/core/models/ir_audit_log.py
# ============================================================
# FIX P4-A: datetime.utcnow() reemplazado por datetime.now(UTC).
#
# PROBLEMA: datetime.datetime.utcnow() está deprecado desde
#   Python 3.12 y emite DeprecationWarning en cada log de
#   auditoría. En Python 3.14 será error.
#
# SOLUCIÓN: datetime.now(timezone.utc) que devuelve un objeto
#   timezone-aware. Para Postgres TIMESTAMP (sin zona), usamos
#   .replace(tzinfo=None) para mantener el formato naive que
#   el driver asyncpg espera en columnas TIMESTAMP.
#   Si en el futuro migras a TIMESTAMPTZ, quita el replace().
# ============================================================
import datetime
from app.core.orm import Model, Field


# Helper centralizado para timestamps consistentes en todo el sistema.
# Naive UTC datetime compatible con columnas Postgres TIMESTAMP.
def _utcnow() -> datetime.datetime:
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
    # FIX P4-A: usar _utcnow como callable en lugar de utcnow
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
        from app.core.env import Context

        env = Context.get_env()

        resolved_user_id = user_id
        if resolved_user_id is None and env and str(env.uid).isdigit():
            resolved_user_id = int(env.uid)

        return await cls.create({
            "res_model": res_model,
            "res_id": int(res_id) if str(res_id).isdigit() else res_id,
            "user_id": resolved_user_id,
            "action": action,
            "changes": changes or None,
            "message": message,
            # FIX P4-A: _utcnow() en lugar de utcnow()
            "timestamp": _utcnow().isoformat(),
        })