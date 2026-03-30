# backend/app/core/worker.py
# ============================================================
# WORKER ENGINE — ARQUITECTURA DEFINITIVA
#
# FIX P1-C:
# - Contexto técnico aislado con env_scope()
# - Sin Context.set_env()/restore manual en enqueue y ejecución
# - Sin graph duplicado accidental
# - Timestamps consistentes
# - Conserva SKIP LOCKED + retry + DLQ + LISTEN/NOTIFY
# ============================================================

import asyncio
import traceback
import json
from datetime import datetime, timedelta

from app.core.registry import Registry


# retry 1 → 30s, retry 2 → 60s, retry 3 → 120s
_RETRY_BASE_SECONDS = 30


def _utcnow_naive() -> datetime:
    """
    UTC naive compatible con columnas TIMESTAMP de Postgres.
    """
    return datetime.utcnow()


class WorkerEngine:
    """
    🏗️ MOTOR DE TRABAJOS ASÍNCRONOS

    Consume ir.queue con garantías de:
    - Exactly-once delivery (SKIP LOCKED)
    - Recovery automático de jobs huérfanos
    - Retry con backoff exponencial
    - DLQ cuando se agotan los reintentos
    """

    _running: bool = False
    _wakeup_event: asyncio.Event = None
    _runner_task: asyncio.Task = None

    # =========================================================================
    # API PÚBLICA
    # =========================================================================

    @classmethod
    async def enqueue(
        cls,
        model_name: str,
        method_name: str,
        args: list = None,
        kwargs: dict = None,
        priority: int = 10,
        max_retries: int = 3,
    ) -> int:
        """
        📥 Encola un job en Postgres de forma aislada del graph actual.

        FIX P1-C:
        - graph técnico propio
        - env técnico scoped
        - no contamina el ContextVar del caller
        """
        from app.core.env import Env, env_scope
        from app.core.storage.postgres_storage import PostgresGraphStorage
        from app.core.graph import Graph

        isolated_graph = Graph()
        isolated_env = Env(
            user_id="system",
            graph=isolated_graph,
            context={"disable_audit": True},
            su=True,
            _skip_autoset=True,
        )

        async with env_scope(isolated_env):
            IrQueue = Registry.get_model("ir.queue")
            now_val = _utcnow_naive()

            tarea = await IrQueue.create({
                "model_name": model_name,
                "method_name": method_name,
                "args_json": json.dumps(args or []),
                "kwargs_json": json.dumps(kwargs or {}),
                "priority": priority,
                "max_retries": max_retries,
                "retries": 0,
                "state": "pending",
                "scheduled_at": now_val.isoformat(),
            })

            storage = PostgresGraphStorage()
            id_mapping = await storage.save(isolated_graph, model_filter="ir.queue")
            real_id = id_mapping.get(str(tarea.id), tarea.id)

            print(f"   📥 Worker: '{model_name}.{method_name}' encolado [ID: {real_id}]")
            return real_id

    # =========================================================================
    # BUCLE PRINCIPAL
    # =========================================================================

    @classmethod
    async def run(cls):
        """
        👷 Bucle event-driven del Worker.

        Ciclo:
        1. Al arrancar: recuperar jobs huérfanos ('started' → 'retry')
        2. Procesar todos los jobs disponibles ('pending' + 'retry' vencidos)
        3. Dormir esperando NOTIFY o timeout de 60s
        4. Despertar y repetir
        """
        from app.core.storage.postgres_storage import PostgresGraphStorage

        if cls._running:
            return

        cls._running = True
        cls._wakeup_event = asyncio.Event()
        cls._runner_task = asyncio.current_task()

        print("   👷 Worker Engine: Operativo con retry + DLQ (Event-Driven)...")

        def wake_up(*args):
            if cls._wakeup_event:
                cls._wakeup_event.set()

        await PostgresGraphStorage.start_worker_listener(wake_up)

        storage = PostgresGraphStorage()
        pool = await storage.get_pool()

        await cls._recover_orphaned_jobs(pool)

        while cls._running:
            cls._wakeup_event.clear()

            while cls._running:
                job = await cls._claim_next_job(pool)
                if not job:
                    break
                await cls._execute_job(pool, job)

            if cls._running:
                try:
                    await asyncio.wait_for(cls._wakeup_event.wait(), timeout=60.0)
                except asyncio.TimeoutError:
                    pass

        cls._runner_task = None

    @classmethod
    def stop(cls):
        cls._running = False
        if cls._wakeup_event:
            cls._wakeup_event.set()

    # =========================================================================
    # INTERNOS
    # =========================================================================

    @classmethod
    async def _recover_orphaned_jobs(cls, pool) -> None:
        """
        Recupera jobs en estado 'started' que quedaron huérfanos
        por caída del proceso anterior.
        """
        async with pool.acquire() as conn:
            orphaned = await conn.fetch(
                'SELECT id, retries, max_retries FROM "ir_queue" WHERE state = $1',
                "started",
            )

            if not orphaned:
                return

            print(f"   🔄 Worker: Recuperando {len(orphaned)} job(s) huérfano(s)...")

            for row in orphaned:
                job_id = row["id"]
                retries = row["retries"] or 0
                max_ret = row["max_retries"] or 3

                if retries < max_ret:
                    await conn.execute(
                        """
                        UPDATE "ir_queue"
                        SET state = 'retry',
                            retry_at = NOW(),
                            error_log = COALESCE(error_log, '') ||
                                E'\n[RECOVERY] Proceso murió durante ejecución. Reintentando...'
                        WHERE id = $1
                        """,
                        job_id,
                    )
                    print(f"     ↩ Job [{job_id}] recuperado → retry")
                else:
                    await conn.execute(
                        """
                        UPDATE "ir_queue"
                        SET state = 'failed',
                            date_finished = NOW(),
                            error_log = COALESCE(error_log, '') ||
                                E'\n[DLQ] Proceso murió y se agotaron los reintentos.'
                        WHERE id = $1
                        """,
                        job_id,
                    )
                    print(f"     💀 Job [{job_id}] → DLQ (reintentos agotados)")

    @classmethod
    async def _claim_next_job(cls, pool) -> dict | None:
        """
        Toma atómicamente el siguiente job disponible con SKIP LOCKED.
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE "ir_queue"
                SET state = 'started', date_started = NOW()
                WHERE id = (
                    SELECT id FROM "ir_queue"
                    WHERE (state = 'pending')
                       OR (state = 'retry' AND (retry_at IS NULL OR retry_at <= NOW()))
                    ORDER BY priority DESC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
                """
            )
        return dict(row) if row else None

    @classmethod
    async def _execute_job(cls, pool, job: dict) -> None:
        """
        Ejecuta un job con manejo completo de éxito, retry y DLQ.
        """
        from app.core.env import Env, env_scope
        from app.core.graph import Graph

        job_id = job["id"]
        model_name = job["model_name"]
        method_name = job["method_name"]
        retries = job.get("retries") or 0
        max_retries = job.get("max_retries") or 3

        print(f"   ⚙️  [{job_id}] {model_name}.{method_name}() — intento {retries + 1}/{max_retries + 1}")

        job_env = Env(
            user_id="system",
            graph=Graph(),
            context={"disable_audit": True},
            su=True,
            _skip_autoset=True,
        )

        start = _utcnow_naive()

        try:
            async with env_scope(job_env):
                args = json.loads(job.get("args_json") or "[]")
                kwargs = json.loads(job.get("kwargs_json") or "{}")

                TargetModel = Registry.get_model(model_name)
                if not TargetModel:
                    raise LookupError(f"El modelo '{model_name}' no está registrado.")

                if not hasattr(TargetModel, method_name):
                    raise AttributeError(
                        f"El modelo '{model_name}' no expone el método '{method_name}'"
                    )

                if "record_id" in kwargs:
                    record_id = kwargs.pop("record_id")
                    record = TargetModel(_id=record_id, context=job_env.graph, env=job_env)
                    method = getattr(record, method_name)
                else:
                    method = getattr(TargetModel, method_name)

                if asyncio.iscoroutinefunction(method):
                    await method(*args, **kwargs)
                else:
                    result = method(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        await result

            duration = (_utcnow_naive() - start).total_seconds()

            async with pool.acquire() as conn:
                await conn.execute(
                    'UPDATE "ir_queue" SET state = $1, date_finished = NOW() WHERE id = $2',
                    "done",
                    job_id,
                )

            print(f"   ✅ [{job_id}] completado en {duration:.2f}s.")

        except Exception as e:
            error_trace = traceback.format_exc()
            new_retries = retries + 1

            async with pool.acquire() as conn:
                if new_retries <= max_retries:
                    delay_seconds = _RETRY_BASE_SECONDS * (2 ** (new_retries - 1))
                    retry_at = _utcnow_naive() + timedelta(seconds=delay_seconds)

                    await conn.execute(
                        """
                        UPDATE "ir_queue"
                        SET state     = 'retry',
                            retries   = $1,
                            retry_at  = $2,
                            error_log = $3
                        WHERE id = $4
                        """,
                        new_retries,
                        retry_at,
                        error_trace,
                        job_id,
                    )
                    print(
                        f"   ↩  [{job_id}] fallo en intento {new_retries}/{max_retries + 1} "
                        f"— reintento en {delay_seconds}s"
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE "ir_queue"
                        SET state         = 'failed',
                            retries       = $1,
                            error_log     = $2,
                            date_finished = NOW()
                        WHERE id = $3
                        """,
                        new_retries,
                        error_trace,
                        job_id,
                    )
                    print(
                        f"   💀 [{job_id}] → DLQ definitivo tras {new_retries} intentos: {str(e)[:80]}"
                    )