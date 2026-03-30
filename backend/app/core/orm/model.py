# backend/app/core/orm/model.py

from typing import Any, Dict, List, Optional, Union
import asyncio
import datetime
import re
import uuid

from app.core.graph import Graph
from app.core.env import Context, Env
from app.core.event_bus import EventBus
from app.core.decorators import action
from app.core.ormcache import ormcache

from .fields import Field, One2manyField
from .recordset import Recordset
from .savepoint import AsyncGraphSavepoint


class Model:
    _name = None
    _inherit = None
    _abstract = False
    _rec_name = "name"

    _sql_constraints = []

    id = Field(type_="int", primary_key=True, readonly=True)
    active = Field(default=True, type_="bool")
    write_version = Field(type_="int", default=1, readonly=True)
    create_date = Field(type_="datetime", readonly=True)
    write_date = Field(type_="datetime", readonly=True)
    create_uid = Field(type_="string", readonly=True)
    write_uid = Field(type_="string", readonly=True)

    def __init__(
        self,
        _id: Union[int, str] = None,
        context: Optional[Graph] = None,
        env: Optional[Env] = None,
    ):
        if _id is not None:
            self._id_val = int(_id) if str(_id).isdigit() else str(_id)
        else:
            self._id_val = f"new_{uuid.uuid4().hex[:8]}"

        self.graph = context if context else (Context.get_graph() or Graph())
        self._env = env or Context.get_env()

    @classmethod
    @ormcache("ir.ui.view")
    async def get_view(cls, view_type: str = "form"):
        """
        Runtime oficial de vistas:
        - explícita en código si existe
        - implícita generada si no existe explícita
        - NO consulta ir.ui.view como fuente canónica de ejecución
        """
        from app.core.scaffolder import ViewScaffolder
        return await ViewScaffolder.get_runtime_view(cls._get_model_name(), view_type)

    def _get_node_name(self, field_name: str) -> tuple:
        return (self._get_model_name(), self._id_val, field_name)

    @classmethod
    def _get_model_name(cls):
        if cls._name:
            return cls._name
        if not hasattr(cls, "_auto_name"):
            cls._auto_name = re.sub(r"(?<!^)(?=[A-Z])", ".", cls.__name__).lower().replace("ir.", "ir.").replace("res.", "res.")
        return cls._auto_name

    @classmethod
    async def _check_create_access(cls):
        env = Context.get_env()
        if not env or getattr(env, "su", False) or str(getattr(env, "uid", "")) == "system":
            return

        model_name = cls._get_model_name()

        from app.core.registry import Registry

        try:
            IrModelAccess = Registry.get_model("ir.model.access")
        except Exception:
            return

        allowed = await IrModelAccess.check_access(model_name, env.uid, "create")
        if not allowed:
            raise PermissionError(
                f"🛑 [SECURITY BLOCK] ACL denegada para operación 'create' en modelo '{model_name}'."
            )

    @property
    def display_name(self) -> str:
        for field in [self._rec_name, "name", "display_name", "login"]:
            try:
                val = self.graph.get(self._get_node_name(field))
                if val:
                    if isinstance(val, dict):
                        lang = getattr(self._env, "lang", "en_US") if self._env else "en_US"
                        return str(val.get(lang, list(val.values())[0] if val else ""))
                    return str(val)
            except Exception:
                continue
        return f"{self._get_model_name()}({self._id_val})"

    @classmethod
    async def _auto_init(cls):
        if cls._abstract:
            return

        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn = await storage.get_connection()
        table_name = cls._get_model_name().replace(".", "_")

        pg_types = {
            "string": "VARCHAR(255)",
            "password": "VARCHAR(255)",
            "text": "TEXT",
            "int": "INTEGER",
            "float": "DOUBLE PRECISION",
            "decimal": "NUMERIC",
            "monetary": "NUMERIC",
            "bool": "BOOLEAN",
            "datetime": "TIMESTAMP",
            "date": "DATE",
            "relation": "BIGINT",
            "many2one": "BIGINT",
            "selection": "VARCHAR(255)",
            "jsonb": "JSONB",
        }

        try:
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                table_name,
            )

            fields_meta = {}
            for name in dir(cls):
                attr = getattr(cls, name, None)
                if hasattr(attr, "get_meta"):
                    meta = attr.get_meta()
                    if meta.get("store", True) and meta.get("type") not in ["one2many", "many2many"]:
                        fields_meta[name] = meta

            if not table_exists:
                print(f"🛠️ [DDL] Evolución Inicial: Creando tabla {table_name}...")
                columns_sql = []

                for f_name, meta in fields_meta.items():
                    pg_type = pg_types.get(meta["type"], "VARCHAR(255)")
                    if f_name == "id":
                        columns_sql.append(f'"{f_name}" BIGSERIAL PRIMARY KEY')
                    else:
                        columns_sql.append(f'"{f_name}" {pg_type}')

                if "x_ext" not in fields_meta:
                    columns_sql.append('"x_ext" JSONB')

                create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns_sql)})'
                await conn.execute(create_sql)

                await conn.execute(
                    f'CREATE INDEX "idx_{table_name}_x_ext_gin" ON "{table_name}" USING GIN ("x_ext")'
                )
            else:
                existing_cols = await conn.fetch(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
                    table_name,
                )
                db_cols = {col["column_name"] for col in existing_cols}

                for f_name, meta in fields_meta.items():
                    if f_name not in db_cols:
                        pg_type = pg_types.get(meta["type"], "VARCHAR(255)")
                        print(f"✨ [DDL] Mutación Detectada en {table_name}: Agregando columna '{f_name}' ({pg_type})")
                        await conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{f_name}" {pg_type}')

                if "x_ext" not in db_cols:
                    await conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "x_ext" JSONB')
                    await conn.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_x_ext_gin" ON "{table_name}" USING GIN ("x_ext")'
                    )

        except Exception as e:
            print(f"❌ Error crítico de DDL en la tabla {table_name}: {e}")

    @staticmethod
    def _normalize_domain(domain: List[Any]) -> List[Any]:
        if not domain:
            return []

        normalized = []
        allowed_operators = {
            "=",
            "!=",
            ">",
            "<",
            ">=",
            "<=",
            "in",
            "not in",
            "like",
            "ilike",
            "not ilike",
            "child_of",
            "parent_of",
        }

        for item in domain:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, op, value = item
                if str(op).lower() not in allowed_operators:
                    raise ValueError(
                        f"🛑 [SECURITY BLOCK] Intento de inyección detectado. Operador SQL no permitido: {op}"
                    )
                normalized.append(tuple(item))
            else:
                normalized.append(item)

        return normalized

    @classmethod
    async def create(cls, vals: Dict[str, Any], context: Optional[Graph] = None) -> "Model":
        await cls._check_create_access()

        model_name = cls._get_model_name()
        env = Context.get_env()
        now = datetime.datetime.utcnow().isoformat()
        graph = context if context else (Context.get_graph() or Graph())

        async with AsyncGraphSavepoint(env):
            vals = dict(vals or {})
            o2m_data = {}

            for key in list(vals.keys()):
                attr = getattr(cls, key, None)
                if isinstance(attr, One2manyField):
                    o2m_data[key] = (attr, vals.pop(key))

            record_id = vals.get("_id") or vals.get("id")
            record = cls(_id=record_id, context=graph, env=env)
            record._is_new = True

            if hasattr(cls, "name") and (not vals.get("name") or vals.get("name") in ["Nuevo", "New", ""]):
                vals["name"] = f"DOC-{str(uuid.uuid4().int)[:4]}"

            vals.update({
                "id": record.id,
                "create_date": now,
                "write_date": now,
                "create_uid": env.uid if env else "system",
                "write_uid": env.uid if env else "system",
                "write_version": 1,
            })

            for name in dir(cls):
                attr = getattr(cls, name, None)
                if isinstance(attr, Field) and name not in vals:
                    vals[name] = attr.default() if callable(attr.default) else attr.default

            for key, value in vals.items():
                if key != "id" and hasattr(record, key):
                    setattr(record, key, value)

            if o2m_data:
                from app.core.registry import Registry

                for key, (attr, lines) in o2m_data.items():
                    if not isinstance(lines, list):
                        continue

                    ChildModel = Registry.get_model(attr.related_model)
                    if not ChildModel:
                        continue

                    inverse_name = attr.inverse_name or f"{model_name.split('.')[-1]}_id"
                    saved_ids = []

                    for line in lines:
                        if isinstance(line, dict):
                            line_vals = {k: v for k, v in line.items() if k != "id"}
                            line_vals[inverse_name] = record.id
                            new_child = await ChildModel.create(line_vals, context=graph)
                            saved_ids.append(new_child.id)

                    setattr(record, key, saved_ids)

            rs = Recordset(cls, [record], env)
            await rs._run_computes()
            await graph.recalculate()

            for f_name in dir(cls):
                f_attr = getattr(cls, f_name, None)
                if hasattr(f_attr, "get_meta"):
                    meta = f_attr.get_meta()
                    if meta.get("store", True) and meta.get("type") not in ["one2many", "many2many"]:
                        node_name = record._get_node_name(f_name)
                        val = record.graph.get(node_name)
                        if val is not None:
                            vals[f_name] = val

            for attr_name in dir(cls):
                attr = getattr(cls, attr_name, None)
                if hasattr(attr, "_constrain_fields"):
                    if asyncio.iscoroutinefunction(attr):
                        await getattr(record, attr_name)()
                    else:
                        getattr(record, attr_name)()

            record._is_new = False
            await EventBus.get_instance().publish(f"{model_name}.created", record=record)
            return record

    async def write(self, vals: Dict[str, Any]) -> bool:
        rs = Recordset(self.__class__, [self], self._env)
        return await rs.write(vals)

    async def unlink(self) -> bool:
        rs = Recordset(self.__class__, [self], self._env)
        return await rs.unlink()

    async def read(self) -> dict:
        rs = Recordset(self.__class__, [self], self._env)
        results = await rs.read()
        return results[0] if results else {}

    @action(label="Archivar", icon="archive", variant="secondary")
    async def action_archive(self):
        if hasattr(self, "active"):
            await self.write({"active": False})

    @action(label="Restaurar", icon="archive_restore", variant="secondary")
    async def action_unarchive(self):
        if hasattr(self, "active"):
            await self.write({"active": True})

    @classmethod
    async def search(
        cls,
        domain: List = None,
        limit: int = None,
        offset: int = None,
        order_by: str = None,
        context: Optional[Graph] = None,
    ) -> Recordset:
        from app.core.storage.postgres_storage import PostgresGraphStorage
        from app.core.registry import Registry

        domain = cls._normalize_domain(domain or [])
        env = Context.get_env()
        model_name = cls._get_model_name()

        if env and not env.su and str(getattr(env, "uid", "")) != "system":
            try:
                IrModelAccess = Registry.get_model("ir.model.access")
                allowed = await IrModelAccess.check_access(model_name, env.uid, "read")
                if not allowed:
                    raise PermissionError(
                        f"🛑 [SECURITY BLOCK] ACL denegada para operación 'read' en modelo '{model_name}'."
                    )
            except PermissionError:
                raise
            except Exception:
                pass

        if hasattr(cls, "active"):
            has_active_filter = any(
                isinstance(d, tuple) and d[0] == "active"
                for d in domain
                if isinstance(d, (tuple, list))
            )
            if not has_active_filter:
                if domain:
                    domain = ["&", ("active", "=", True)] + domain
                else:
                    domain = [("active", "=", True)]

        storage = PostgresGraphStorage()
        ids = await storage.search_domain(
            model_name,
            domain,
            limit=limit,
            offset=offset,
            order_by=order_by,
            check_access=True,
        )

        graph = context or Context.get_graph()
        records = [cls(_id=rid, context=graph, env=env) for rid in ids]
        return Recordset(cls, records, env)

    @classmethod
    def browse(cls, ids: List[Union[int, str]], context: Optional[Graph] = None) -> Recordset:
        unique_ids = []
        for i in ids:
            if i not in unique_ids:
                unique_ids.append(i)

        env = Context.get_env()
        graph = context or Context.get_graph()
        return Recordset(cls, [cls(_id=i, context=graph, env=env) for i in unique_ids], env)

    def __repr__(self):
        return f"<{self.__class__.__name__}({self._id_val})>"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if "_abstract" not in cls.__dict__:
            cls._abstract = False

        try:
            from app.core.registry import Registry

            Registry.register_model(cls)

            if not getattr(cls, "_inherit", None) and not cls._abstract:
                model_name = cls._get_model_name()
                for name in dir(cls):
                    attr = getattr(cls, name, None)
                    if hasattr(attr, "get_meta"):
                        meta = attr.get_meta()
                        if meta.get("store", True):
                            Registry.register_field(model_name, name, meta)
        except Exception as e:
            print(f"⚠️ Error registrando modelo '{getattr(cls, '__name__', cls)}': {e}")