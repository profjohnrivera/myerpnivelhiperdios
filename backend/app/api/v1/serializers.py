# backend/app/api/v1/serializers.py

import json
import datetime
import decimal
from typing import Any, Dict, List

from app.core.registry import Registry
from app.core.storage.postgres_storage import PostgresGraphStorage


async def _read_rows_bulk(storage: PostgresGraphStorage, model_name: str, record_ids: List[int]) -> Dict[int, dict]:
    clean_ids = [int(i) for i in record_ids if str(i).isdigit()]
    if not clean_ids:
        return {}

    conn_or_pool = await storage.get_connection()
    table_name = model_name.replace(".", "_")

    try:
        query = f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])'
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                rows = await conn.fetch(query, clean_ids)
        else:
            rows = await conn_or_pool.fetch(query, clean_ids)

        result_map: Dict[int, dict] = {}
        for row in rows:
            row_dict: dict = {}
            for col, val in row.items():
                if col == "x_ext" and val:
                    extra = json.loads(val) if isinstance(val, str) else dict(val)
                    row_dict.update(extra)
                else:
                    row_dict[col] = storage._parse_db_value(val)
            result_map[row["id"]] = row_dict
        return result_map
    except Exception:
        return {}


def _find_inverse_field(child_model_name: str, parent_model_name: str, parent_field_name: str | None = None) -> str:
    if parent_field_name:
        parent_cls = Registry.get_model(parent_model_name)
        parent_attr = getattr(parent_cls, parent_field_name, None)
        if parent_attr and hasattr(parent_attr, "inverse_name") and parent_attr.inverse_name:
            return parent_attr.inverse_name

    child_cls = Registry.get_model(child_model_name)
    for fname in dir(child_cls):
        attr = getattr(child_cls, fname, None)
        if hasattr(attr, "get_meta"):
            meta = attr.get_meta()
            if meta.get("type") == "relation":
                target = getattr(attr, "related_model", "") or meta.get("target", "")
                if Registry._resolve_name(str(target)) == parent_model_name:
                    return fname

    return parent_model_name.split(".")[-1] + "_id"


async def _serialize_records(env, records, model_name: str, fields: List[str] | None = None) -> List[dict]:
    if not records:
        return []

    storage = PostgresGraphStorage()
    record_ids = [r.id for r in records if str(r.id).isdigit()]
    if not record_ids:
        return []

    rows_map = await _read_rows_bulk(storage, model_name, record_ids)
    model_cls = Registry.get_model(model_name)

    m2o_fields: dict = {}
    o2m_fields: dict = {}
    m2m_fields: dict = {}

    for fname in dir(model_cls):
        if fields and fname not in fields and fname != "id":
            continue

        attr = getattr(model_cls, fname, None)
        if not hasattr(attr, "get_meta"):
            continue

        meta = attr.get_meta()
        ftype = meta.get("type")

        if ftype in ("relation", "many2one"):
            m2o_fields[fname] = getattr(attr, "related_model", None) or meta.get("target")
        elif ftype == "one2many":
            o2m_fields[fname] = getattr(attr, "related_model", None) or meta.get("target")
        elif ftype == "many2many":
            m2m_fields[fname] = getattr(attr, "related_model", None) or meta.get("target")

    base_rows = [rows_map.get(rid, {"id": rid}) for rid in record_ids]

    # M2O
    for fname, target_model in m2o_fields.items():
        if not target_model:
            continue

        target_cls = Registry.get_model(target_model)
        rec_name = getattr(target_cls, "_rec_name", "name")
        target_ids = list({
            row[fname]
            for row in base_rows
            if row.get(fname) and not isinstance(row[fname], list)
        })
        target_int_ids = [int(i) for i in target_ids if str(i).isdigit()]

        if target_int_ids:
            target_rows = await _read_rows_bulk(storage, target_model, target_int_ids)
            for row in base_rows:
                raw_id = row.get(fname)
                if raw_id and str(raw_id).isdigit():
                    raw_id = int(raw_id)
                    display = (
                        target_rows.get(raw_id, {}).get(rec_name)
                        or target_rows.get(raw_id, {}).get("name")
                        or str(raw_id)
                    )
                    row[fname] = [raw_id, display] if raw_id in target_rows else [raw_id, str(raw_id)]

    # O2M
    for fname, target_model in o2m_fields.items():
        if not target_model:
            for row in base_rows:
                row[fname] = []
            continue

        inverse_field = _find_inverse_field(target_model, model_name, fname)
        conn_or_pool = await storage.get_connection()
        table_name = target_model.replace(".", "_")

        try:
            query = f'SELECT * FROM "{table_name}" WHERE "{inverse_field}" = ANY($1::bigint[])'
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    child_rows_raw = await conn.fetch(query, record_ids)
            else:
                child_rows_raw = await conn_or_pool.fetch(query, record_ids)

            children_list: List[dict] = []
            for crow in child_rows_raw:
                cdict: dict = {}
                for col, val in crow.items():
                    if col == "x_ext" and val:
                        cdict.update(json.loads(val) if isinstance(val, str) else dict(val))
                    else:
                        cdict[col] = storage._parse_db_value(val)
                children_list.append(cdict)
        except Exception:
            children_list = []

        target_cls = Registry.get_model(target_model)
        child_m2o_fields: dict = {}

        for cfname in dir(target_cls):
            cattr = getattr(target_cls, cfname, None)
            if hasattr(cattr, "get_meta"):
                cmeta = cattr.get_meta()
                if cmeta.get("type") in ("relation", "many2one"):
                    child_m2o_fields[cfname] = getattr(cattr, "related_model", None) or cmeta.get("target")

        for cfname, crel_model in child_m2o_fields.items():
            if not crel_model:
                continue

            crel_cls = Registry.get_model(crel_model)
            crec_name = getattr(crel_cls, "_rec_name", "name")
            crel_ids = list({
                c[cfname]
                for c in children_list
                if c.get(cfname) and not isinstance(c[cfname], list)
            })
            crel_int_ids = [int(i) for i in crel_ids if str(i).isdigit()]

            if crel_int_ids:
                crel_rows = await _read_rows_bulk(storage, crel_model, crel_int_ids)
                for c in children_list:
                    raw_id = c.get(cfname)
                    if raw_id and str(raw_id).isdigit():
                        raw_id = int(raw_id)
                        display = (
                            crel_rows.get(raw_id, {}).get(crec_name)
                            or crel_rows.get(raw_id, {}).get("name")
                            or str(raw_id)
                        )
                        c[cfname] = [raw_id, display]

        crec_name_field = getattr(target_cls, "_rec_name", "name")
        grouped_children = {rid: [] for rid in record_ids}

        for c in children_list:
            if crec_name_field and crec_name_field in c and "name" not in c:
                c["name"] = c[crec_name_field]

            p_id = c.get(inverse_field)
            if isinstance(p_id, list) and p_id:
                p_id = p_id[0]
            if p_id:
                grouped_children.setdefault(p_id, []).append(c)

        for row in base_rows:
            row[fname] = grouped_children.get(row.get("id"), [])

    # M2M
    for fname, target_model in m2m_fields.items():
        if not target_model:
            for row in base_rows:
                row[fname] = []
            continue

        parent_table = model_name.replace(".", "_")
        rel_table = f"{parent_table}_{fname}_rel"
        target_table = target_model.replace(".", "_")

        try:
            conn_or_pool = await storage.get_connection()
            q_rel = f'SELECT base_id, rel_id FROM "{rel_table}" WHERE base_id = ANY($1::bigint[])'
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    rel_rows = await conn.fetch(q_rel, record_ids)
            else:
                rel_rows = await conn_or_pool.fetch(q_rel, record_ids)

            all_rel_ids = list({int(r["rel_id"]) for r in rel_rows})
            target_data: dict = {}

            if all_rel_ids:
                try:
                    target_cls = Registry.get_model(target_model)
                    rec_name_field = getattr(target_cls, "_rec_name", "name") if target_cls else "name"
                    has_color = bool(target_cls and hasattr(target_cls, "color"))
                    cols = f'"id", "{rec_name_field}"' + (', "color"' if has_color else "")
                    q_target = f'SELECT {cols} FROM "{target_table}" WHERE id = ANY($1::bigint[])'
                    if hasattr(conn_or_pool, "acquire"):
                        async with conn_or_pool.acquire() as conn:
                            target_rows = await conn.fetch(q_target, all_rel_ids)
                    else:
                        target_rows = await conn_or_pool.fetch(q_target, all_rel_ids)

                    for tr in target_rows:
                        obj = {"id": tr["id"], "name": tr.get(rec_name_field) or str(tr["id"])}
                        if has_color:
                            obj["color"] = tr.get("color", 0)
                        target_data[tr["id"]] = obj
                except Exception:
                    for rid in all_rel_ids:
                        target_data[rid] = {"id": rid, "name": str(rid)}

            m2m_map: dict = {rid: [] for rid in record_ids}
            for rel_row in rel_rows:
                bid = rel_row["base_id"]
                rid = int(rel_row["rel_id"])
                obj = target_data.get(rid, {"id": rid, "name": str(rid)})
                m2m_map.setdefault(bid, []).append(obj)

            for row in base_rows:
                row[fname] = m2m_map.get(row.get("id"), [])
        except Exception:
            for row in base_rows:
                row[fname] = []

    return base_rows


async def _serialize_record(env, record, model_name: str) -> dict:
    results = await _serialize_records(env, [record], model_name)
    return results[0] if results else {}


def _clean_m2o_payload(vals: dict, model_name: str | None = None) -> dict:
    """
    Limpia el payload del frontend:
    - Many2One [id, "nombre"] → extrae solo el id entero
    - Many2Many [1,2] o [{id:1}] → lista de IDs enteros
    - *_id → normaliza a entero
    """
    m2m_field_names = set()

    if model_name:
        try:
            model_cls = Registry.get_model(model_name)
            for fname in dir(model_cls):
                attr = getattr(model_cls, fname, None)
                if hasattr(attr, "get_meta") and attr.get_meta().get("type") == "many2many":
                    m2m_field_names.add(fname)
        except Exception:
            pass

    safe_vals: dict = {}
    for k, v in vals.items():
        if k == "id":
            continue

        if k in m2m_field_names:
            if isinstance(v, list):
                clean = []
                for item in v:
                    if isinstance(item, dict):
                        _id = item.get("id")
                        if _id is not None and str(_id).isdigit():
                            clean.append(int(_id))
                    elif str(item).isdigit():
                        clean.append(int(item))
                safe_vals[k] = clean
            else:
                safe_vals[k] = v

        elif isinstance(v, list) and len(v) >= 2:
            clean_id = v[0]
            safe_vals[k] = int(clean_id) if str(clean_id).isdigit() else clean_id

        elif k.endswith("_id") and isinstance(v, (int, float, str)):
            safe_vals[k] = int(v) if str(v).isdigit() else v

        else:
            safe_vals[k] = v

    return safe_vals