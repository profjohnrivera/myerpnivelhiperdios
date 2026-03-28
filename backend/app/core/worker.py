# backend/app/core/worker.py
import asyncio
import traceback
import json
from datetime import datetime
from app.core.registry import Registry

class WorkerEngine:
    """
    🏗️ EL OBRERO DEL SISTEMA (Worker Engine - Nivel HiperDios)
    Consume la tabla 'ir.queue' usando Event-Driven Puro (LISTEN/NOTIFY) y SKIP LOCKED.
    Escala a infinitos nodos físicos con 0% de CPU en estado de inactividad (Zero-Polling).
    """
    _running: bool = False
    _wakeup_event: asyncio.Event = None

    @classmethod
    async def enqueue(cls, model_name: str, method_name: str, args: list = None, kwargs: dict = None, priority: int = 10) -> int:
        """
        📥 Añade una tarea a la base de datos de Postgres y dispara NOTIFY.
        """
        from app.core.env import Context, Env
        from app.core.storage.postgres_storage import PostgresGraphStorage # 💎 IMPORTACIÓN CLAVE
        
        env = Context.get_env()
        if not env:
            from app.core.graph import Graph
            env = Env(user_id="system", graph=Graph())

        IrQueue = env['ir.queue']
        
        tarea = await IrQueue.create({
            'model_name': model_name,
            'method_name': method_name,
            'args_json': json.dumps(args or []),
            'kwargs_json': json.dumps(kwargs or {}),
            'priority': priority,
            'state': 'pending'
        })
        
        # 💎 EL FIX MAESTRO: Guardamos el grafo para que Postgres inserte la fila y grite NOTIFY
        storage = PostgresGraphStorage()
        id_mapping = await storage.save(env.graph)
        
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
        
        # 1. Conectar el Sistema Nervioso (Listener)
        def wake_up(*args):
            cls._wakeup_event.set()
            
        await PostgresGraphStorage.start_worker_listener(wake_up)
        
        storage = PostgresGraphStorage()
        pool = await storage.get_pool()

        while cls._running:
            cls._wakeup_event.clear()
            
            # 2. Bucle de Vaciado de Cola (Drain Loop)
            while cls._running:
                job = None
                async with pool.acquire() as conn:
                    # 💎 FOR UPDATE SKIP LOCKED: Toma la tarea de forma atómica y bloquea la fila
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
                    break # Cola vacía, a dormir
                
                job_id = job['id']
                m_name = job['model_name']
                meth_name = job['method_name']
                
                print(f"   ⚙️ Worker: Procesando Tarea [{job_id}] -> {m_name}.{meth_name}()")
                
                worker_env = Env(user_id="system", graph=Graph())
                Context.set_env(worker_env)
                
                start_time = datetime.now()
                try:
                    args = json.loads(job['args_json'])
                    kwargs = json.loads(job['kwargs_json'])
                    
                    TargetModel = Registry.get_model(m_name)
                    
                    if 'record_id' in kwargs:
                        record = TargetModel(_id=kwargs.pop('record_id'), context=worker_env.graph)
                        method = getattr(record, meth_name)
                    else:
                        method = getattr(TargetModel, meth_name)
                    
                    if asyncio.iscoroutinefunction(method):
                        await method(*args, **kwargs)
                    else:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, lambda: method(*args, **kwargs))
                    
                    duration = (datetime.now() - start_time).total_seconds()
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE \"ir_queue\" SET state = 'done', date_finished = NOW() WHERE id = $1", job_id)
                    print(f"   ✅ Worker: Tarea [{job_id}] finalizada en {duration:.2f}s.")
                    
                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f"   ❌ Worker Error en [{job_id}]: {str(e)}")
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE \"ir_queue\" SET state = 'failed', error_log = $1 WHERE id = $2", error_trace, job_id)
                finally:
                    Context.set_env(None)
            
            # 3. Suspensión Profunda
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