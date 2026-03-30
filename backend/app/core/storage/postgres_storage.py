# backend/app/core/storage/postgres_storage.py

import os
import re
import json
import asyncpg
import datetime
from typing import Any, Dict, List, Optional

from app.core.graph import Graph
from app.core.registry import Registry


class PostgresGraphStorage:
    """
    🏗️ ALMACENAMIENTO MATERIALIZADO (Nivel HiperDios)

    Objetivos de esta versión:
    - Mantener compatibilidad con lo que ya funciona
    - Sacar la infraestructura a variables de entorno (con mismos defaults actuales)
    - Endurecer persistencia y schema sin introducir migraciones destructivas
    - Mantener LISTEN/NOTIFY, BIGSERIAL, M2M y búsquedas compiladas
    """
    _conn_pool: Optional[asyncpg.Pool] = None
    _ormcache_listener_conn: Optional[asyncpg.Connection] = None
    _worker_listener_conn: Optional[asyncpg.Connection] = None

    # =========================================================================
    # 0. CONFIG / INFRA
    # =========================================================================
    @classmethod
    def _db_config(cls) -> Dict[str, Any]:
        """
        Defaults conservadores: preservan tu entorno actual si no defines variables.
        """
        return {
            "user": os.getenv("ERP_DB_USER", "postgres"),
            "password": os.getenv("ERP_DB_PASSWORD", "1234"),
            "database": os.getenv("ERP_DB_NAME", "erp_automata"),
            "host": os.getenv("ERP_DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("ERP_DB_PORT", "5432")),
            "min_size": int(os.getenv("ERP_DB_POOL_MIN", "5")),
            "max_size": int(os.getenv("ERP_DB_POOL_MAX", "20")),
        }

    @staticmethod
    def _safe_ident(name: str) -> str:
        """
        Blindaje básico para nombres SQL generados por el motor.
        """
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Identificador SQL inválido: {name!r}")
        return name

    @classmethod
    async def get_pool(cls):
        if not cls._conn_pool:
            cfg = cls._db_config()
            try:
                cls._conn_pool = await asyncpg.create_pool(
                    user=cfg["user"],
                    password=cfg["password"],
                    database=cfg["database"],
                    host=cfg["host"],
                    port=cfg["port"],
                    min_size=cfg["min_size"],
                    max_size=cfg["max_size"],
                )
            except Exception as e:
                raise RuntimeError(f"❌ ERROR DE INFRAESTRUCTURA POSTGRES: {e}") from e
        return cls._conn_pool

    @classmethod
    async def start_ormcache_listener(cls):
        from app.core.ormcache import ORMCache

        try:
            if not cls._ormcache_listener_conn:
                cfg = cls._db_config()
                cls._ormcache_listener_conn = await asyncpg.connect(
                    user=cfg["user"],
                    password=cfg["password"],
                    database=cfg["database"],
                    host=cfg["host"],
                    port=cfg["port"],
                )

            async def on_notify(connection, pid, channel, payload):
                ORMCache.clear(payload)

            await cls._ormcache_listener_conn.add_listener("ormcache_channel", on_notify)
            print("   📡 [Postgres] Canal LISTEN 'ormcache_channel' abierto. Escuchando a otros Workers...")
        except Exception as e:
            print(f"   ⚠️ No se pudo iniciar el listener de ormcache: {e}")

    @classmethod
    async def start_worker_listener(cls, callback):
        """
        👂 DEMONIO DE COLA EVENT-DRIVEN
        Mantiene una conexión dedicada para despertar al Worker.
        """
        try:
            if not cls._worker_listener_conn:
                cfg = cls._db_config()
                cls._worker_listener_conn = await asyncpg.connect(
                    user=cfg["user"],
                    password=cfg["password"],
                    database=cfg["database"],
                    host=cfg["host"],
                    port=cfg["port"],
                )

            await cls._worker_listener_conn.add_listener("worker_queue_channel", callback)
            print("   📡 [Postgres] Canal LISTEN 'worker_queue_channel' abierto. Trabajadores listos.")
        except Exception as e:
            print(f"   ⚠️ No se pudo iniciar el listener del worker: {e}")

    async def get_connection(self):
        from app.core.transaction import transaction_conn

        conn = transaction_conn.get()
        if conn:
            return conn

        pool = await self.get_pool()
        return pool

    async def init_db(self):
        await self.get_pool()
        await self.sync_schema()

    # =========================================================================
    # 1. PARSING / NORMALIZACIÓN
    # =========================================================================
    def _parse_db_value(self, value: Any) -> Any:
        if isinstance(value, datetime.datetime):
            return value.isoformat()

        if isinstance(value, datetime.date):
            return value.isoformat()

        if isinstance(value, str):
            if (value.startswith("[") and value.endswith("]")) or (value.startswith("{") and value.endswith("}")):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

        return value

    def _map_type(self, internal_type: str) -> str:
        return {
            "integer": "INTEGER",
            "int": "INTEGER",
            "float": "NUMERIC",
            "decimal": "NUMERIC",
            "monetary": "NUMERIC",
            "bool": "BOOLEAN",
            "datetime": "TIMESTAMP",
            "date": "DATE",
            "string": "VARCHAR(255)",
            "password": "VARCHAR(255)",
            "selection": "VARCHAR(255)",
            "text": "TEXT",
            "jsonb": "JSONB",
            "relation": "BIGINT",
            "many2one": "BIGINT",
        }.get(internal_type, "TEXT")

    # =========================================================================
    # 2. MOTOR DE BÚSQUEDA COMPILADO (AST -> SQL)
    # =========================================================================
    async def search_domain(
        self,
        model: str,
        domain: List,
        limit: int = None,
        offset: int = None,
        order_by: str = None,
        check_access: bool = True,
    ) -> List[int]:
        conn_or_pool = await self.get_connection()
        table_name = self._safe_ident(model.replace(".", "_"))

        final_domain = list(domain) if domain else []

        if check_access:
            from app.core.env import Context

            env = Context.get_env()
            if env and not env.su and model not in ["ir.rule", "ir.model", "ir.model.fields", "res.users"]:
                try:
                    IrRuleModel = Registry.get_model("ir.rule")
                    if IrRuleModel:
                        user_security_domain = await IrRuleModel.get_domain(model, env.uid)
                        if user_security_domain:
                            if final_domain:
                                final_domain = ["&"] + user_security_domain + final_domain
                            else:
                                final_domain = user_security_domain
                except Exception as e:
                    print(f"⚠️ Error aplicando reglas de seguridad en {model}: {e}")

        from app.core.domain import DomainEngine

        joins_sql, where_sql, params = DomainEngine.compile_sql(final_domain, model)
        where_str = f"WHERE {where_sql}" if where_sql else ""

        order_str = ""
        if order_by:
            safe_parts = []
            fields_config = Registry.get_fields_for_model(model)

            for part in order_by.split(","):
                part = part.strip()
                if not part:
                    continue

                field_dir = part.split()
                field_name = field_dir[0]
                direction = field_dir[1].upper() if len(field_dir) > 1 and field_dir[1].upper() in ["ASC", "DESC"] else "ASC"

                if field_name in fields_config or field_name == "id":
                    safe_parts.append(f't0."{field_name}" {direction}')
                elif field_name.replace("_", "").isalnum():
                    safe_parts.append(f"t0.x_ext->>'{field_name}' {direction}")

            if safe_parts:
                order_str = f"ORDER BY {', '.join(safe_parts)}"

        limit_str = f"LIMIT {int(limit)}" if limit is not None else ""
        offset_str = f"OFFSET {int(offset)}" if offset is not None else ""

        query = f'SELECT t0.id FROM "{table_name}" t0 {joins_sql} {where_str} {order_str} {limit_str} {offset_str}'.strip()

        try:
            if isinstance(conn_or_pool, asyncpg.Pool):
                async with conn_or_pool.acquire() as conn:
                    rows = await conn.fetch(query, *params)
            else:
                rows = await conn_or_pool.fetch(query, *params)

            return [r["id"] for r in rows]
        except Exception as e:
            print(f"🔥 Error en Compilación SQL ({table_name}): {e}\nQuery: {query}")
            return []

    async def get_all_ids(self, model: str) -> List[int]:
        return await self.search_domain(model, [])

    # =========================================================================
    # 3. CARGA COMPLETA DEL GRAFO
    # =========================================================================
    async def load(self) -> Graph:
        """
        Retorna un Graph vacío.

        ARQUITECTURA DEFINITIVA:
        El master Graph NO pre-carga todos los registros al boot.
        Los registros se cargan on-demand via load_data() por request.

        Por qué: SELECT * de todas las tablas al boot escala O(n_records).
        Con 100k pedidos × 10 campos = 1M nodos en RAM antes del primer
        request. Con LRUCache(100000) empieza a desalojar inmediatamente.
        El boot tardaría minutos en producción.

        El mecanismo correcto es el lazy loader (load_context) que ya existe
        y que cada session graph usa via clone_for_session() + ChainMap.
        Los registros se cargan cuando se necesitan, no al arrancar.
        """
        return Graph()


    async def load_context(self, key_prefix: str) -> Dict[str, Any]:
        if not key_prefix.startswith("data:"):
            return {}

        parts = key_prefix.split(":")
        if len(parts) < 3:
            return {}

        model_name, rec_id = parts[1], parts[2]
        conn_or_pool = await self.get_connection()

        if isinstance(conn_or_pool, asyncpg.Pool):
            async with conn_or_pool.acquire() as conn:
                return await self._execute_load_context(conn, model_name, rec_id)
        else:
            return await self._execute_load_context(conn_or_pool, model_name, rec_id)

    async def _execute_load_context(self, conn, model_name, rec_id):
        table_name = self._safe_ident(model_name.replace(".", "_"))
        fields_cfg = Registry.get_fields_for_model(model_name)

        db_id = int(rec_id) if str(rec_id).isdigit() else rec_id

        try:
            row = await conn.fetchrow(f'SELECT * FROM "{table_name}" WHERE id = $1', db_id)
            if not row:
                return {}

            facts = {}

            for col_n, col_v in row.items():
                if col_n == "x_ext" and col_v:
                    dynamic_data = json.loads(col_v) if isinstance(col_v, str) else col_v
                    for f_n, f_v in dynamic_data.items():
                        facts[(model_name, db_id, f_n)] = {"value": f_v, "version": 1}
                else:
                    facts[(model_name, db_id, col_n)] = {
                        "value": self._parse_db_value(col_v),
                        "version": 1,
                    }

            for f_n, meta in fields_cfg.items():
                if meta.get("type") == "many2many":
                    rel_table = self._safe_ident(f"{table_name}_{f_n}_rel")
                    try:
                        m2m_rows = await conn.fetch(f'SELECT rel_id FROM "{rel_table}" WHERE base_id = $1', db_id)
                        facts[(model_name, db_id, f_n)] = {
                            "value": [r["rel_id"] for r in m2m_rows],
                            "version": 1,
                        }
                    except Exception:
                        pass

            return facts
        except Exception:
            return {}

    # =========================================================================
    # 4. ESQUEMA DINÁMICO (DDL) CON BIGSERIAL
    # =========================================================================
    async def sync_schema(self):
        conn_or_pool = await self.get_connection()
        models = Registry.get_all_models()

        if isinstance(conn_or_pool, asyncpg.Pool):
            async with conn_or_pool.acquire() as conn:
                await self._execute_sync_schema(conn, models)
        else:
            await self._execute_sync_schema(conn_or_pool, models)

    async def _execute_sync_schema(self, conn, models):
        for tech_name, model_cls in models.items():
            table_name = self._safe_ident(tech_name.replace(".", "_"))
            fields = Registry.get_fields_for_model(tech_name)

            await conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{table_name}" ('
                'id BIGSERIAL PRIMARY KEY, '
                "x_ext JSONB DEFAULT '{}'::jsonb)"
            )

            sql_constraints = getattr(model_cls, "_sql_constraints", [])
            for const_name, const_def, const_msg in sql_constraints:
                try:
                    safe_const_name = self._safe_ident(const_name)
                    await conn.execute(
                        f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{safe_const_name}" {const_def}'
                    )
                except Exception:
                    pass

            for field_name, meta in fields.items():
                if field_name == "id":
                    continue

                safe_field_name = self._safe_ident(field_name)
                f_type = meta.get("type", "string")

                if f_type == "many2many":
                    target_model_m2m = meta.get("target") or meta.get("relation")
                    rel_table = self._safe_ident(f"{table_name}_{field_name}_rel")
                    await conn.execute(
                        f'CREATE TABLE IF NOT EXISTS "{rel_table}" ('
                        "base_id BIGINT NOT NULL, "
                        "rel_id BIGINT NOT NULL, "
                        "PRIMARY KEY (base_id, rel_id))"
                    )
                    await conn.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{rel_table}_base_id" ON "{rel_table}"("base_id")'
                    )
                    await conn.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{rel_table}_rel_id" ON "{rel_table}"("rel_id")'
                    )
                    # FK reales para la tabla relacional
                    if target_model_m2m:
                        target_table_m2m = self._safe_ident(target_model_m2m.replace(".", "_"))
                        for col, ref_tbl in [("base_id", table_name), ("rel_id", target_table_m2m)]:
                            fk_name = self._safe_ident(f"fk_{rel_table}_{col}")[:63]
                            try:
                                await conn.execute(f"""
                                    ALTER TABLE "{rel_table}"
                                    ADD CONSTRAINT "{fk_name}"
                                    FOREIGN KEY ("{col}") REFERENCES "{ref_tbl}" (id)
                                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
                                """)
                            except Exception:
                                pass
                    continue

                pg_type = self._map_type(f_type)

                try:
                    await conn.execute(
                        f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{safe_field_name}" {pg_type}'
                    )

                    if meta.get("index"):
                        idx_name = self._safe_ident(f"idx_{table_name}_{field_name}")
                        await conn.execute(
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}"("{safe_field_name}")'
                        )
                except Exception:
                    pass

        # ── SEGUNDA PASADA: Foreign Keys reales ──────────────────────────────
        # Se hace DESPUÉS de crear todas las tablas para evitar que el FK
        # falle porque la tabla referenciada aún no existe.
        # ON DELETE CASCADE/SET NULL según el ondelete del campo en Python.
        for tech_name, model_cls in models.items():
            table_name = self._safe_ident(tech_name.replace(".", "_"))
            fields = Registry.get_fields_for_model(tech_name)

            for field_name, meta in fields.items():
                f_type = meta.get("type", "string")
                if f_type not in ("relation", "many2one"):
                    continue

                target_model = meta.get("target") or meta.get("relation")
                if not target_model:
                    continue

                target_table = self._safe_ident(target_model.replace(".", "_"))
                ondelete = meta.get("ondelete", "set null").upper().replace(" ", "_")
                # Normalizar: solo CASCADE y SET NULL son estándar aquí
                if ondelete not in ("CASCADE", "SET_NULL", "RESTRICT", "SET NULL"):
                    ondelete = "SET NULL"
                ondelete = ondelete.replace("_", " ")

                safe_field = self._safe_ident(field_name)
                fk_name = self._safe_ident(
                    f"fk_{table_name}_{field_name}_{target_table}"
                )[:63]  # PostgreSQL identifier limit

                try:
                    await conn.execute(f"""
                        ALTER TABLE "{table_name}"
                        ADD CONSTRAINT "{fk_name}"
                        FOREIGN KEY ("{safe_field}")
                        REFERENCES "{target_table}" (id)
                        ON DELETE {ondelete}
                        DEFERRABLE INITIALLY DEFERRED
                    """)
                except Exception:
                    # FK already exists or table/column not ready — skip silently
                    pass

    # =========================================================================
    # 5. PERSISTENCIA ATÓMICA Y AUTO-RESOLUTOR TOPOLÓGICO
    # =========================================================================
    async def save(self, graph: Graph, model_filter: Optional[str] = None) -> Dict[str, int]:
        all_dirty = graph.get_dirty_items()
        if not all_dirty:
            return {}

        changes = {}
        persisted_keys = []

        for key, value in all_dirty.items():
            if isinstance(key, tuple) and len(key) == 3:
                m_name, r_id, f_name = key
            elif isinstance(key, str) and key.startswith("data:"):
                parts = key.split(":")
                m_name, r_id, f_name = parts[1], parts[2], parts[3]
            else:
                continue

            if model_filter and m_name != model_filter:
                continue

            changes.setdefault(m_name, {}).setdefault(r_id, {})[f_name] = value
            persisted_keys.append(key)

        if not changes:
            return {}

        conn_or_pool = await self.get_connection()
        id_mapping = {}

        if isinstance(conn_or_pool, asyncpg.Pool):
            async with conn_or_pool.acquire() as conn:
                async with conn.transaction():
                    id_mapping = await self._execute_save(conn, changes)
        else:
            id_mapping = await self._execute_save(conn_or_pool, changes)

        graph.clear_dirty(keys=persisted_keys)
        return id_mapping

    async def _execute_save(self, conn, changes) -> Dict[str, int]:
        id_mapping = {}
        pending_queue = []

        for model_name, records in changes.items():
            for rec_id, vals in records.items():
                pending_queue.append({
                    "model_name": model_name,
                    "rec_id": rec_id,
                    "vals": vals,
                })

        max_iterations = max(len(pending_queue) * 2, 1)
        iterations = 0

        while pending_queue:
            iterations += 1
            if iterations > max_iterations:
                raise Exception("💥 ERROR: Dependencia circular infinita detectada al guardar. Revisa referencias 'new_'.")

            deferred_queue = []

            for item in pending_queue:
                model_name = item["model_name"]
                rec_id = item["rec_id"]
                vals = item["vals"]

                table_name = self._safe_ident(model_name.replace(".", "_"))
                fields_cfg = Registry.get_fields_for_model(model_name)

                is_new = not str(rec_id).isdigit()
                phys: Dict[str, Any] = {}
                dyname: Dict[str, Any] = {}
                m2m_vals: Dict[str, List[int]] = {}

                if not is_new:
                    phys["id"] = int(rec_id)

                expected_version = None
                if "write_version" in vals:
                    try:
                        expected_version = int(vals["write_version"]) - 1
                    except (ValueError, TypeError):
                        expected_version = None

                can_process_record = True

                for f_n, f_v in vals.items():
                    if f_n in fields_cfg:
                        f_type = fields_cfg[f_n].get("type")

                        if f_type in ["relation", "many2one"]:
                            if isinstance(f_v, str) and f_v.startswith("new_"):
                                if f_v in id_mapping:
                                    f_v = id_mapping[f_v]
                                else:
                                    can_process_record = False
                                    break
                            elif f_v == "" or f_v is False or f_v is None:
                                f_v = None
                            elif str(f_v).isdigit():
                                f_v = int(f_v)

                        if f_type == "many2many":
                            resolved_m2m = []
                            if isinstance(f_v, list):
                                for r_id in f_v:
                                    if isinstance(r_id, str) and r_id.startswith("new_"):
                                        if r_id in id_mapping:
                                            resolved_m2m.append(id_mapping[r_id])
                                        else:
                                            can_process_record = False
                                            break
                                    elif str(r_id).isdigit():
                                        resolved_m2m.append(int(r_id))

                            if not can_process_record:
                                break

                            m2m_vals[f_n] = resolved_m2m
                            continue

                        if f_type in ["string", "text", "selection", "password"] and f_v is not None:
                            f_v = str(f_v)
                        elif f_type in ["integer", "int"]:
                            if f_v == "" or f_v is None:
                                f_v = 0
                            elif str(f_v).isdigit():
                                f_v = int(f_v)
                        elif f_type in ["float", "decimal", "monetary"]:
                            if f_v == "" or f_v is None:
                                f_v = 0.0
                        elif f_type == "datetime" and isinstance(f_v, str):
                            try:
                                f_v = datetime.datetime.fromisoformat(f_v.replace("Z", "+00:00"))
                            except ValueError:
                                pass
                        elif f_type == "date" and isinstance(f_v, str):
                            try:
                                f_v = datetime.date.fromisoformat(f_v)
                            except ValueError:
                                pass
                        elif isinstance(f_v, (list, dict)) and f_type != "jsonb":
                            f_v = json.dumps(f_v)

                        phys[f_n] = f_v
                    else:
                        if isinstance(f_v, (datetime.date, datetime.datetime)):
                            f_v = f_v.isoformat()
                        dyname[f_n] = f_v

                if not can_process_record:
                    deferred_queue.append(item)
                    continue

                cols = list(phys.keys())
                q_vals = list(phys.values())
                placeholders = [f"${i + 1}" for i in range(len(cols))]
                safe_cols_str = ", ".join([f'"{self._safe_ident(c)}"' for c in cols])

                update_parts = []
                if not is_new:
                    update_parts = [f'"{self._safe_ident(c)}" = EXCLUDED."{self._safe_ident(c)}"' for c in cols if c != "id"]

                if dyname:
                    dyname_keep = {k: v for k, v in dyname.items() if v is not None}
                    dyname_remove = [k for k, v in dyname.items() if v is None]

                    if safe_cols_str:
                        safe_cols_str += ', "x_ext"'
                    else:
                        safe_cols_str = '"x_ext"'

                    q_vals.append(json.dumps(dyname_keep))
                    placeholders.append(f"${len(q_vals)}")

                    if not is_new:
                        if dyname_remove:
                            q_vals.append(dyname_remove)
                            array_param_idx = len(q_vals)
                            update_parts.append(
                                f'"x_ext" = (COALESCE("{table_name}"."x_ext", \'{{}}\'::jsonb) || EXCLUDED."x_ext") - ${array_param_idx}::text[]'
                            )
                        else:
                            update_parts.append(
                                f'"x_ext" = COALESCE("{table_name}"."x_ext", \'{{}}\'::jsonb) || EXCLUDED."x_ext"'
                            )

                real_id = None

                if is_new:
                    if safe_cols_str:
                        query = f'INSERT INTO "{table_name}" ({safe_cols_str}) VALUES ({", ".join(placeholders)}) RETURNING id'
                        new_id_row = await conn.fetchrow(query, *q_vals)
                    else:
                        query = f'INSERT INTO "{table_name}" DEFAULT VALUES RETURNING id'
                        new_id_row = await conn.fetchrow(query)

                    real_id = new_id_row["id"]
                    id_mapping[str(rec_id)] = real_id
                else:
                    query = f'INSERT INTO "{table_name}" ({safe_cols_str}) VALUES ({", ".join(placeholders)})'

                    if update_parts:
                        update_stmt = ", ".join(update_parts)
                        query += f' ON CONFLICT ("id") DO UPDATE SET {update_stmt}'
                    else:
                        query += ' ON CONFLICT ("id") DO NOTHING'

                    if expected_version is not None and update_parts:
                        q_vals.append(expected_version)
                        query += f' WHERE "{table_name}"."write_version" = ${len(q_vals)}'

                    result = await conn.execute(query, *q_vals)

                    if expected_version is not None and update_parts and result == "INSERT 0 0":
                        raise Exception(f"💥 ERROR DE CONCURRENCIA: El registro '{model_name}' ha sido modificado en otra sesión.")

                    real_id = int(rec_id)

                for m2m_f, m2m_list in m2m_vals.items():
                    rel_table = self._safe_ident(f"{table_name}_{m2m_f}_rel")
                    await conn.execute(f'DELETE FROM "{rel_table}" WHERE base_id = $1', real_id)

                    if m2m_list and isinstance(m2m_list, list):
                        bulk_data = [(real_id, int(r_id)) for r_id in set(m2m_list) if str(r_id).isdigit()]
                        if bulk_data:
                            await conn.executemany(
                                f'INSERT INTO "{rel_table}" (base_id, rel_id) VALUES ($1, $2)',
                                bulk_data,
                            )

            pending_queue = deferred_queue

        for model_name, records in changes.items():
            if model_name == "ir.queue":
                await conn.execute("NOTIFY worker_queue_channel, 'ping'")

            for rec_id in records.keys():
                await conn.execute(f"NOTIFY ormcache_channel, '{model_name}:{rec_id}'")

        return id_mapping