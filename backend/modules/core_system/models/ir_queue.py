# backend/modules/core_system/models/ir_queue.py
# ============================================================
# COLA DE TRABAJOS — ARQUITECTURA DEFINITIVA
#
# Campos añadidos vs versión anterior:
#
# retries        → contador de intentos realizados
# max_retries    → máximo de intentos antes de ir a DLQ (default 3)
# retry_at       → timestamp para el próximo reintento (backoff exponencial)
# scheduled_at   → cuándo fue creado/encolado el job
#
# Estados:
#   pending  → en cola, esperando ser procesado
#   started  → siendo procesado ahora mismo
#   done     → completado con éxito
#   failed   → falló y se agotaron los reintentos → DLQ definitivo
#   retry    → falló pero aún tiene reintentos disponibles
#
# FIX DEFINITIVO — Recovery de jobs huérfanos:
#   Jobs en estado 'started' al arrancar el Worker significan que el
#   proceso murió a mitad de ejecución. El Worker los recupera
#   automáticamente al boot: SET state='retry' WHERE state='started'.
#   Esto garantiza que ningún job se pierda por un crash del servidor.
#
# FIX DEFINITIVO — Retry con backoff exponencial:
#   Intento 1 falla → retry en 30s
#   Intento 2 falla → retry en 60s
#   Intento 3 falla → retry en 120s
#   Intento max_retries falla → state='failed' (DLQ definitivo)
# ============================================================

from app.core.orm import Model, Field, SelectionField


class IrQueue(Model):
    """
    📋 COLA DE TRABAJOS PERSISTENTE

    Cada row es un job asíncrono con ciclo de vida completo:
    retry automático, backoff exponencial, y DLQ cuando se agota.
    """
    _name = "ir.queue"
    _description = "Cola de Trabajos"

    # ── Identidad del job ────────────────────────────────────────────────────
    model_name  = Field(type_="string",  required=True, index=True)
    method_name = Field(type_="string",  required=True, index=True)
    args_json   = Field(type_="text")
    kwargs_json = Field(type_="text")

    # ── Control de ejecución ─────────────────────────────────────────────────
    priority    = Field(type_="integer", default=10,    index=True)

    state = SelectionField(
        options=[
            ("pending", "Pendiente"),
            ("started", "En Proceso"),
            ("retry",   "Reintentando"),
            ("done",    "Completado"),
            ("failed",  "Fallido (DLQ)"),
        ],
        default="pending",
        index=True,
        required=True,
    )

    # ── Retry con backoff exponencial ────────────────────────────────────────
    retries     = Field(type_="integer",  default=0)
    max_retries = Field(type_="integer",  default=3)
    retry_at    = Field(type_="datetime")  # cuándo reintentarlo

    # ── Timestamps de ciclo de vida ──────────────────────────────────────────
    scheduled_at   = Field(type_="datetime")
    date_started   = Field(type_="datetime")
    date_finished  = Field(type_="datetime")

    # ── Log de errores ───────────────────────────────────────────────────────
    error_log = Field(type_="text")