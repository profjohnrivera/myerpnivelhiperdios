# backend/app/core/transaction.py
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional, Any
import asyncpg
import logging

class LazyConnectionProxy:
    """
    🕵️ INVISIBLE DB PROXY (Conexión Perezosa)
    Se hace pasar por una conexión de asyncpg (Duck Typing). 
    NO se conecta a la base de datos hasta el milisegundo exacto en que se 
    necesita enviar un query. Ahorra un 99% de tiempo de retención de conexiones.
    """
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        self._conn: Optional[asyncpg.Connection] = None
        self._tx: Optional[asyncpg.transaction.Transaction] = None

    async def _ensure_connection(self):
        """Abre la conexión solo si alguien realmente intenta hablar con la BD."""
        if self._conn is None:
            self._conn = await self._pool.acquire()
            self._tx = self._conn.transaction()
            await self._tx.start()
            # print("   ⚖️  Transaction: [LAZY] Conexión abierta justo a tiempo (Just-In-Time).")

    # =========================================================================
    # 🎭 INTERCEPTADORES SQL (Duck Typing para engañar al Storage)
    # =========================================================================
    
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

    # =========================================================================
    # 🛡️ GESTIÓN DEL CICLO DE VIDA (ACID)
    # =========================================================================

    async def commit(self):
        """Consolida la transacción y libera la conexión física instantáneamente."""
        if self._tx:
            await self._tx.commit()
            # print("   ✅ Transaction: Cambios consolidados con éxito.")
        if self._conn:
            await self._pool.release(self._conn)
            self._conn = None
            self._tx = None

    async def rollback(self):
        """Deshace la transacción en caso de error y libera la memoria."""
        if self._tx:
            await self._tx.rollback()
            print("   🔥 Transaction [ROLLBACK]: Operación abortada en Base de Datos.")
        if self._conn:
            await self._pool.release(self._conn)
            self._conn = None
            self._tx = None


# 🧬 La variable de contexto ahora almacena el Proxy Inteligente, no la conexión cruda.
transaction_conn: ContextVar[Optional[LazyConnectionProxy]] = ContextVar("transaction_conn", default=None)

@asynccontextmanager
async def transaction():
    """
    💎 MANEJADOR DE TRANSACCIONES (Lazy Unit of Work)
    Soporta anidamiento e inicia la conexión física de manera diferida.
    """
    from app.core.storage.postgres_storage import PostgresGraphStorage
    storage = PostgresGraphStorage()
    
    pool = await storage.get_pool()
    
    # 1. Check de Anidamiento
    existing_proxy = transaction_conn.get()
    if existing_proxy is not None:
        yield existing_proxy
        return

    # 2. Transacción Raíz (Creamos el Proxy Perezoso)
    proxy = LazyConnectionProxy(pool)
    token = transaction_conn.set(proxy)
    
    try:
        yield proxy
        # Si todo sale bien, el Proxy hará el commit (si es que llegó a conectarse)
        await proxy.commit()
    except Exception as e:
        # Si ocurre un error, revertimos (si es que se tocó la BD)
        await proxy.rollback()
        raise e
    finally:
        transaction_conn.reset(token)

def get_current_conn() -> Optional[Any]:
    """Helper para que el Storage obtenga el Proxy Activo si existe."""
    return transaction_conn.get()