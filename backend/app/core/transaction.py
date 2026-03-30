# backend/app/core/transaction.py
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional, Any

import asyncpg


class LazyNestedTransaction:
    def __init__(self, proxy: "LazyConnectionProxy"):
        self._proxy = proxy
        self._tx: Optional[asyncpg.transaction.Transaction] = None

    async def start(self):
        await self._proxy._ensure_connection()
        self._tx = self._proxy._conn.transaction()
        await self._tx.start()

    async def commit(self):
        if self._tx:
            await self._tx.commit()
            self._tx = None

    async def rollback(self):
        if self._tx:
            await self._tx.rollback()
            self._tx = None


class LazyConnectionProxy:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        self._conn: Optional[asyncpg.Connection] = None
        self._tx: Optional[asyncpg.transaction.Transaction] = None

    async def _ensure_connection(self):
        if self._conn is None:
            self._conn = await self._pool.acquire()
            self._tx = self._conn.transaction()
            await self._tx.start()

    def transaction(self) -> LazyNestedTransaction:
        return LazyNestedTransaction(self)

    async def execute(self, query: str, *args, **kwargs):
        await self._ensure_connection()
        return await self._conn.execute(query, *args, **kwargs)

    async def executemany(self, query: str, args, **kwargs):
        await self._ensure_connection()
        return await self._conn.executemany(query, args, **kwargs)

    async def fetch(self, query: str, *args, **kwargs):
        await self._ensure_connection()
        return await self._conn.fetch(query, *args, **kwargs)

    async def fetchrow(self, query: str, *args, **kwargs):
        await self._ensure_connection()
        return await self._conn.fetchrow(query, *args, **kwargs)

    async def fetchval(self, query: str, *args, **kwargs):
        await self._ensure_connection()
        return await self._conn.fetchval(query, *args, **kwargs)

    async def commit(self):
        if self._tx:
            await self._tx.commit()
        if self._conn:
            await self._pool.release(self._conn)
        self._conn = None
        self._tx = None

    async def rollback(self):
        if self._tx:
            await self._tx.rollback()
            print("   🔥 Transaction [ROLLBACK]: Operación abortada en Base de Datos.")
        if self._conn:
            await self._pool.release(self._conn)
        self._conn = None
        self._tx = None


transaction_conn: ContextVar[Optional[LazyConnectionProxy]] = ContextVar(
    "transaction_conn",
    default=None,
)


@asynccontextmanager
async def transaction():
    """
    FIX P1-C: token siempre se resetea en finally.
    Sin esto, una excepción dejaba el ContextVar apuntando
    a un proxy muerto para el siguiente await del mismo Task.
    """
    from app.core.storage.postgres_storage import PostgresGraphStorage

    storage = PostgresGraphStorage()
    pool = await storage.get_pool()

    existing_proxy = transaction_conn.get()

    # Transacción anidada: savepoint sobre la raíz existente
    if existing_proxy is not None:
        nested = existing_proxy.transaction()
        await nested.start()
        try:
            yield existing_proxy
            await nested.commit()
        except Exception:
            await nested.rollback()
            raise
        return

    # Transacción raíz
    proxy = LazyConnectionProxy(pool)
    token = transaction_conn.set(proxy)

    try:
        yield proxy
        await proxy.commit()
    except Exception:
        await proxy.rollback()
        raise
    finally:
        # CRÍTICO: siempre resetear sin importar qué ocurrió arriba.
        transaction_conn.reset(token)


def get_current_conn() -> Optional[Any]:
    return transaction_conn.get(None)