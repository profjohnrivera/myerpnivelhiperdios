# backend/app/core/worker.py
import asyncio
import traceback
import json
from datetime import datetime
from app.core.registry import Registry


class WorkerEngine:
    """
    🏗️ EL OBRERO DEL SISTEMA (Worker Engine - Nivel HiperDios)
    Consume la tabla 'ir.queue' usando Event-Driven puro.
    """
    _running: bool = False
    _wakeup_event: asyncio.Event = None

    @classmethod
    async def enqueue(
        cls,
        model_name: str,
        method_name: str,
        args: list = None,
        kwargs: dict = None,
        priority: int = 10,
    ) -> int:
        """
        📥 Añade una tarea a la cola de Postgres SIN tocar el graph vivo
        de la operación actual.
        """
        from app.core.env import Env, Context
        from app.core.storage.postgres_storage import PostgresGraphStorage
        from app.core.graph import Graph

        # 💎 FIX CRÍTICO:
        # La cola SIEMPRE se crea en un graph aislado para no contaminar
        # el graph de negocio que todavía puede tener new_* sin resolver.
        isolated_graph = Graph()
        isolated_env = Env(
            user_id="system",
            graph=isolated_graph,
            context={"disable_audit": True},
            su=True,
        )

        IrQueue = isolated_env["ir.queue"]

        tarea = await IrQueue.create({
            "model_name": model_name,
            "method_name": method_name,
            "args_json": json.dumps(args or []),
            "kwargs_json": json.dumps(kwargs or {}),
            "priority": priority,
            "state": "pending",
        })

        storage = PostgresGraphStorage()

        # Guardamos SOLO la cola, no el graph completo de negocio
        id_mapping = await storage.save(isolated_env.graph, model_filter="ir.queue")
        real_id = id_mapping.get(str(tarea.id), tarea.id)

        print(f"   📥 Worker: Tarea '{model_name}.{method_name}' encolada en Postgres [ID: {real_id}]")
        return real_id

    @classmethod
    async def run(cls):
        """
        👷 Bucle Reactivo del Obrero. (Event-Driven)
        """
        from app.core.storage.postgres_storage import PostgresGraphStorage
        from app.core.env import Env, Context
        from app.core.graph import Graph

        cls._running = True
        cls._wakeup_event = asyncio.Event()

        print("   👷 Worker Engine: Operativo y en suspensión profunda (Event-Driven)...")

        def wake_up(*args):
            if cls._wakeup_event:
                cls._wakeup_event.set()

        await PostgresGraphStorage.start_worker_listener(wake_up)

        storage = PostgresGraphStorage()
        pool = await storage.get_pool()

        while cls._running:
            cls._wakeup_event.clear()

            while cls._running:
                job = None
                async with pool.acquire() as conn:
                    query = """
                        UPDATE "ir_queue"
                        SET state = 'started', date_started = NOW()
                        WHERE id = (
                            SELECT id FROM "ir_queue"
                            WHERE state = 'pending'
                            ORDER BY priority DESC, id ASC
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                        ) RETURNING *;
                    """
                    job = await conn.fetchrow(query)

                if not job:
                    break

                job_id = job["id"]
                m_name = job["model_name"]
                meth_name = job["method_name"]

                print(f"   ⚙️ Worker: Procesando Tarea [{job_id}] -> {m_name}.{meth_name}()")

                worker_env = Env(
                    user_id="system",
                    graph=Graph(),
                    context={"disable_audit": True},
                    su=True,
                )
                Context.set_env(worker_env)

                start_time = datetime.now()
                try:
                    args = json.loads(job["args_json"] or "[]")
                    kwargs = json.loads(job["kwargs_json"] or "{}")

                    TargetModel = Registry.get_model(m_name)

                    if not hasattr(TargetModel, meth_name):
                        raise AttributeError(f"El modelo '{m_name}' no expone el método '{meth_name}'")

                    if "record_id" in kwargs:
                        record_id = kwargs.pop("record_id")
                        record = TargetModel(_id=record_id, context=worker_env.graph)
                        method = getattr(record, meth_name)
                    else:
                        method = getattr(TargetModel, meth_name)

                    if asyncio.iscoroutinefunction(method):
                        await method(*args, **kwargs)
                    else:
                        result = method(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            await result

                    duration = (datetime.now() - start_time).total_seconds()
                    async with pool.acquire() as conn:
                        await conn.execute(
                            'UPDATE "ir_queue" SET state = $1, date_finished = NOW() WHERE id = $2',
                            "done",
                            job_id,
                        )
                    print(f"   ✅ Worker: Tarea [{job_id}] finalizada en {duration:.2f}s.")

                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f"   ❌ Worker Error en [{job_id}]: {str(e)}")
                    async with pool.acquire() as conn:
                        await conn.execute(
                            'UPDATE "ir_queue" SET state = $1, error_log = $2, date_finished = NOW() WHERE id = $3',
                            "failed",
                            error_trace,
                            job_id,
                        )
                finally:
                    Context.clear()

            if cls._running:
                try:
                    await asyncio.wait_for(cls._wakeup_event.wait(), timeout=60.0)
                except asyncio.TimeoutError:
                    pass

    @classmethod
    def stop(cls):
        cls._running = False
        if cls._wakeup_event:
            cls._wakeup_event.set()