# backend/app/core/models/ir_audit_log.py
import datetime
from app.core.orm import Model, Field


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
    timestamp = Field(type_="datetime", default=datetime.datetime.utcnow)

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
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })