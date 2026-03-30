# backend/app/main.py
import asyncio
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.orm import Model
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.env import Env, Context

from app.api.v1.endpoints import router as api_router
from app.api.v1 import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [GRANIAN] Iniciando motor HiperDios...")
    erp_app = Application()
    await erp_app.boot(discover_modules("modules"))
    app.state.erp_app = erp_app
    Model._graph = erp_app.kernel.graph
    await PostgresGraphStorage.start_ormcache_listener()
    print(f"🧠 [MAIN] Graph Maestro ID: {id(Model._graph)}")
    try:
        nodes_count = len(getattr(Model._graph, "_values", {}))
        print(f"📊 [MAIN] Nodos en memoria: {nodes_count}")
    except Exception:
        pass
    try:
        yield
    finally:
        print("🔌 Apagado.")
        await erp_app.shutdown()


app = FastAPI(
    title="HiperDios ERP",
    version="1.0.0",
    description="ERP Graph-native, reactivo, vigencia centenaria.",
    lifespan=lifespan,
)


# ==============================================================================
# 🛡️ SESSION GRAPH MIDDLEWARE — aislamiento O(1) por request
# ==============================================================================
@app.middleware("http")
async def session_graph_middleware(request: Request, call_next: Callable) -> Response:
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    master_graph = getattr(Model, "_graph", None)
    if master_graph is None:
        return await call_next(request)
    session_graph = master_graph.clone_for_session()
    request.state.session_graph = session_graph
    env = Env(user_id="public", graph=session_graph)
    token = Context.set_env(env)
    try:
        return await call_next(request)
    finally:
        Context.restore(token)


# ==============================================================================
# 🛡️ CORS
# ==============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 🏥 HEALTH CHECKS
# GET /health        liveness  — proceso vivo, < 1ms
# GET /health/live   alias K8s
# GET /health/ready  readiness — Postgres + pool OK, 503 si falla
# ==============================================================================
async def _ping_database(timeout: float = 2.0) -> dict:
    import time
    storage = PostgresGraphStorage()
    t0 = time.perf_counter()
    try:
        pool = await asyncio.wait_for(storage.get_pool(), timeout=timeout)
        async with asyncio.timeout(timeout):
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        return {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except asyncio.TimeoutError:
        return {"status": "timeout", "error": f"Postgres no respondió en {timeout}s"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}


@app.get("/health", tags=["Health"])
async def health_live():
    """Liveness: proceso vivo. K8s usa esto para reiniciar el pod."""
    return {
        "status": "ok",
        "service": "hiperdios-erp",
        "graph_id": id(Model._graph) if getattr(Model, "_graph", None) else None,
    }


@app.get("/health/live", tags=["Health"])
async def health_live_alias():
    return await health_live()


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    """
    Readiness: BD y pool OK. HTTP 200 = listo, 503 = no enviar tráfico.
    Configurar en K8s: readinessProbe.httpGet.path = /health/ready
    """
    checks: dict = {}

    # 1. Graph inicializado
    checks["graph"] = {"status": "ok" if getattr(Model, "_graph", None) else "not_initialized"}

    # 2. Postgres responde en < 2s
    checks["database"] = await _ping_database(timeout=2.0)

    # 3. Pool con capacidad
    try:
        pool = await PostgresGraphStorage().get_pool()
        size = pool.get_size()
        idle = pool.get_idle_size()
        checks["pool"] = {"status": "ok", "size": size, "idle": idle, "used": size - idle}
    except Exception as e:
        checks["pool"] = {"status": "error", "error": str(e)[:80]}

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


# ==============================================================================
# 🔌 ROUTERS
# ==============================================================================
app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])