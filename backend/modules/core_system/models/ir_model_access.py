# backend/modules/core_system/models/ir_model_access.py
from typing import Dict, Union

from app.core.orm import Model, Field, RelationField
from app.core.ormcache import ormcache
from app.core.env import Context


class IrModelAccess(Model):
    """
    🛡️ PERMISOS DE ACCESO CRUD (ir.model.access)
    """
    _name = "ir.model.access"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre del Permiso", required=True)
    model_id = RelationField("ir.model", label="Modelo", required=True, ondelete="cascade")
    group_id = RelationField("res.groups", label="Grupo de Acceso", ondelete="cascade")

    perm_read = Field(type_="bool", default=False, label="Permiso Lectura")
    perm_write = Field(type_="bool", default=False, label="Permiso Escritura")
    perm_create = Field(type_="bool", default=False, label="Permiso Creación")
    perm_unlink = Field(type_="bool", default=False, label="Permiso Borrado")

    active = Field(type_="bool", default=True, label="Activo")

    @classmethod
    @ormcache("ir.model.access")
    async def get_permissions(cls, target_model: str, user_id: Union[int, str]) -> Dict[str, bool]:
        """
        Calcula la matriz efectiva de permisos para un usuario.
        """
        env = Context.get_env()

        # system / sudo = acceso total
        if str(user_id) == "system" or (env and getattr(env, "su", False)):
            return {
                "read": True,
                "write": True,
                "create": True,
                "unlink": True,
            }

        if not str(user_id).isdigit():
            return {
                "read": False,
                "write": False,
                "create": False,
                "unlink": False,
            }

        cache_key = f"acl::{target_model}::{user_id}"
        if env and hasattr(env.graph, "_acl_cache") and cache_key in env.graph._acl_cache:
            return env.graph._acl_cache[cache_key]

        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()
        safe_uid = int(user_id)

        query = """
            SELECT
                a.perm_read,
                a.perm_write,
                a.perm_create,
                a.perm_unlink
            FROM "ir_model_access" a
            JOIN "ir_model" m ON m.id = a.model_id
            LEFT JOIN "res_users_group_ids_rel" rug ON rug.rel_id = a.group_id
            WHERE a.active = TRUE
              AND m.model = $1
              AND (
                    a.group_id IS NULL
                    OR rug.base_id = $2
                  )
        """

        perms = {
            "read": False,
            "write": False,
            "create": False,
            "unlink": False,
        }

        try:
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    rows = await conn.fetch(query, target_model, safe_uid)
            else:
                rows = await conn_or_pool.fetch(query, target_model, safe_uid)

            for row in rows:
                perms["read"] = perms["read"] or bool(row["perm_read"])
                perms["write"] = perms["write"] or bool(row["perm_write"])
                perms["create"] = perms["create"] or bool(row["perm_create"])
                perms["unlink"] = perms["unlink"] or bool(row["perm_unlink"])
        except Exception as e:
            print(f"⚠️ Error calculando ACL para {target_model}/{user_id}: {e}")

        if env:
            if not hasattr(env.graph, "_acl_cache"):
                env.graph._acl_cache = {}
            env.graph._acl_cache[cache_key] = perms

        return perms

    @classmethod
    async def check_access(cls, target_model: str, user_id: Union[int, str], operation: str) -> bool:
        perms = await cls.get_permissions(target_model, user_id)
        return bool(perms.get(operation, False))