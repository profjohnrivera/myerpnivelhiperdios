# backend/app/core/tree.py
# ============================================================
# FIX P3-F: UPDATE de parent_path en cascada usa la conexión
#   activa de la transacción, no una conexión nueva del pool.
#
# PROBLEMA ORIGINAL:
#   El UPDATE en cascada de parent_path hacía:
#     conn_or_pool = await storage.get_connection()
#     if hasattr(conn_or_pool, 'acquire'):
#         async with conn_or_pool.acquire() as conn:
#             await conn.execute(query, ...)
#
#   Si get_connection() devolvía el Pool (porque no había
#   transacción activa en el ContextVar), abría una conexión
#   NUEVA fuera de la transacción del request actual.
#   Si el write() de la cabecera fallaba después del UPDATE
#   de parent_path, los paths quedaban actualizados pero el
#   registro padre no — inconsistencia de árbol permanente.
#
# SOLUCIÓN:
#   Usar get_current_conn() de transaction.py para obtener el
#   LazyConnectionProxy activo si existe. Solo si no hay
#   transacción activa (llamada directa fuera de request),
#   caer al pool como antes.
#   Esto garantiza que el UPDATE de cascada forme parte de
#   la misma transacción ACID que el write() de la cabecera.
# ============================================================
from app.core.orm import Model, Field, RelationField
from app.core.registry import Registry
from app.core.env import Context


class TreeModel(Model):
    """
    🌳 MOTOR DE JERARQUÍAS (Materialized Path)
    Añade capacidades de árbol infinito mediante Metaprogramación.
    """
    _abstract = True

    parent_path = Field(type_="string", label="Vector de Ruta", index=True, readonly=True)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "_abstract", False):
            parent_field = RelationField(cls._name, label="Nodo Padre", ondelete="cascade")
            parent_field.name = "parent_id"
            cls.parent_id = parent_field
            if hasattr(cls, "_fields"):
                cls._fields["parent_id"] = parent_field

    @classmethod
    async def create(cls, vals):
        record = await super().create(vals)

        if vals.get("parent_id"):
            graph = Context.get_graph()
            parent = cls(_id=vals["parent_id"], context=graph)
            p_path = getattr(parent, "parent_path", "")

            if not p_path:
                parents_db = await cls.search([("id", "=", vals["parent_id"])])
                if parents_db:
                    p_path = parents_db[0].parent_path

            parent_path = f"{p_path}{record.id}/"
        else:
            parent_path = f"{record.id}/"

        await super(TreeModel, record).write({"parent_path": parent_path})
        return record

    async def write(self, vals):
        old_path = getattr(self, "parent_path", "")

        if "parent_id" in vals:
            new_parent_id = vals["parent_id"]
            if new_parent_id:
                graph = Context.get_graph()
                TargetModel = Registry.get_model(self._name)
                new_parent = TargetModel(_id=new_parent_id, context=graph)

                p_path = getattr(new_parent, "parent_path", "")
                if not p_path:
                    parents_db = await TargetModel.search([("id", "=", new_parent_id)])
                    if parents_db:
                        p_path = parents_db[0].parent_path

                # REGLA ANTIMATRIX: No ser hijo de tu hijo
                if old_path and p_path.startswith(old_path):
                    raise ValueError(
                        f"❌ Paradoja Espacio-Temporal: No puedes mover "
                        f"'{self.display_name}' dentro de su propia descendencia."
                    )
                vals["parent_path"] = f"{p_path}{self.id}/"
            else:
                vals["parent_path"] = f"{self.id}/"

        # Actualizar el propio registro
        await super().write(vals)

        # CASCADA VECTORIZADA — O(1) en SQL
        if "parent_path" in vals and old_path and old_path != vals["parent_path"]:
            new_path = vals["parent_path"]
            table_name = self._name.replace(".", "_")

            start_pos = len(old_path) + 1
            like_pattern = f"{old_path}%"

            query = f"""
                UPDATE "{table_name}"
                SET parent_path = $1 || SUBSTRING(parent_path FROM $2)
                WHERE parent_path LIKE $3 AND id != $4
            """

            # FIX P3-F: usar la conexión activa de la transacción si existe.
            # Esto garantiza que el UPDATE de cascada sea parte de la misma
            # transacción ACID que el write() de la cabecera.
            await self._execute_cascade_update(
                query, new_path, start_pos, like_pattern, self.id
            )

            from app.core.ormcache import ORMCache
            ORMCache.clear(self._name)

    @staticmethod
    async def _execute_cascade_update(query: str, *params):
        """
        FIX P3-F: Ejecuta el UPDATE de cascada usando la conexión
        de la transacción activa cuando existe, o el pool cuando no.

        Nunca abre una conexión nueva si ya hay una transacción en curso.
        """
        from app.core.transaction import get_current_conn
        from app.core.storage.postgres_storage import PostgresGraphStorage

        # 1. Verificar si hay una transacción activa en el ContextVar
        active_conn = get_current_conn()
        if active_conn is not None:
            # Usar la conexión lazy de la transacción activa.
            # _ensure_connection() abrirá la conexión si aún no se ha usado.
            await active_conn.execute(query, *params)
            return

        # 2. Sin transacción activa: usar pool directamente (ej: scripts de migración)
        storage = PostgresGraphStorage()
        pool = await storage.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, *params)