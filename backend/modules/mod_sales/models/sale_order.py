# backend/modules/mod_sales/models/sale_order.py

from typing import Dict, Any

from app.core.orm import (
    Field, SelectionField, MonetaryField, One2manyField,
    compute, onchange, check_state, constrains,
)
from app.core.decorators import transaction, action
from app.core.abstract_models import AbstractDocument
from app.core.mixins import TrazableMixin, AprobableMixin
from app.core.env import Context

from modules.mod_sales.services import SaleOrderService


class SaleOrder(AbstractDocument, TrazableMixin, AprobableMixin):
    _name = "sale.order"
    _rec_name = "name"
    _description = "Pedido de Venta"

    currency_id = Field(type_="string", default="PEN", label="Moneda")
    amount_total = MonetaryField(currency_field="currency_id", label="Total Pedido", readonly=True)

    state = SelectionField(
        options=[
            ("draft", "Cotización"),
            ("sent", "Cotización Enviada"),
            ("sale", "Orden de Venta"),
            ("done", "Completado"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        label="Estado",
    )

    invoice_status = SelectionField(
        options=[
            ("upselling", "Oportunidad de Upselling"),
            ("invoiced", "Totalmente Facturado"),
            ("to invoice", "A Facturar"),
            ("no", "Nada que Facturar"),
        ],
        default="no",
        label="Estado de Facturación",
        readonly=True,
    )

    order_line = One2manyField(
        related_model="sale.order.line",
        inverse_name="order_id",
        label="Líneas de Pedido",
    )

    # ── Helpers fachada ───────────────────────────────────────────────────────

    @staticmethod
    def _resolve_company_from_env():
        return SaleOrderService.resolve_company_from_env()

    @classmethod
    async def _resolve_company_async(cls) -> int | None:
        return await SaleOrderService.resolve_company_async()

    @staticmethod
    def _iter_lines(lines):
        return SaleOrderService.iter_lines(lines)

    async def _get_order_lines(self, allow_db_fallback: bool = True):
        return await SaleOrderService.get_order_lines(self, allow_db_fallback=allow_db_fallback)

    @staticmethod
    def _is_commercial_line(line) -> bool:
        return SaleOrderService.is_commercial_line(line)

    @staticmethod
    def _line_subtotal(line) -> float:
        return SaleOrderService.line_subtotal(line)

    @staticmethod
    def _line_invoice_status(line) -> str:
        return SaleOrderService.line_invoice_status(line)

    # ── Onchange ─────────────────────────────────────────────────────────────

    @onchange("order_line")
    def _onchange_order_line(self):
        SaleOrderService.recompute_onchange_total(self)

    # ── Compute ──────────────────────────────────────────────────────────────

    @compute(depends=["order_line.price_subtotal", "order_line.invoice_status", "state"])
    async def _compute_total_and_invoice_status(self):
        await SaleOrderService.compute_total_and_invoice_status(self)

    # ── Constrains ───────────────────────────────────────────────────────────

    @constrains("company_id", "partner_id")
    def _check_company_consistency(self):
        SaleOrderService.check_company_consistency(self)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    @classmethod
    async def create(cls, vals, context=None):
        vals = await SaleOrderService.prepare_create_vals(vals)
        order = await super().create(vals, context=context)

        # cierre final del agregado, incluso si el create vino con líneas nested
        await SaleOrderService.compute_total_and_invoice_status(order)
        return order

    async def write(self, vals: Dict[str, Any]) -> bool:
        vals = SaleOrderService.sanitize_write_vals(self, vals)

        if not vals:
            return True

        result = await super().write(vals)

        # cierre final del agregado cuando cambian líneas o estado
        if any(k in vals for k in ("order_line", "state")):
            await SaleOrderService.compute_total_and_invoice_status(self)

        return result

    # ── Acciones ─────────────────────────────────────────────────────────────

    @action(label="Marcar como Enviado", icon="send", variant="secondary")
    @check_state(["draft"])
    async def action_sent(self):
        await self.write({"state": "sent"})

    @action(label="Confirmar Pedido", icon="check_circle", variant="primary")
    @transaction
    @check_state(["draft", "sent"])
    async def action_confirm(self):
        await SaleOrderService.ensure_confirmable(self)
        await self.write({"state": "sale"})

    @action(label="Marcar como Completado", icon="badge_check", variant="secondary")
    @check_state(["sale"])
    async def action_done(self):
        await self.write({"state": "done"})

    @action(label="Volver a Borrador", icon="undo", variant="secondary")
    @check_state(["cancel"])
    async def action_draft(self):
        await self.write({"state": "draft"})

    @action(label="Cancelar Pedido", icon="x_circle", variant="secondary")
    @check_state(["draft", "sent", "sale"])
    async def action_cancel(self):
        await self.write({"state": "cancel"})

    @action(label="Confirmar Masivamente (Background)", icon="zap", variant="primary")
    @check_state(["draft", "sent"])
    async def action_confirm_async(self, **kwargs):
        import asyncio

        print(f"\n⏳ [WORKER] Iniciando tarea pesada para Pedido {self.id}...")
        await asyncio.sleep(10)

        env = Context.get_env()
        if not env:
            raise Exception("❌ [WORKER] No se encontró contexto activo.")

        recordset = env["sale.order"].browse([self.id])
        await recordset.load_data()

        if recordset and len(recordset) > 0:
            record = recordset[0]
            await SaleOrderService.ensure_confirmable(record)
            await record.write({"state": "sale"})
            print(f"✅ [WORKER] Pedido {self.id} confirmado.\n")
        else:
            print(f"❌ [WORKER] El pedido {self.id} no pudo ser re-localizado.")