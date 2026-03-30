# backend/app/core/orm/savepoint.py

from typing import Optional

from app.core.graph import Graph
from app.core.env import Context, Env


class AsyncGraphSavepoint:
    """
    💎 MEMENTO PATTERN + SQL SAVEPOINT
    Garantiza consistencia absoluta. Si hay error, revierte la RAM y
    deshace la sub-transacción de Postgres para no bloquear conexiones.
    """

    def __init__(self, env: Optional[Env]):
        self.env = env
        self.graph = (env.graph if env else None) or Context.get_graph() or Graph()
        self._snap_vals = None
        self._snap_vers = None
        self._snap_dirty = None
        self.db_transaction = None

    def _clone_storage(self, storage_obj):
        if storage_obj is None:
            return {}
        if hasattr(storage_obj, "copy"):
            return storage_obj.copy()
        if hasattr(storage_obj, "items"):
            return {k: v for k, v in storage_obj.items()}
        if hasattr(storage_obj, "cache"):
            return storage_obj.cache.copy()
        return dict(storage_obj)

    async def __aenter__(self):
        self._snap_vals = self._clone_storage(getattr(self.graph, "_values", None))
        self._snap_vers = self._clone_storage(getattr(self.graph, "_versions", None))
        dirty = getattr(self.graph, "_dirty_nodes", None)
        self._snap_dirty = dirty.copy() if hasattr(dirty, "copy") else set(dirty) if dirty else set()

        from app.core.transaction import transaction_conn

        conn = transaction_conn.get()
        if conn and hasattr(conn, "transaction"):
            self.db_transaction = conn.transaction()
            await self.db_transaction.start()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self.db_transaction:
                await self.db_transaction.rollback()

            if hasattr(self.graph, "_values"):
                v_store = self.graph._values
                if hasattr(v_store, "clear"):
                    v_store.clear()
                for k, v in self._snap_vals.items():
                    v_store[k] = v

            if hasattr(self.graph, "_versions"):
                ver_store = self.graph._versions
                if hasattr(ver_store, "clear"):
                    ver_store.clear()
                for k, v in self._snap_vers.items():
                    ver_store[k] = v

            if hasattr(self.graph, "_dirty_nodes"):
                self.graph._dirty_nodes = (
                    self._snap_dirty.copy()
                    if hasattr(self._snap_dirty, "copy")
                    else set(self._snap_dirty)
                )
        else:
            if self.db_transaction:
                await self.db_transaction.commit()