# backend/modules/mod_sales/models/sale_order.py
from typing import Dict, Any

from app.core.orm import (
    Field,
    SelectionField,
    MonetaryField,
    One2manyField,
    compute,
    onchange,
    check_state,
    constrains,
)
from app.core.decorators import transaction, action
from app.core.registry import Registry
from app.core.abstract_models import AbstractDocument
from app.core.mixins import TrazableMixin, AprobableMixin
from app.core.env import Context


class SaleOrder(AbstractDocument, TrazableMixin, AprobableMixin):
    """
    ===========================================================================
    3. CABECERA DEL PEDIDO
    ===========================================================================
    """
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

    @staticmethod
    def _resolve_company_from_env():
        env = Context.get_env()
        if not env:
            return None

        ctx_company = env.context.get("company_id") if getattr(env, "context", None) else None
        if ctx_company is not None:
            return ctx_company

        try:
            if env.user and env.user.company_id:
                return env.user.company_id.id if hasattr(env.user.company_id, "id") else env.user.company_id
        except Exception:
            pass

        return None

    @onchange("order_line")
    def _onchange_order_line(self):
        total = 0.0
        lines = getattr(self, "order_line", [])
        if isinstance(lines, list):
            for line in lines:
                if isinstance(line, dict):
                    sub = line.get("price_subtotal", 0.0)
                    total += float(sub) if sub is not None else 0.0
                else:
                    sub = getattr(line, "price_subtotal", 0.0)
                    total += float(sub) if sub is not None else 0.0
        self.amount_total = total

    @compute(depends=["order_line.price_subtotal"])
    async def _compute_total_and_invoice_status(self):
        total = 0.0
        line_statuses = set()

        lines = getattr(self, "order_line", [])

        if lines:
            if hasattr(lines, "load_data"):
                await lines.load_data()

            for line in lines:
                total += float(getattr(line, "price_subtotal", 0.0) or 0.0)
                if not getattr(line, "display_type", None):
                    line_statuses.add(getattr(line, "invoice_status", "no"))

        self.amount_total = total

        current_state = getattr(self, "state", "draft")
        if current_state not in ["sale", "done"]:
            self.invoice_status = "no"
        elif "to invoice" in line_statuses:
            self.invoice_status = "to invoice"
        elif line_statuses and all(s == "invoiced" for s in line_statuses):
            self.invoice_status = "invoiced"
        elif line_statuses and all(s in ["invoiced", "upselling"] for s in line_statuses):
            self.invoice_status = "upselling"
        else:
            self.invoice_status = "no"

    @constrains("company_id", "partner_id")
    def _check_company_consistency(self):
        if not self.company_id:
            raise ValueError("La orden debe tener compañía.")

        partner = getattr(self, "partner_id", None)
        if not partner:
            return

        try:
            partner_company = getattr(partner, "company_id", None)
            if partner_company:
                partner_company_id = partner_company.id if hasattr(partner_company, "id") else partner_company
                company_id = self.company_id.id if hasattr(self.company_id, "id") else self.company_id
                if partner_company_id and company_id and int(partner_company_id) != int(company_id):
                    raise ValueError("El contacto pertenece a otra compañía.")
        except AttributeError:
            # Si el partner aún no maneja company_id en su modelo, no rompemos.
            pass

    @classmethod
    async def create(cls, vals, context=None):
        vals = dict(vals or {})

        if not vals.get("company_id"):
            resolved_company = cls._resolve_company_from_env()
            if resolved_company:
                vals["company_id"] = resolved_company

        if not vals.get("currency_id"):
            vals["currency_id"] = "PEN"

        if vals.get("name", "Nuevo") == "Nuevo":
            IrSequence = Registry.get_model("ir.sequence")
            if IrSequence:
                new_name = await IrSequence.next_by_code("sale.order")
                if new_name:
                    vals["name"] = new_name

        return await super().create(vals, context=context)

    async def write(self, vals: Dict[str, Any]) -> bool:
        env = Context.get_env()
        vals = dict(vals or {})

        if not vals:
            return await super().write(vals)

        db_state = getattr(self, "state", "draft")

        if db_state in ["sale", "done"] and not (env and getattr(env, "su", False)):
            allowed_fields = {"state", "invoice_status", "write_version", "write_date", "write_uid"}
            attempted_fields = set(vals.keys())

            if not attempted_fields.issubset(allowed_fields):
                print("⚠️ [WARNING] Intento de modificar pedido cerrado. Bloqueando campos protegidos.")
                vals = {k: v for k, v in vals.items() if k in allowed_fields}
                if not vals:
                    return True

        return await super().write(vals)

    # =============================================================================
    # 🛡️ PROTECCIÓN DE ESTADOS FSM (Finite State Machine)
    # =============================================================================
    @action(label="Confirmar Pedido", icon="check_circle", variant="primary")
    @transaction
    @check_state(["draft", "sent"])
    async def action_confirm(self):
        lines = getattr(self, "order_line", [])
        if not lines:
            SaleOrderLineModel = Registry.get_model("sale.order.line")
            if SaleOrderLineModel:
                lines = await SaleOrderLineModel.search([("order_id", "=", self.id)], context=self.graph)

        if not lines:
            raise ValueError("No puedes confirmar una venta sin líneas de pedido.")

        await self.write({"state": "sale"})

    @action(label="Volver a Borrador", icon="undo", variant="secondary")
    @check_state(["cancel"])
    async def action_draft(self):
        await self.write({"state": "draft"})

    @action(label="Cancelar Pedido", icon="x_circle", variant="secondary")
    @check_state(["draft", "sent", "sale"])
    async def action_cancel(self):
        await self.write({"state": "cancel"})

    # =============================================================================
    # 🚀 LA PRUEBA DE FUEGO: EL MÉTODO ASÍNCRONO PESADO
    # =============================================================================
    @action(label="Confirmar Masivamente (Background)", icon="zap", variant="primary")
    @check_state(["draft", "sent"])
    async def action_confirm_async(self, **kwargs):
        """
        Este método es invocado por el WorkerEngine en un hilo paralelo.
        """
        import asyncio
        from app.core.env import Context

        print(f"\n⏳ [WORKER] ¡Iniciando tarea pesada para el Pedido {self.id}!")
        print("⏳ [WORKER] Simulando recálculo de costos y generación de documentos...")

        await asyncio.sleep(10)

        env = Context.get_env()
        if not env:
            raise Exception("❌ [WORKER] Error Crítico: No se encontró un contexto activo.")

        recordset = env["sale.order"].browse([self.id])
        await recordset.load_data()

        if recordset and len(recordset) > 0:
            record_to_update = recordset[0]

            v_actual = getattr(record_to_update, "write_version", 1)
            print(f"🔄 [WORKER] Aplicando cambio sobre Versión {v_actual} recién leída de Postgres...")

            await record_to_update.write({"state": "sale"})

            print(f"✅ [WORKER] ¡Pedido {self.id} finalizado con éxito tras 10s!\n")
        else:
            print(f"❌ [WORKER] Error: El pedido {self.id} no pudo ser re-localizado.")