# backend/tests/helpers.py

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, Optional

from app.api.v1.runtime import request_env
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.transaction import transaction


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def extract_id(value: Any) -> Optional[int]:
    """
    Extrae un id int de:
    - int
    - "12"
    - objeto con .id
    - [id, display_name]
    - {"id": ...}
    """
    if value is None or value is False:
        return None

    if hasattr(value, "id"):
        raw = value.id
        return int(raw) if str(raw).isdigit() else None

    if isinstance(value, (list, tuple)) and value:
        raw = value[0]
        return int(raw) if str(raw).isdigit() else None

    if isinstance(value, dict) and value.get("id") is not None:
        raw = value["id"]
        return int(raw) if str(raw).isdigit() else None

    return int(value) if str(value).isdigit() else None


async def persist_graph(session_graph) -> dict:
    storage = PostgresGraphStorage()
    return await storage.save(session_graph)


async def finalize_record(record, session_graph) -> int:
    """
    Persiste el graph actual y, si el record sigue con id temporal,
    lo parchea con el id real devuelto por save().
    """
    id_mapping = await persist_graph(session_graph)

    current_id = str(getattr(record, "id", ""))
    if current_id in id_mapping:
        record._id_val = id_mapping[current_id]

    return int(record.id) if str(record.id).isdigit() else record.id


@asynccontextmanager
async def tx_env(user_id: int | str):
    """
    Flujo canónico de mutación:
    transaction() + request_env()
    """
    async with transaction():
        async with request_env(user_id) as (env, session_graph):
            yield env, session_graph


async def get_conn():
    storage = PostgresGraphStorage()
    return await storage.get_connection()


async def fetch_user(user_id: int | str) -> dict:
    async with request_env("system") as (env, session_graph):
        rs = env["res.users"].browse([int(user_id)], context=session_graph)
        await rs.load_data()
        rows = await rs.read(["id", "name", "login", "company_id", "partner_id", "group_ids"])
        return rows[0]


async def create_company(prefix: str) -> int:
    async with tx_env("system") as (env, session_graph):
        company = await env["res.company"].create(
            {"name": unique_name(f"{prefix}_company")},
            context=session_graph,
        )
        return await finalize_record(company, session_graph)


async def create_partner(prefix: str, company_id: int, user_id: int | str = "system") -> int:
    async with tx_env(user_id) as (env, session_graph):
        partner = await env["res.partner"].create(
            {
                "name": unique_name(f"{prefix}_partner"),
                "company_id": company_id,
            },
            context=session_graph,
        )
        return await finalize_record(partner, session_graph)


async def create_product(prefix: str, price: float = 1.0) -> int:
    async with tx_env("system") as (env, session_graph):
        product = await env["product.product"].create(
            {
                "name": unique_name(f"{prefix}_product"),
                "list_price": float(price),
                "standard_price": 0.0,
                "type": "product",
            },
            context=session_graph,
        )
        return await finalize_record(product, session_graph)


async def create_user(prefix: str, company_id: int, is_admin: bool = False) -> dict:
    """
    Crea usuario real vía ORM y, si corresponde, lo vincula al grupo admin técnico.
    """
    login = unique_name(prefix).lower()

    async with tx_env("system") as (env, session_graph):
        user = await env["res.users"].create(
            {
                "name": login,
                "login": login,
                "password": "admin",
                "company_id": company_id,
                "active": True,
            },
            context=session_graph,
        )
        user_id = await finalize_record(user, session_graph)

        if is_admin:
            conn = await get_conn()
            admin_group_id = await conn.fetchval(
                'SELECT id FROM "res_groups" WHERE is_system_admin = TRUE ORDER BY id LIMIT 1'
            )
            if admin_group_id:
                exists = await conn.fetchval(
                    'SELECT 1 FROM "res_users_group_ids_rel" WHERE base_id = $1 AND rel_id = $2',
                    int(user_id),
                    int(admin_group_id),
                )
                if not exists:
                    await conn.execute(
                        'INSERT INTO "res_users_group_ids_rel" (base_id, rel_id) VALUES ($1, $2)',
                        int(user_id),
                        int(admin_group_id),
                    )

        rs = env["res.users"].browse([int(user_id)], context=session_graph)
        await rs.load_data()
        rows = await rs.read(["id", "name", "login", "company_id", "partner_id"])
        row = rows[0]

        return {
            "id": int(row["id"]),
            "login": row["login"],
            "password": "admin",
            "name": row["name"],
            "company_id": extract_id(row.get("company_id")) or company_id,
            "partner_id": extract_id(row.get("partner_id")),
            "is_admin": bool(is_admin),
        }


async def create_test_record(prefix: str, user_id: int | str = "system") -> int:
    async with tx_env(user_id) as (env, session_graph):
        rec = await env["test.record"].create(
            {
                "name": unique_name(f"{prefix}_record"),
                "description": "constitutional test",
                "status": "draft",
            },
            context=session_graph,
        )
        return await finalize_record(rec, session_graph)


async def create_sale_order(
    user_id: int | str,
    prefix: str,
    company_id: int,
    partner_id: int,
    product_id: Optional[int] = None,
    line_specs: Optional[list[dict]] = None,
) -> int:
    vals: Dict[str, Any] = {
        "name": "Nuevo",
        "company_id": company_id,
        "partner_id": partner_id,
        "currency_id": "PEN",
    }

    if line_specs:
        vals["order_line"] = []
        for spec in line_specs:
            vals["order_line"].append(
                {
                    "product_id": spec.get("product_id", product_id),
                    "name": spec.get("name", "Línea de prueba"),
                    "product_uom_qty": float(spec.get("qty", 1.0)),
                    "price_unit": float(spec.get("price", 1.0)),
                }
            )

    async with tx_env(user_id) as (env, session_graph):
        order = await env["sale.order"].create(vals, context=session_graph)
        return await finalize_record(order, session_graph)


async def create_sale_order_line(
    user_id: int | str,
    order_id: int,
    product_id: int,
    qty: float = 1.0,
    price: float = 1.0,
    name: str = "Línea adicional",
) -> int:
    async with tx_env(user_id) as (env, session_graph):
        line = await env["sale.order.line"].create(
            {
                "order_id": order_id,
                "product_id": product_id,
                "name": name,
                "product_uom_qty": float(qty),
                "price_unit": float(price),
            },
            context=session_graph,
        )
        return await finalize_record(line, session_graph)


async def create_category(name_prefix: str, parent_id: Optional[int] = None) -> int:
    """
    product.category hereda TreeModel.
    """
    async with tx_env("system") as (env, session_graph):
        vals = {"name": unique_name(name_prefix)}
        if parent_id:
            vals["parent_id"] = parent_id

        category = await env["product.category"].create(vals)
        return await finalize_record(category, session_graph)


async def search_ids(user_id: int | str, model_name: str, domain: list) -> list[int]:
    async with request_env(user_id) as (env, session_graph):
        rs = await env[model_name].search(domain, context=session_graph)
        return [int(rec.id) for rec in rs if str(rec.id).isdigit()]


async def read_single(user_id: int | str, model_name: str, record_id: int, fields: Optional[list[str]] = None) -> dict:
    async with request_env(user_id) as (env, session_graph):
        rs = env[model_name].browse([record_id], context=session_graph)
        await rs.load_data()
        rows = await rs.read(fields=fields)
        return rows[0]


async def write_model(user_id: int | str, model_name: str, record_id: int, vals: dict) -> None:
    async with tx_env(user_id) as (env, session_graph):
        rs = env[model_name].browse([record_id], context=session_graph)
        await rs.load_data()
        await rs[0].write(vals)
        await persist_graph(session_graph)


async def unlink_model(user_id: int | str, model_name: str, record_id: int) -> None:
    async with tx_env(user_id) as (env, session_graph):
        rs = env[model_name].browse([record_id], context=session_graph)
        await rs.load_data()
        await rs[0].unlink()
        await persist_graph(session_graph)


async def order_snapshot(user_id: int | str, order_id: int) -> dict:
    row = await read_single(
        user_id,
        "sale.order",
        order_id,
        fields=["id", "name", "amount_total", "invoice_status", "order_line", "state"],
    )
    lines = row.get("order_line") or []
    lines_total = sum(float(line.get("price_subtotal", 0.0) or 0.0) for line in lines)

    return {
        "id": row["id"],
        "name": row["name"],
        "amount_total": float(row.get("amount_total", 0.0) or 0.0),
        "invoice_status": row.get("invoice_status"),
        "state": row.get("state"),
        "lines": lines,
        "lines_total": float(lines_total),
    }


async def order_line_ids(user_id: int | str, order_id: int) -> list[int]:
    return await search_ids(user_id, "sale.order.line", [("order_id", "=", order_id)])