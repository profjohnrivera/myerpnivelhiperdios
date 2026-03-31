# backend/modules/mod_sales/services/sale_order_service.py

from typing import Dict, Any, Iterable, List

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
    - cálculo de total / invoice_status desde una fuente de verdad consistente
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
        Ya no usa contrato ambiguo pool/conn.
        """
        sync_result = cls.resolve_company_from_env()
        if sync_result:
            return int(sync_result)

        try:
            from app.core.storage.postgres_storage import PostgresGraphStorage

            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            row = await conn.fetchrow('SELECT id FROM "res_company" ORDER BY id LIMIT 1')
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

    @staticmethod
    def _order_identity(order_value) -> int | None:
        if not order_value:
            return None
        raw = order_value.id if hasattr(order_value, "id") else order_value
        return int(raw) if str(raw).isdigit() else None

    @staticmethod
    def _is_line_object(line) -> bool:
        if isinstance(line, dict):
            return True

        if hasattr(line, "_get_model_name"):
            try:
                return line._get_model_name() == "sale.order.line"
            except Exception:
                pass

        return hasattr(line, "price_subtotal") or hasattr(line, "order_id") or hasattr(line, "product_uom_qty")

    @staticmethod
    def _line_identity(line) -> str | None:
        if isinstance(line, dict):
            raw = line.get("id")
        elif hasattr(line, "id"):
            raw = line.id
        else:
            raw = None

        if raw in (None, False, ""):
            return None
        return str(raw)

    @classmethod
    def _extract_line_ids(cls, lines) -> List[int]:
        ids: List[int] = []

        for line in cls.iter_lines(lines):
            if isinstance(line, dict):
                raw = line.get("id")
            elif hasattr(line, "id"):
                raw = line.id
            else:
                raw = line

            if str(raw).isdigit():
                ids.append(int(raw))

        unique_ids = []
        seen = set()
        for lid in ids:
            if lid not in seen:
                unique_ids.append(lid)
                seen.add(lid)
        return unique_ids

    @classmethod
    async def _load_lines_by_ids(cls, line_ids: List[int], graph=None):
        if not line_ids:
            return []

        SaleOrderLineModel = Registry.get_model("sale.order.line")
        if not SaleOrderLineModel:
            return []

        rs = await SaleOrderLineModel.search([("id", "in", line_ids)], context=graph)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        materialized = cls.iter_lines(rs)
        by_id = {}
        for line in materialized:
            if hasattr(line, "id") and str(line.id).isdigit():
                by_id[int(line.id)] = line

        return [by_id[lid] for lid in line_ids if lid in by_id]

    @classmethod
    async def _load_order_record(cls, order_value, graph=None):
        order_id = cls._order_identity(order_value)
        if not order_id:
            return None

        OrderModel = Registry.get_model("sale.order")
        if not OrderModel:
            return None

        rs = await OrderModel.search([("id", "=", order_id)], context=graph)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        return rs[0] if rs and len(rs) > 0 else None

    @classmethod
    def _graph_lines_for_order(cls, order_id: int, graph) -> List:
        """
        Extrae líneas vivas del graph actual, incluyendo líneas nuevas todavía
        no persistidas.
        """
        if not graph or not str(order_id).isdigit():
            return []

        SaleOrderLineModel = Registry.get_model("sale.order.line")
        if not SaleOrderLineModel:
            return []

        values = getattr(graph, "_values", None)
        if values is None or not hasattr(values, "keys"):
            return []

        env = Context.get_env()
        found = []
        seen = set()

        for key in list(values.keys()):
            if not (isinstance(key, tuple) and len(key) == 3):
                continue
            if key[0] != "sale.order.line" or key[2] != "order_id":
                continue

            line_id = key[1]
            raw_order = values.get(key)

            resolved_order_id = None
            if hasattr(raw_order, "id"):
                resolved_order_id = cls._order_identity(raw_order.id)
            else:
                resolved_order_id = cls._order_identity(raw_order)

            if resolved_order_id != int(order_id):
                continue

            if line_id in seen:
                continue

            seen.add(line_id)
            found.append(SaleOrderLineModel(_id=line_id, context=graph, env=env))

        return found

    @classmethod
    def _merge_line_sources(cls, *collections) -> List:
        """
        Merge estable por id:
        - fuentes posteriores pisan a las anteriores
        - graph gana sobre DB
        """
        merged = {}
        anon_idx = 0

        for collection in collections:
            for line in cls.iter_lines(collection):
                key = cls._line_identity(line)
                if key is None:
                    key = f"anon:{anon_idx}"
                    anon_idx += 1
                merged[key] = line

        return list(merged.values())

    @classmethod
    async def get_order_lines(cls, order, allow_db_fallback: bool = True):
        """
        Fuente de verdad correcta:
        - pedido NUEVO (id temporal): usar relación en memoria
        - pedido persistido: usar DB + graph actual
        """
        graph = getattr(order, "graph", None)
        order_id = cls._order_identity(getattr(order, "id", None))

        # Pedido virtual/new: solo memoria
        if not str(order_id).isdigit():
            lines = getattr(order, "order_line", None)

            if lines:
                try:
                    if hasattr(lines, "load_data"):
                        await lines.load_data()
                except Exception:
                    pass

                materialized = cls.iter_lines(lines)

                if materialized:
                    if all(cls._is_line_object(item) for item in materialized):
                        return materialized

                    line_ids = cls._extract_line_ids(materialized)
                    if line_ids:
                        resolved = await cls._load_lines_by_ids(line_ids, graph=graph)
                        if resolved:
                            return resolved

            return []

        # Pedido persistido: DB + graph
        db_lines = []
        if allow_db_fallback:
            SaleOrderLineModel = Registry.get_model("sale.order.line")
            if SaleOrderLineModel:
                try:
                    rs = await SaleOrderLineModel.search(
                        [("order_id", "=", int(order_id))],
                        context=graph,
                    )
                    if rs and hasattr(rs, "load_data"):
                        await rs.load_data()
                    db_lines = cls.iter_lines(rs)
                except PermissionError:
                    db_lines = []

        graph_lines = cls._graph_lines_for_order(int(order_id), graph)

        return cls._merge_line_sources(db_lines, graph_lines)

    @staticmethod
    def is_commercial_line(line) -> bool:
        if isinstance(line, dict):
            return not line.get("display_type")

        if hasattr(line, "display_type"):
            return not getattr(line, "display_type", None)

        return False

    @staticmethod
    def line_subtotal(line) -> float:
        if isinstance(line, dict):
            return float(line.get("price_subtotal", 0.0) or 0.0)

        if hasattr(line, "price_subtotal"):
            return float(getattr(line, "price_subtotal", 0.0) or 0.0)

        return 0.0

    @staticmethod
    def line_invoice_status(line) -> str:
        if isinstance(line, dict):
            return str(line.get("invoice_status", "no") or "no")

        if hasattr(line, "invoice_status"):
            return str(getattr(line, "invoice_status", "no") or "no")

        return "no"

    @classmethod
    def _apply_aggregate_result(cls, order, total: float, line_statuses: set[str]):
        order.amount_total = float(total or 0.0)

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

    @classmethod
    def recompute_onchange_total(cls, order):
        """
        Onchange puro de UI:
        usa solo lo que ya esté en memoria del formulario.
        """
        total = 0.0
        statuses = set()

        for line in cls.iter_lines(getattr(order, "order_line", [])):
            if not cls._is_line_object(line):
                continue
            if cls.is_commercial_line(line):
                total += cls.line_subtotal(line)
                statuses.add(cls.line_invoice_status(line))

        cls._apply_aggregate_result(order, total, statuses)

    @classmethod
    async def compute_total_and_invoice_status(cls, order):
        """
        Recompute robusto:
        nunca se queda solo con una relación mal materializada.
        """
        total = 0.0
        line_statuses = set()

        lines = await cls.get_order_lines(order, allow_db_fallback=True)

        for line in lines:
            if cls.is_commercial_line(line):
                total += cls.line_subtotal(line)
                line_statuses.add(cls.line_invoice_status(line))

        cls._apply_aggregate_result(order, total, line_statuses)

    @classmethod
    async def recompute_parent_from_value(cls, order_value, graph=None):
        """
        Recalcula el agregado del pedido padre y lo deja dirty en el graph actual.
        """
        order = await cls._load_order_record(order_value, graph=graph)
        if not order:
            return

        await cls.compute_total_and_invoice_status(order)

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