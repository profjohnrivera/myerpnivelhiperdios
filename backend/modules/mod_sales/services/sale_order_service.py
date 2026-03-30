# backend/modules/mod_sales/services/sale_order_service.py

from typing import Dict, Any, Iterable

from app.core.registry import Registry
from app.core.env import Context


class SaleOrderService:
    """
    🧠 SERVICIO DE NEGOCIO DE PEDIDOS DE VENTA

    Responsabilidades:
    - helpers de líneas
    - resolución de compañía
    - preparación de create
    - sanitización de write
    - validaciones de confirmación
    - cálculo de total / invoice_status desde el Graph
    """

    @staticmethod
    def resolve_company_from_env():
        env = Context.get_env()
        if not env:
            return None

        ctx_company = env.context.get("company_id") if getattr(env, "context", None) else None
        if ctx_company is not None:
            return ctx_company

        try:
            if env.user_id and str(env.user_id).isdigit():
                graph = getattr(env, "graph", None)
                if graph:
                    company_id = graph.get(("res.users", int(env.user_id), "company_id"))
                    if company_id:
                        return company_id
        except Exception:
            pass

        return None

    @classmethod
    async def resolve_company_async(cls) -> int | None:
        """
        Resolución async con fallback a BD.
        Se mantiene aquí para aislar infraestructura fuera del modelo.
        """
        sync_result = cls.resolve_company_from_env()
        if sync_result:
            return sync_result

        try:
            from app.core.storage.postgres_storage import PostgresGraphStorage

            storage = PostgresGraphStorage()
            conn_or_pool = await storage.get_connection()
            query = 'SELECT id FROM "res_company" ORDER BY id LIMIT 1'

            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    row = await conn.fetchrow(query)
            else:
                row = await conn_or_pool.fetchrow(query)

            return int(row["id"]) if row else None
        except Exception:
            return None

    @staticmethod
    def iter_lines(lines) -> Iterable:
        if not lines:
            return []
        if isinstance(lines, list):
            return lines
        try:
            return list(lines)
        except Exception:
            return []

    @classmethod
    async def get_order_lines(cls, order, allow_db_fallback: bool = False):
        lines = getattr(order, "order_line", None)

        if lines:
            try:
                if hasattr(lines, "load_data"):
                    await lines.load_data()
            except Exception:
                pass

            materialized = cls.iter_lines(lines)
            if materialized:
                return materialized

        if not allow_db_fallback:
            return []

        SaleOrderLineModel = Registry.get_model("sale.order.line")
        if not SaleOrderLineModel:
            return []

        try:
            rs = await SaleOrderLineModel.search(
                [("order_id", "=", order.id)],
                context=order.graph,
            )
            if rs and hasattr(rs, "load_data"):
                await rs.load_data()
            return cls.iter_lines(rs)
        except PermissionError:
            return []

    @staticmethod
    def is_commercial_line(line) -> bool:
        if isinstance(line, dict):
            return not line.get("display_type")
        return not getattr(line, "display_type", None)

    @staticmethod
    def line_subtotal(line) -> float:
        if isinstance(line, dict):
            return float(line.get("price_subtotal", 0.0) or 0.0)
        return float(getattr(line, "price_subtotal", 0.0) or 0.0)

    @staticmethod
    def line_invoice_status(line) -> str:
        if isinstance(line, dict):
            return str(line.get("invoice_status", "no") or "no")
        return str(getattr(line, "invoice_status", "no") or "no")

    @classmethod
    def recompute_onchange_total(cls, order):
        total = 0.0
        for line in cls.iter_lines(getattr(order, "order_line", [])):
            if cls.is_commercial_line(line):
                total += cls.line_subtotal(line)
        order.amount_total = total

    @classmethod
    async def compute_total_and_invoice_status(cls, order):
        """
        Calcula total e invoice_status SOLO desde el Graph.
        La BD NO manda aquí.
        """
        total = 0.0
        line_statuses = set()

        lines = await cls.get_order_lines(order, allow_db_fallback=False)

        for line in lines:
            if cls.is_commercial_line(line):
                total += cls.line_subtotal(line)
                line_statuses.add(cls.line_invoice_status(line))

        order.amount_total = total

        current_state = getattr(order, "state", "draft")
        if current_state not in ["sale", "done"]:
            order.invoice_status = "no"
        elif "to invoice" in line_statuses:
            order.invoice_status = "to invoice"
        elif line_statuses and all(status == "invoiced" for status in line_statuses):
            order.invoice_status = "invoiced"
        elif line_statuses and all(status in ["invoiced", "upselling"] for status in line_statuses):
            order.invoice_status = "upselling"
        else:
            order.invoice_status = "no"

    @staticmethod
    def check_company_consistency(order):
        if not order.company_id:
            raise ValueError("La orden debe tener compañía.")

        partner = getattr(order, "partner_id", None)
        if not partner:
            return

        try:
            partner_company = getattr(partner, "company_id", None)
            if partner_company:
                pc_id = partner_company.id if hasattr(partner_company, "id") else partner_company
                co_id = order.company_id.id if hasattr(order.company_id, "id") else order.company_id

                if pc_id and co_id and int(pc_id) != int(co_id):
                    raise ValueError("El contacto pertenece a otra compañía.")
        except AttributeError:
            pass

    @classmethod
    async def prepare_create_vals(cls, vals: Dict[str, Any]) -> Dict[str, Any]:
        vals = dict(vals or {})

        if not vals.get("company_id"):
            resolved = await cls.resolve_company_async()
            if resolved:
                vals["company_id"] = resolved

        if not vals.get("currency_id"):
            vals["currency_id"] = "PEN"

        if vals.get("name", "Nuevo") == "Nuevo":
            IrSequence = Registry.get_model("ir.sequence")
            if IrSequence:
                try:
                    new_name = await IrSequence.next_by_code("sale.order")
                    if new_name:
                        vals["name"] = new_name
                except ValueError:
                    pass

        return vals

    @staticmethod
    def sanitize_write_vals(order, vals: Dict[str, Any]) -> Dict[str, Any]:
        env = Context.get_env()
        vals = dict(vals or {})

        if not vals:
            return vals

        db_state = getattr(order, "state", "draft")
        if db_state in ["sale", "done"] and not (env and getattr(env, "su", False)):
            allowed = {"state", "invoice_status", "write_version", "write_date", "write_uid"}
            if not set(vals.keys()).issubset(allowed):
                print("⚠️ [WARNING] Intento de modificar pedido cerrado. Bloqueando.")
                vals = {k: v for k, v in vals.items() if k in allowed}

        return vals

    @classmethod
    async def ensure_confirmable(cls, order):
        lines = await cls.get_order_lines(order, allow_db_fallback=True)
        commercial_lines = [line for line in lines if cls.is_commercial_line(line)]

        if not commercial_lines:
            raise ValueError("No puedes confirmar una venta sin líneas de pedido.")