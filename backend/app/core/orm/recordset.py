# backend/app/core/orm/recordset.py

from typing import Any, Dict, List, Optional, Type, Callable
import asyncio
import datetime
import decimal
import json

from app.core.graph import Graph
from app.core.env import Context, Env
from app.core.event_bus import EventBus

from .fields import ComputedField, One2manyField
from .savepoint import AsyncGraphSavepoint


class Recordset:
    def __init__(self, model_class: Type, records: List[Any], env: Optional[Env] = None):
        self._model_class = model_class
        self._records = records
        self._env = env or Context.get_env()

    def __iter__(self):
        return iter(self._records)

    def __len__(self):
        return len(self._records)

    def __bool__(self):
        return bool(self._records)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Recordset(self._model_class, self._records[index], self._env)
        return self._records[index]

    def sudo(self):
        sudo_env = self._env.sudo() if self._env else Env(su=True)
        return Recordset(self._model_class, self._records, sudo_env)

    def _get_env(self) -> Optional[Env]:
        return self._env or Context.get_env()

    def _get_graph(self) -> Graph:
        if self._records:
            first = self._records[0]
            if hasattr(first, "graph") and first.graph:
                return first.graph
        env = self._get_env()
        return (env.graph if env else None) or Context.get_graph() or Graph()

    async def _run_computes(self):
        if not self._records:
            return

        computes = {}
        for attr_name in dir(self._model_class):
            attr = getattr(self._model_class, attr_name, None)
            if isinstance(attr, ComputedField):
                computes[attr_name] = attr

        if not computes:
            return

        visited = set()
        temp_mark = set()
        ordered = []

        def visit(node):
            if node in temp_mark:
                return
            if node not in visited:
                temp_mark.add(node)
                attr = computes.get(node)
                if attr and getattr(attr, "depends_on", None):
                    for dep in attr.depends_on:
                        dep_base = dep.split(".")[0]
                        if dep_base in computes:
                            visit(dep_base)
                temp_mark.remove(node)
                visited.add(node)
                ordered.append(node)

        for node in computes.keys():
            visit(node)

        for attr_name in ordered:
            attr = computes[attr_name]
            if asyncio.iscoroutinefunction(attr.func):
                await attr.func(self)
            else:
                attr.func(self)

    async def _check_acl(self, operation: str = "read") -> None:
        env = self._get_env()
        if not env or getattr(env, "su", False) or str(getattr(env, "uid", "")) == "system":
            return

        model_name = self._model_class._get_model_name()

        from app.core.registry import Registry

        try:
            IrModelAccess = Registry.get_model("ir.model.access")
        except Exception:
            return

        allowed = await IrModelAccess.check_access(model_name, env.uid, operation)
        if not allowed:
            raise PermissionError(
                f"🛑 [SECURITY BLOCK] ACL denegada para operación '{operation}' en modelo '{model_name}'."
            )

    async def _check_row_rules(self, operation: str = "read") -> None:
        if not self._records:
            return

        env = self._get_env()
        if not env or getattr(env, "su", False) or str(getattr(env, "uid", "")) == "system":
            return

        model_name = self._model_class._get_model_name()

        if model_name in ["ir.rule", "ir.model", "ir.model.fields", "ir.model.access", "ir.sequence"]:
            return

        from app.core.registry import Registry
        from app.core.storage.postgres_storage import PostgresGraphStorage

        try:
            IrRuleModel = Registry.get_model("ir.rule")
        except Exception:
            return

        user_domain = await IrRuleModel.get_domain(model_name, env.uid, operation=operation)
        if not user_domain:
            return

        ids = [r.id for r in self._records if str(r.id).isdigit()]
        if not ids:
            return

        storage = PostgresGraphStorage()
        allowed_ids = await storage.search_domain(
            model_name,
            ["&", ("id", "in", ids)] + user_domain,
            check_access=False,
        )

        if len(set(allowed_ids)) != len(set(ids)):
            raise PermissionError(
                f"🛑 [SECURITY BLOCK] RLS denegada para operación '{operation}' en modelo '{model_name}'."
            )

    async def _check_access(self, operation: str = "read") -> None:
        await self._check_acl(operation)
        await self._check_row_rules(operation)

    @staticmethod
    def _is_pool(conn_or_pool) -> bool:
        return hasattr(conn_or_pool, "acquire")

    async def _fetch(self, query: str, *args):
        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()

        if self._is_pool(conn_or_pool):
            async with conn_or_pool.acquire() as conn:
                return await conn.fetch(query, *args)
        return await conn_or_pool.fetch(query, *args)

    async def _fetchrow(self, query: str, *args):
        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()

        if self._is_pool(conn_or_pool):
            async with conn_or_pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        return await conn_or_pool.fetchrow(query, *args)

    @staticmethod
    def _row_to_dict(storage, row) -> Dict[str, Any]:
        row_dict: Dict[str, Any] = {}
        for col, val in row.items():
            if col == "x_ext" and val:
                extra = val if isinstance(val, dict) else (json.loads(val) if isinstance(val, str) else dict(val))
                row_dict.update(extra)
            else:
                row_dict[col] = storage._parse_db_value(val) if hasattr(storage, "_parse_db_value") else val
        return row_dict

    async def _read_rows_bulk(self, model_name: str, record_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        from app.core.storage.postgres_storage import PostgresGraphStorage

        clean_ids = [int(i) for i in record_ids if str(i).isdigit()]
        if not clean_ids:
            return {}

        storage = PostgresGraphStorage()
        table_name = model_name.replace(".", "_")

        try:
            rows = await self._fetch(f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])', clean_ids)
            return {int(row["id"]): self._row_to_dict(storage, row) for row in rows}
        except Exception as e:
            print(f"⚠️ Error leyendo filas bulk de {model_name}: {e}")
            return {}

    @staticmethod
    def _find_inverse_field(child_model_name: str, parent_model_name: str, parent_field_name: str | None = None) -> str:
        from app.core.registry import Registry

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
                if meta.get("type") in ("relation", "many2one"):
                    target = getattr(attr, "related_model", "") or meta.get("target", "")
                    if Registry._resolve_name(str(target)) == parent_model_name:
                        return fname

        return parent_model_name.split(".")[-1] + "_id"

    @staticmethod
    def _normalize_json_value(val: Any, translate: bool = False, lang: str = "en_US") -> Any:
        if translate and isinstance(val, dict):
            return val.get(lang, list(val.values())[0] if val else "")

        if isinstance(val, decimal.Decimal):
            return float(val)
        if isinstance(val, datetime.datetime):
            return val.isoformat()
        if isinstance(val, datetime.date):
            return val.isoformat()

        return val

    async def _resolve_m2o_cache(
        self,
        base_rows: List[Dict[str, Any]],
        m2o_fields: Dict[str, str],
    ) -> Dict[str, Dict[int, List[Any]]]:
        from app.core.registry import Registry

        m2o_cache: Dict[str, Dict[int, List[Any]]] = {}

        for fname, target_model in m2o_fields.items():
            if not target_model:
                continue

            target_cls = Registry.get_model(target_model)
            rec_name = getattr(target_cls, "_rec_name", "name")

            target_ids = list({
                row.get(fname)
                for row in base_rows
                if row.get(fname) and not isinstance(row.get(fname), list)
            })
            target_int_ids = [int(i) for i in target_ids if str(i).isdigit()]

            if not target_int_ids:
                m2o_cache[target_model] = {}
                continue

            target_rows = await self._read_rows_bulk(target_model, target_int_ids)
            resolved = {}

            for raw_id, row in target_rows.items():
                display = row.get(rec_name) or row.get("name") or row.get("display_name") or str(raw_id)
                resolved[int(raw_id)] = [int(raw_id), display]

            m2o_cache[target_model] = resolved

        return m2o_cache

    async def _resolve_o2m_payloads(
        self,
        parent_model: str,
        parent_ids: List[int],
        o2m_fields: Dict[str, str],
    ) -> Dict[str, Dict[int, List[Dict[str, Any]]]]:
        from app.core.registry import Registry
        from app.core.storage.postgres_storage import PostgresGraphStorage

        payloads: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        storage = PostgresGraphStorage()

        for field_name, target_model in o2m_fields.items():
            grouped_children: Dict[int, List[Dict[str, Any]]] = {pid: [] for pid in parent_ids}

            if not target_model:
                payloads[field_name] = grouped_children
                continue

            inverse_field = self._find_inverse_field(target_model, parent_model, field_name)
            child_table = target_model.replace(".", "_")

            try:
                child_rows_raw = await self._fetch(
                    f'SELECT * FROM "{child_table}" WHERE "{inverse_field}" = ANY($1::bigint[])',
                    parent_ids,
                )
            except Exception:
                payloads[field_name] = grouped_children
                continue

            child_model_cls = Registry.get_model(target_model)

            child_m2o_fields: Dict[str, str] = {}
            for cfname in dir(child_model_cls):
                cattr = getattr(child_model_cls, cfname, None)
                if hasattr(cattr, "get_meta"):
                    cmeta = cattr.get_meta()
                    if cmeta.get("type") in ("relation", "many2one"):
                        child_m2o_fields[cfname] = getattr(cattr, "related_model", None) or cmeta.get("target")

            children_list = []
            for row in child_rows_raw:
                children_list.append(self._row_to_dict(storage, row))

            child_m2o_cache = await self._resolve_m2o_cache(children_list, child_m2o_fields) if children_list else {}
            rec_name_field = getattr(child_model_cls, "_rec_name", "name")

            for child in children_list:
                for cfname, ctarget_model in child_m2o_fields.items():
                    raw_id = child.get(cfname)
                    if raw_id and str(raw_id).isdigit():
                        child[cfname] = child_m2o_cache.get(ctarget_model, {}).get(int(raw_id), [int(raw_id), str(raw_id)])

                if rec_name_field and rec_name_field in child and "name" not in child:
                    child["name"] = child[rec_name_field]

                p_id = child.get(inverse_field)
                if isinstance(p_id, list) and p_id:
                    p_id = p_id[0]
                if p_id and int(p_id) in grouped_children:
                    grouped_children[int(p_id)].append(child)

            payloads[field_name] = grouped_children

        return payloads

    async def _resolve_m2m_payloads(
        self,
        model_name: str,
        record_ids: List[int],
        m2m_fields: Dict[str, str],
    ) -> Dict[str, Dict[int, List[Dict[str, Any]]]]:
        from app.core.registry import Registry

        payloads: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        parent_table = model_name.replace(".", "_")

        for field_name, target_model in m2m_fields.items():
            grouped = {rid: [] for rid in record_ids}

            if not target_model:
                payloads[field_name] = grouped
                continue

            rel_table = f"{parent_table}_{field_name}_rel"
            target_table = target_model.replace(".", "_")

            try:
                rel_rows = await self._fetch(
                    f'SELECT base_id, rel_id FROM "{rel_table}" WHERE base_id = ANY($1::bigint[])',
                    record_ids,
                )
            except Exception:
                payloads[field_name] = grouped
                continue

            all_rel_ids = list({int(r["rel_id"]) for r in rel_rows if str(r["rel_id"]).isdigit()})
            target_data: Dict[int, Dict[str, Any]] = {}

            if all_rel_ids:
                try:
                    target_cls = Registry.get_model(target_model)
                    rec_name_field = getattr(target_cls, "_rec_name", "name") if target_cls else "name"
                    has_color = bool(target_cls and hasattr(target_cls, "color"))
                    cols = f'"id", "{rec_name_field}"' + (', "color"' if has_color else "")
                    target_rows = await self._fetch(
                        f'SELECT {cols} FROM "{target_table}" WHERE id = ANY($1::bigint[])',
                        all_rel_ids,
                    )

                    for tr in target_rows:
                        obj = {"id": tr["id"], "name": tr.get(rec_name_field) or str(tr["id"])}
                        if has_color:
                            obj["color"] = tr.get("color", 0)
                        target_data[int(tr["id"])] = obj
                except Exception:
                    for rid in all_rel_ids:
                        target_data[int(rid)] = {"id": int(rid), "name": str(rid)}

            for rel_row in rel_rows:
                bid = int(rel_row["base_id"])
                rid = int(rel_row["rel_id"])
                grouped.setdefault(bid, []).append(target_data.get(rid, {"id": rid, "name": str(rid)}))

            payloads[field_name] = grouped

        return payloads

    async def load_data(self) -> "Recordset":
        if not self._records:
            return self

        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        model_name = self._model_class._get_model_name()
        graph = self._get_graph()

        ids = [r.id for r in self._records if str(r.id).isdigit()]
        if not ids:
            return self

        table_name = model_name.replace(".", "_")

        try:
            rows = await self._fetch(f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])', ids)
            dirty_nodes = getattr(graph, "_dirty_nodes", set())

            for row in rows:
                row_id = row["id"]
                row_dict = self._row_to_dict(storage, row)
                for k, v in row_dict.items():
                    node_name = (model_name, row_id, k)
                    if node_name not in dirty_nodes:
                        graph._values[node_name] = v
        except Exception as e:
            print(f"⚠️ Error en Bulk Load de {model_name}: {e}")

        return self

    async def prefetch_related(self, fields: List[str]) -> "Recordset":
        if not self._records:
            return self

        await self.load_data()

        from app.core.registry import Registry
        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        graph = self._get_graph()
        env = self._get_env()

        for path in fields:
            parts = path.split(".")
            current_rs = self

            for part in parts:
                if not current_rs:
                    break

                model_cls = current_rs._model_class
                attr = getattr(model_cls, part, None)
                if not attr or not hasattr(attr, "get_meta"):
                    break

                meta = attr.get_meta()
                f_type = meta.get("type")
                target_model_name = getattr(attr, "related_model", None) or meta.get("target")
                if not target_model_name:
                    break

                TargetModel = Registry.get_model(target_model_name)
                target_table = target_model_name.replace(".", "_")
                next_rs_records = []

                if f_type in ["relation", "many2one"]:
                    target_ids = set()
                    for rec in current_rs:
                        val = rec.graph.get(rec._get_node_name(part))
                        if val is None and hasattr(rec, "_id_val"):
                            val = getattr(rec, part, None)

                        if val and hasattr(val, "id"):
                            target_ids.add(str(val.id))
                        elif val and isinstance(val, list):
                            target_ids.add(str(val[0]))
                        elif val and isinstance(val, str):
                            target_ids.add(val)
                        elif val and isinstance(val, int):
                            target_ids.add(str(val))

                    target_int_ids = [int(i) for i in target_ids if str(i).isdigit()]

                    if target_int_ids:
                        rows = await self._fetch(
                            f'SELECT * FROM "{target_table}" WHERE id = ANY($1::bigint[])',
                            target_int_ids,
                        )
                        dirty_nodes = getattr(graph, "_dirty_nodes", set())

                        for row in rows:
                            row_id = row["id"]
                            next_rs_records.append(TargetModel(_id=row_id, context=graph, env=env))
                            row_dict = self._row_to_dict(storage, row)
                            for k, v in row_dict.items():
                                node_name = (target_model_name, row_id, k)
                                if node_name not in dirty_nodes:
                                    graph._values[node_name] = v

                elif f_type == "one2many":
                    inverse = attr.inverse_name or f"{model_cls._get_model_name().split('.')[-1]}_id"
                    parent_ids = [r.id for r in current_rs if str(r.id).isdigit()]

                    if parent_ids:
                        rows = await self._fetch(
                            f'SELECT * FROM "{target_table}" WHERE "{inverse}" = ANY($1::bigint[])',
                            parent_ids,
                        )

                        grouped = {pid: [] for pid in parent_ids}
                        dirty_nodes = getattr(graph, "_dirty_nodes", set())

                        for row in rows:
                            row_id = row["id"]
                            p_id = row[inverse]
                            if p_id in grouped:
                                grouped[p_id].append(row_id)
                            next_rs_records.append(TargetModel(_id=row_id, context=graph, env=env))

                            row_dict = self._row_to_dict(storage, row)
                            for k, v in row_dict.items():
                                node_name = (target_model_name, row_id, k)
                                if node_name not in dirty_nodes:
                                    graph._values[node_name] = v

                        for rec in current_rs:
                            if not str(rec.id).isdigit():
                                continue

                            children_ids = grouped.get(rec.id, [])
                            children_instances = [
                                TargetModel(_id=cid, context=graph, env=env)
                                for cid in children_ids
                            ]
                            rec.graph.set_fact(
                                ("virtual", rec._get_model_name(), rec.id, part),
                                children_instances,
                            )
                            rec.graph.set_fact(rec._get_node_name(part), children_ids)

                current_rs = Recordset(TargetModel, next_rs_records, env)

        return self

    async def read(self, fields: List[str] = None) -> List[Dict[str, Any]]:
        await self._check_access("read")
        if not self._records:
            return []

        model_name = self._model_class._get_model_name()
        record_ids = [r.id for r in self._records if str(r.id).isdigit()]
        if not record_ids:
            return []

        rows_map = await self._read_rows_bulk(model_name, record_ids)
        if not rows_map:
            return []

        model_cls = self._model_class
        env = self._get_env()
        lang = getattr(env, "lang", "en_US") if env else "en_US"

        m2o_fields: Dict[str, str] = {}
        o2m_fields: Dict[str, str] = {}
        m2m_fields: Dict[str, str] = {}
        scalar_fields: Dict[str, Dict[str, Any]] = {}

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
            else:
                scalar_fields[fname] = meta

        base_rows = [dict(rows_map.get(int(rid), {"id": int(rid)})) for rid in record_ids]

        m2o_cache = await self._resolve_m2o_cache(base_rows, m2o_fields)
        o2m_payloads = await self._resolve_o2m_payloads(model_name, record_ids, o2m_fields)
        m2m_payloads = await self._resolve_m2m_payloads(model_name, record_ids, m2m_fields)

        results: List[Dict[str, Any]] = []

        for rec_id in record_ids:
            row = rows_map.get(int(rec_id))
            if not row:
                continue

            res: Dict[str, Any] = {"id": int(rec_id)}

            for fname, meta in scalar_fields.items():
                val = row.get(fname)
                res[fname] = self._normalize_json_value(
                    val,
                    translate=bool(meta.get("translate")),
                    lang=lang,
                )

            for fname, target_model in m2o_fields.items():
                raw_id = row.get(fname)
                if raw_id and str(raw_id).isdigit():
                    res[fname] = m2o_cache.get(target_model, {}).get(int(raw_id), [int(raw_id), str(raw_id)])
                else:
                    res[fname] = False

            for fname in o2m_fields.keys():
                res[fname] = o2m_payloads.get(fname, {}).get(int(rec_id), [])

            for fname in m2m_fields.keys():
                res[fname] = m2m_payloads.get(fname, {}).get(int(rec_id), [])

            res["display_name"] = res.get("name") or row.get("display_name") or f"{model_name}({rec_id})"
            results.append(res)

        return results

    async def write(self, vals: Dict[str, Any]) -> bool:
        if not self._records:
            return True

        await self._check_access("write")

        env = self._get_env()
        model_name = self._model_class._get_model_name()

        async with AsyncGraphSavepoint(env):
            if vals and "state" not in vals and not (env and getattr(env, "su", False)):
                for rec in self._records:
                    if hasattr(rec, "state"):
                        current_state = getattr(rec, "state", None)
                        if current_state in ["done", "cancel"]:
                            raise PermissionError("⛔ Acción 'write' bloqueada. El registro está cerrado.")

            from app.core.storage.postgres_storage import PostgresGraphStorage

            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            table_name = model_name.replace(".", "_")
            ids = [int(r.id) for r in self._records if str(r.id).isdigit()]

            vals = self._model_class._sanitize_input_vals(vals)
            frontend_version = vals.pop("write_version", None)
            db_versions = {}

            if ids:
                rows = await conn.fetch(
                    f'SELECT id, write_version FROM "{table_name}" WHERE id = ANY($1::bigint[]) FOR UPDATE',
                    ids,
                )
                db_versions = {row["id"]: row["write_version"] for row in rows}

                _is_system_write = (
                    env is None
                    or getattr(env, "su", False)
                    or str(getattr(env, "user_id", "")) == "system"
                    or str(getattr(env, "uid", "")) == "system"
                )
                if not _is_system_write:
                    for rec in self._records:
                        if str(rec.id).isdigit():
                            db_version = db_versions.get(int(rec.id))
                            base_version = (
                                frontend_version
                                if frontend_version is not None
                                else getattr(rec, "write_version", 1)
                            )

                            if db_version is not None and db_version > int(base_version):
                                raise ValueError(
                                    f"⚠️ [CONCURRENCY_CONFLICT] El registro {model_name}({rec.id}) ha sido modificado por otro usuario. Por favor, recarga la página."
                                )

            o2m_data = {}
            for key in list(vals.keys()):
                attr = getattr(self._model_class, key, None)
                if isinstance(attr, One2manyField):
                    o2m_data[key] = (attr, vals.pop(key))

            now = datetime.datetime.utcnow().isoformat()
            uid = env.uid if env else "system"

            for rec in self._records:
                local_vals = vals.copy()

                if str(rec.id).isdigit() and int(rec.id) in db_versions:
                    local_vals["write_version"] = db_versions[int(rec.id)] + 1
                else:
                    current_version = getattr(rec, "write_version", 1)
                    local_vals["write_version"] = current_version + 1

                local_vals.update({"write_date": now, "write_uid": uid})

                declared_fields = self._model_class._declared_fields()
                for key, value in local_vals.items():
                    if key == "id":
                        continue
                    if key in declared_fields:
                        setattr(rec, key, value)

            if o2m_data:
                from app.core.registry import Registry

                for rec in self._records:
                    for key, (attr, lines) in o2m_data.items():
                        if not isinstance(lines, list):
                            continue

                        ChildModel = Registry.get_model(attr.related_model)
                        if not ChildModel:
                            continue

                        inverse_name = attr.inverse_name or f"{model_name.split('.')[-1]}_id"

                        current_children = await ChildModel.search([(inverse_name, "=", rec.id)], context=rec.graph)
                        current_ids = {c.id for c in current_children if str(c.id).isdigit()}
                        processed_ids = set()

                        for line in lines:
                            if isinstance(line, dict):
                                line_id = line.get("id", "")
                                line_vals = ChildModel._sanitize_input_vals({k: v for k, v in line.items() if k != "id"})
                                line_vals[inverse_name] = rec.id

                                if line_id and str(line_id).isdigit() and int(line_id) in current_ids:
                                    child_rec = await ChildModel.search([("id", "=", int(line_id))], context=rec.graph)
                                    if child_rec:
                                        await child_rec.load_data()
                                        await child_rec.write(line_vals)
                                        processed_ids.add(int(line_id))
                                else:
                                    new_child = await ChildModel.create(line_vals, context=rec.graph)
                                    processed_ids.add(new_child.id)

                            elif isinstance(line, int) or (isinstance(line, str) and str(line).isdigit()):
                                line_int = int(line)
                                processed_ids.add(line_int)
                                child_rec = await ChildModel.search([("id", "=", line_int)], context=rec.graph)
                                if child_rec:
                                    await child_rec.load_data()
                                    await child_rec.write({inverse_name: rec.id})

                        orphans = current_ids - processed_ids
                        if orphans:
                            for orphan_id in orphans:
                                orphan_rec = await ChildModel.search([("id", "=", orphan_id)], context=rec.graph)
                                if orphan_rec:
                                    await orphan_rec.load_data()
                                    await orphan_rec.unlink()

                        setattr(rec, key, list(processed_ids))

            await self._run_computes()
            await self._get_graph().recalculate()

            for rec in self._records:
                local_vals_to_send = vals.copy()

                for f_name in dir(self._model_class):
                    f_attr = getattr(self._model_class, f_name, None)
                    if hasattr(f_attr, "get_meta"):
                        meta = f_attr.get_meta()
                        if meta.get("store", True) and meta.get("type") not in ["one2many", "many2many"]:
                            node_name = rec._get_node_name(f_name)
                            val = rec.graph.get(node_name)
                            if isinstance(val, dict) and meta.get("translate"):
                                lang = getattr(self._get_env(), "lang", "en_US") if self._get_env() else "en_US"
                                local_vals_to_send[f_name] = val.get(lang, list(val.values())[0] if val else "")
                            elif val is not None:
                                local_vals_to_send[f_name] = val

                for attr_name in dir(self._model_class):
                    attr = getattr(self._model_class, attr_name, None)
                    if hasattr(attr, "_constrain_fields"):
                        if any(f in vals for f in attr._constrain_fields):
                            if asyncio.iscoroutinefunction(attr):
                                await getattr(rec, attr_name)()
                            else:
                                getattr(rec, attr_name)()

                await EventBus.get_instance().publish(
                    f"{model_name}.updated",
                    record=rec,
                    changes=local_vals_to_send,
                )

            return True

    async def unlink(self) -> bool:
        if not self._records:
            return True

        await self._check_access("unlink")

        model_name = self._model_class._get_model_name()
        env = self._get_env()

        async with AsyncGraphSavepoint(env):
            if not (env and getattr(env, "su", False)):
                for rec in self._records:
                    if hasattr(rec, "state"):
                        current_state = getattr(rec, "state", None)
                        if current_state not in ["draft", "cancel", None]:
                            raise PermissionError("⛔ Acción 'Eliminar' bloqueada. Hay registros en uso.")

            from app.core.storage.postgres_storage import PostgresGraphStorage

            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            table_name = model_name.replace(".", "_")

            ids = [r.id for r in self._records if str(r.id).isdigit()]

            if ids:
                try:
                    await conn.execute(f'DELETE FROM "{table_name}" WHERE id = ANY($1::bigint[])', ids)
                except Exception:
                    raise ValueError(
                        "❌ No se pueden eliminar los registros. Probablemente estén vinculados a otras operaciones (Integridad Referencial)."
                    )

            graph = self._get_graph()
            keys_to_remove = [
                k for k in list(graph._values.keys())
                if isinstance(k, tuple) and k[0] == model_name and k[1] in ids
            ]

            for k in keys_to_remove:
                try:
                    del graph._values[k]
                except KeyError:
                    graph._values[k] = None

                if hasattr(graph, "_versions"):
                    try:
                        del graph._versions[k]
                    except KeyError:
                        graph._versions[k] = None

                if hasattr(graph, "_dirty_nodes"):
                    graph._dirty_nodes.discard(k)

            bus = EventBus.get_instance()
            for rec_id in ids:
                await bus.publish(f"{model_name}.unlinked", record_id=rec_id)

            return True

    def mapped(self, field_name: str) -> List[Any]:
        return [getattr(rec, field_name) for rec in self._records]

    def filtered(self, func: Callable[[Any], bool]) -> "Recordset":
        return Recordset(self._model_class, [r for r in self._records if func(r)], self._env)

    def __getattr__(self, name):
        if len(self._records) == 1:
            return getattr(self._records[0], name)
        if len(self._records) == 0:
            raise ValueError(f"❌ Recordset vacío: No se puede leer '{name}'.")
        raise ValueError(f"❌ Error Singleton: Tienes {len(self._records)} registros. Usa .read()")

    def __repr__(self):
        name = self._model_class.__name__ if self._model_class else "Unknown"
        return f"<{name}Recordset({len(self._records)} records)>"