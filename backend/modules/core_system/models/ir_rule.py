# backend/modules/core_system/models/ir_rule.py
import json
from typing import Union, Optional

from app.core.orm import Model, Field, RelationField
from app.core.env import Context
from app.core.ormcache import ormcache


class IrRule(Model):
    """
    ⚖️ REGLAS DE SEGURIDAD (Row-Level Security / ir.rule)
    """
    _name = "ir.rule"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre de la Regla", required=True)
    model_name = Field(type_="string", label="Modelo Técnico", required=True, index=True)
    domain_force = Field(type_="string", label="Dominio (JSON)", default="[]", required=True)

    # Regla global o por grupo
    group_id = RelationField("res.groups", label="Grupo", ondelete="cascade")

    perm_read = Field(type_="bool", default=True, label="Aplica para Lectura")
    perm_write = Field(type_="bool", default=True, label="Aplica para Escritura")
    perm_create = Field(type_="bool", default=True, label="Aplica para Creación")
    perm_unlink = Field(type_="bool", default=True, label="Aplica para Eliminación")

    active = Field(type_="bool", default=True, label="Activo")

    @classmethod
    async def _user_group_ids(cls, user_id: Union[int, str]) -> list[int]:
        from app.core.storage.postgres_storage import PostgresGraphStorage

        if not str(user_id).isdigit():
            return []

        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()
        safe_uid = int(user_id)

        query = """
            SELECT rel_id
            FROM "res_users_group_ids_rel"
            WHERE base_id = $1
        """

        try:
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    rows = await conn.fetch(query, safe_uid)
            else:
                rows = await conn_or_pool.fetch(query, safe_uid)
            return [int(r["rel_id"]) for r in rows]
        except Exception:
            return []

    @classmethod
    async def _is_admin_user(cls, user_id: Union[int, str]) -> bool:
        """
        El bypass NO depende del login textual.
        Solo aplica a:
        - env.su
        - system
        - usuario miembro del grupo técnico de administración
        """
        if str(user_id) == "system":
            return True

        env = Context.get_env()
        if env and getattr(env, "su", False):
            return True

        if not str(user_id).isdigit():
            return False

        cache_key = f"admin_group_member::{user_id}"
        if env and hasattr(env.graph, "_admin_cache") and cache_key in env.graph._admin_cache:
            return env.graph._admin_cache[cache_key]

        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()
        safe_uid = int(user_id)

        query = """
            SELECT 1
            FROM "res_users_group_ids_rel" rug
            JOIN "res_groups" g ON g.id = rug.rel_id
            WHERE rug.base_id = $1
              AND g.name IN ('Administración / Ajustes', 'Administracion / Ajustes', 'Settings / Administration')
            LIMIT 1
        """

        is_admin = False
        try:
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    row = await conn.fetchrow(query, safe_uid)
            else:
                row = await conn_or_pool.fetchrow(query, safe_uid)
            is_admin = bool(row)
        except Exception:
            is_admin = False

        if env:
            if not hasattr(env.graph, "_admin_cache"):
                env.graph._admin_cache = {}
            env.graph._admin_cache[cache_key] = is_admin

        return is_admin

    @classmethod
    def _perm_field_for_operation(cls, operation: str) -> str:
        mapping = {
            "read": "perm_read",
            "write": "perm_write",
            "create": "perm_create",
            "unlink": "perm_unlink",
        }
        return mapping.get(operation, "perm_read")

    @classmethod
    @ormcache("ir.rule")
    async def get_domain(
        cls,
        target_model: str,
        user_id: Union[int, str],
        operation: str = "read",
    ) -> list:
        """
        Devuelve el dominio RLS combinado para el usuario/operación.
        """
        env = Context.get_env()

        if await cls._is_admin_user(user_id):
            return []

        perm_field = cls._perm_field_for_operation(operation)
        cache_key = f"rls::{target_model}::{user_id}::{operation}"

        if env and hasattr(env.graph, "_rls_cache") and cache_key in env.graph._rls_cache:
            return env.graph._rls_cache[cache_key]

        rules = await cls.search([
            ("model_name", "=", target_model),
            (perm_field, "=", True),
            ("active", "=", True),
        ])

        # FIX DEFINITIVO: cargar los datos de las reglas desde BD.
        # ORM.search() solo retorna IDs en el Graph, sin valores de campos.
        # rule.domain_force sin load_data() → lee Field.default="[]" (vacío)
        # → json.loads("[]") = [] → dominio vacío → sin filtro → todos ven todo.
        if rules and hasattr(rules, "load_data"):
            try:
                await rules.load_data()
            except Exception:
                pass

        user_group_ids = await cls._user_group_ids(user_id)
        combined_domain = []

        for rule in rules:
            # Si la regla tiene grupo, solo aplica si el usuario pertenece
            if getattr(rule, "group_id", None):
                group_val = rule.group_id
                group_id = group_val.id if hasattr(group_val, "id") else group_val
                if not group_id or int(group_id) not in user_group_ids:
                    continue

            df = rule.domain_force
            if isinstance(df, (list, dict)):
                df_str = json.dumps(df)
            else:
                df_str = str(df or "[]")

            company_id = None
            company_ids = []

            if env:
                company_id = env.context.get("company_id")
                if company_id is None and hasattr(env, "user") and env.user:
                    try:
                        company_id = env.user.company_id.id if env.user.company_id else None
                    except Exception:
                        company_id = None

                if company_id is not None:
                    company_ids = [company_id]

            raw_domain = (
                df_str
                .replace("{user_id}", str(user_id))
                .replace("{company_id}", str(company_id) if company_id is not None else "null")
                .replace("{company_ids}", json.dumps(company_ids))
            )

            try:
                parsed_domain = json.loads(raw_domain)

                # FIX 1: saltar reglas con dominio vacío.
                # Una regla '[]' no restringe nada pero sí corrompe el
                # combined_domain al generar ["&", [...]] malformado → sin filtro.
                if not parsed_domain:
                    continue

                # FIX 2: usar OR (|) entre reglas del mismo modelo, como Odoo.
                # AND (&) significaría "registros que cumplen TODAS las reglas"
                # → resultado vacío si hay dos reglas restrictivas distintas.
                # OR (|) significa "registros que cumplen AL MENOS UNA regla"
                # → correcto para "ves los tuyos O los de tu equipo".
                if combined_domain:
                    combined_domain = ["|"] + combined_domain + parsed_domain
                else:
                    combined_domain = parsed_domain
            except Exception as e:
                print(f"🔥 Error parseando regla de seguridad '{rule.name}': {e}")

        if env:
            if not hasattr(env.graph, "_rls_cache"):
                env.graph._rls_cache = {}
            env.graph._rls_cache[cache_key] = combined_domain

        return combined_domain