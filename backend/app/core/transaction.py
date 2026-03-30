# backend/app/core/transaction.py

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional, Any

import asyncpg


class LazyNestedTransaction:
    """
    Savepoint anidado sobre la conexión raíz ya abierta.
    """

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
    """
    Proxy raíz transaccional.
    Adquiere la conexión del pool solo al primer uso y la mantiene viva
    hasta commit/rollback de la transacción actual.
    """

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


class PooledConnectionProxy:
    """
    Proxy NO transaccional con contrato idéntico al de una conexión:
    fetch/fetchrow/fetchval/execute/executemany.

    Cada operación adquiere y libera una conexión del pool automáticamente.
    Así get_connection() SIEMPRE devuelve un objeto conexión-like.
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, query: str, *args, **kwargs):
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args, **kwargs)

    async def executemany(self, query: str, args, **kwargs):
        async with self._pool.acquire() as conn:
            return await conn.executemany(query, args, **kwargs)

    async def fetch(self, query: str, *args, **kwargs):
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args, **kwargs)

    async def fetchrow(self, query: str, *args, **kwargs):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args, **kwargs)

    async def fetchval(self, query: str, *args, **kwargs):
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args, **kwargs)


transaction_conn: ContextVar[Optional[LazyConnectionProxy]] = ContextVar(
    "transaction_conn",
    default=None,
)


@asynccontextmanager
async def transaction():
    """
    Transacción raíz o anidada.

    Garantías:
    - savepoint real en anidadas
    - token del ContextVar siempre reseteado en finally
    """
    from app.core.storage.postgres_storage import PostgresGraphStorage

    storage = PostgresGraphStorage()
    pool = await storage.get_pool()

    existing_proxy = transaction_conn.get()

    # ── Transacción anidada: savepoint sobre la raíz existente ───────────────
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

    # ── Transacción raíz ──────────────────────────────────────────────────────
    proxy = LazyConnectionProxy(pool)
    token = transaction_conn.set(proxy)

    try:
        yield proxy
        await proxy.commit()
    except Exception:
        await proxy.rollback()
        raise
    finally:
        transaction_conn.reset(token)


def get_current_conn() -> Optional[Any]:
    return transaction_conn.get(None)