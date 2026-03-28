# backend/modules/core_system/models/ir_queue.py
from app.core.orm import Model, Field


class IrQueue(Model):
    _name = "ir.queue"
    _description = "Cola de Trabajos"

    model_name = Field(type_="string", required=True, index=True)
    method_name = Field(type_="string", required=True, index=True)

    args_json = Field(type_="text")
    kwargs_json = Field(type_="text")

    priority = Field(type_="integer", default=10, index=True)

    state = Field(
        type_="selection",
        options=[
            ("pending", "Pendiente"),
            ("started", "En Proceso"),
            ("done", "Completado"),
            ("failed", "Fallido"),
        ],
        default="pending",
        index=True,
        required=True,
    )

    error_log = Field(type_="text")
    date_started = Field(type_="datetime")
    date_finished = Field(type_="datetime")