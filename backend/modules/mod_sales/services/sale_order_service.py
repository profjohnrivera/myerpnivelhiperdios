# backend/modules/mod_sales/services/sale_order_service.py

from typing import Dict, Any, Iterable, List

from app.core.registry import Registry
from app.core.env import Context


class SaleOrderService:
    """
    🧠 SERVICIO DE NEGOCIO DE PEDIDOS DE VENTA

    P1-A:
    - el agregado del pedido vive en el dominio
    - la API no corrige amount_total por SQL
    - las líneas pueden mantener sincronizado al padre dentro del graph
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
        """
        Extrae líneas del pedido.

        Estrategia:
        1. Graph actual (si ya están materializadas)
        2. Fallback a BD solo cuando se pide explícitamente
        """
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

    @staticmethod
    def line_id(line) -> str | None:
        if isinstance(line, dict):
            raw = line.get("id")
        else:
            raw = getattr(line, "id", None)

        if raw is None:
            return None
        return str(raw)

    @classmethod
    def _calculate_aggregates(cls, order, lines) -> tuple[float, str]:
        """
        Calcula amount_total e invoice_status a partir de una colección de líneas.
        No toca BD.
        """
        total = 0.0
        line_statuses = set()

        for line in cls.iter_lines(lines):
            if cls.is_commercial_line(line):
                total += cls.line_subtotal(line)
                line_statuses.add(cls.line_invoice_status(line))

        current_state = getattr(order, "state", "draft")

        if current_state not in ["sale", "done"]:
            invoice_status = "no"
        elif "to invoice" in line_statuses:
            invoice_status = "to invoice"
        elif line_statuses and all(status == "invoiced" for status in line_statuses):
            invoice_status = "invoiced"
        elif line_statuses and all(status in ["invoiced", "upselling"] for status in line_statuses):
            invoice_status = "upselling"
        else:
            invoice_status = "no"

        return float(total), invoice_status

    @classmethod
    def recompute_onchange_total(cls, order):
        total, _ = cls._calculate_aggregates(
            order,
            cls.iter_lines(getattr(order, "order_line", [])),
        )
        order.amount_total = total

    @classmethod
    async def compute_total_and_invoice_status(cls, order):
        """
        Compute oficial del pedido.
        """
        lines = await cls.get_order_lines(order, allow_db_fallback=False)
        total, invoice_status = cls._calculate_aggregates(order, lines)

        order.amount_total = total
        order.invoice_status = invoice_status

    @classmethod
    def _merge_or_append_current_line(cls, lines: List, current_line) -> List:
        """
        Reemplaza la versión persistida de una línea por su versión viva
        en el graph, o la agrega si todavía no existe en BD.
        """
        current_id = cls.line_id(current_line)
        if current_id is None:
            return list(lines)

        merged = []
        replaced = False

        for line in cls.iter_lines(lines):
            if cls.line_id(line) == current_id:
                merged.append(current_line)
                replaced = True
            else:
                merged.append(line)

        if not replaced:
            merged.append(current_line)

        return merged

    @classmethod
    def _remove_line_from_collection(cls, lines: List, line_to_remove) -> List:
        remove_id = cls.line_id(line_to_remove)
        if remove_id is None:
            return list(lines)

        return [line for line in cls.iter_lines(lines) if cls.line_id(line) != remove_id]

    @classmethod
    async def sync_order_aggregates_for_line(
        cls,
        line,
        *,
        removing: bool = False,
        explicit_order=None,
    ) -> None:
        """
        Sincroniza amount_total e invoice_status del pedido padre
        desde el dominio, sin SQL correctivo en la API.

        Estrategia:
        - toma las líneas persistidas visibles para el pedido
        - fusiona o elimina la línea viva del graph según corresponda
        - recalcula agregados y los deja marcados en el graph del pedido
        """
        order = explicit_order or getattr(line, "order_id", None)
        if not order:
            return

        # Para pedidos nuevos no persistidos, el create padre volverá a calcular
        # correctamente al final del flujo. Aquí no forzamos fallback extraño.
        if not str(getattr(order, "id", "")).isdigit():
            return

        lines = await cls.get_order_lines(order, allow_db_fallback=True)

        if removing:
            effective_lines = cls._remove_line_from_collection(lines, line)
        else:
            effective_lines = cls._merge_or_append_current_line(lines, line)

        total, invoice_status = cls._calculate_aggregates(order, effective_lines)

        order.amount_total = total
        order.invoice_status = invoice_status

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