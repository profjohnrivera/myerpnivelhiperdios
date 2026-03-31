# backend/app/core/tree.py

from app.core.orm import Model, Field, RelationField
from app.core.env import Context


class TreeModel(Model):
    """
    🌳 CONTRATO CONSTITUCIONAL DE ÁRBOLES (Materialized Path)

    Invariantes globales del core:
    1. Cada nodo persistido tiene parent_path canónico.
       - raíz: "{self.id}/"
       - hijo: "{parent.parent_path}{self.id}/"

    2. Toda mutación de parent_id actualiza:
       - el nodo actual
       - toda su descendencia
       dentro de la MISMA transacción activa.

    3. Operaciones prohibidas:
       - self-parent
       - mover un nodo dentro de su propia descendencia
       - reinyectar una raíz actual bajo un nodo ya anidado

    4. Esta semántica es GLOBAL para todos los consumidores de TreeModel.
       Si en el futuro un árbol necesita una política distinta,
       debe nacer otro modelo base explícito.
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
    async def _resolve_node(cls, node_id, graph=None):
        if not node_id:
            return None

        graph = graph or Context.get_graph()
        rs = await cls.search([("id", "=", node_id)], context=graph)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        return rs[0] if rs and len(rs) > 0 else None

    @classmethod
    async def _resolve_parent_path(cls, node_id, graph=None) -> str:
        node = await cls._resolve_node(node_id, graph=graph)
        if not node:
            return ""
        return getattr(node, "parent_path", None) or ""

    @classmethod
    async def _resolve_parent_id(cls, node_id, graph=None):
        node = await cls._resolve_node(node_id, graph=graph)
        if not node:
            return None

        parent = getattr(node, "parent_id", None)
        if hasattr(parent, "id"):
            return parent.id
        return parent

    @classmethod
    async def _ancestor_ids(cls, node_id, graph=None) -> list[int]:
        graph = graph or Context.get_graph()
        ancestors: list[int] = []
        seen: set[int] = set()

        current_id = node_id
        while current_id and str(current_id).isdigit():
            parent_id = await cls._resolve_parent_id(int(current_id), graph=graph)
            if not parent_id or not str(parent_id).isdigit():
                break

            parent_id = int(parent_id)

            if parent_id in seen:
                break

            seen.add(parent_id)
            ancestors.append(parent_id)
            current_id = parent_id

        return ancestors

    @classmethod
    async def create(cls, vals):
        record = await super().create(vals)

        graph = getattr(record, "graph", None) or Context.get_graph()

        if vals.get("parent_id"):
            p_path = await cls._resolve_parent_path(vals["parent_id"], graph=graph)
            parent_path = f"{p_path}{record.id}/"
        else:
            parent_path = f"{record.id}/"

        await super(TreeModel, record).write({"parent_path": parent_path})
        return record

    async def write(self, vals):
        graph = getattr(self, "graph", None) or Context.get_graph()

        current_self = await self.__class__._resolve_node(self.id, graph=graph)
        old_path = getattr(current_self, "parent_path", None) or f"{self.id}/"
        current_parent = getattr(current_self, "parent_id", None) if current_self else None

        if hasattr(current_parent, "id"):
            current_parent = current_parent.id

        if "parent_id" in vals:
            new_parent_id = vals["parent_id"]

            if not new_parent_id:
                vals["parent_path"] = f"{self.id}/"
            else:
                if not str(new_parent_id).isdigit():
                    raise ValueError("❌ parent_id inválido para árbol.")

                new_parent_id = int(new_parent_id)

                # 1) Nunca ser hijo de sí mismo
                if new_parent_id == int(self.id):
                    raise ValueError(
                        f"❌ Paradoja Espacio-Temporal: '{self.display_name}' no puede ser su propio padre."
                    )

                new_parent = await self.__class__._resolve_node(new_parent_id, graph=graph)
                if not new_parent:
                    raise ValueError("❌ No existe el nodo padre destino.")

                new_parent_path = getattr(new_parent, "parent_path", None) or ""
                new_parent_parent = getattr(new_parent, "parent_id", None)
                if hasattr(new_parent_parent, "id"):
                    new_parent_parent = new_parent_parent.id

                # 2) Anti-ciclo clásico real por ancestros
                ancestors = await self.__class__._ancestor_ids(new_parent_id, graph=graph)
                if int(self.id) in ancestors:
                    raise ValueError(
                        f"❌ Paradoja Espacio-Temporal: No puedes mover "
                        f"'{self.display_name}' dentro de su propia descendencia."
                    )

                # 3) Regla estructural global del contrato
                current_is_root = not current_parent
                new_parent_is_nested = bool(new_parent_parent)

                if current_is_root and new_parent_is_nested:
                    raise ValueError(
                        "❌ Paradoja Espacio-Temporal: Una raíz no puede reinsertarse bajo un nodo anidado."
                    )

                vals["parent_path"] = f"{new_parent_path}{self.id}/"

        await super().write(vals)

        if "parent_path" in vals and old_path and old_path != vals["parent_path"]:
            new_path = vals["parent_path"]
            table_name = self._name.replace(".", "_")

            start_pos = len(old_path) + 1
            like_pattern = f"{old_path}%"

            query = f"""
                UPDATE "{table_name}"
                SET parent_path = $1 || SUBSTR(parent_path, $2::int)
                WHERE parent_path LIKE $3
                  AND id != $4
            """

            await self._execute_cascade_update(
                query, new_path, start_pos, like_pattern, self.id
            )

            from app.core.ormcache import ORMCache
            ORMCache.clear(self._name)

    @staticmethod
    async def _execute_cascade_update(query: str, *params):
        from app.core.transaction import get_current_conn
        from app.core.storage.postgres_storage import PostgresGraphStorage

        active_conn = get_current_conn()
        if active_conn is not None:
            await active_conn.execute(query, *params)
            return

        storage = PostgresGraphStorage()
        pool = await storage.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, *params)