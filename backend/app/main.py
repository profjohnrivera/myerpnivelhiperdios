# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.orm import Model
from app.core.storage.postgres_storage import PostgresGraphStorage

from app.api.v1.endpoints import router as api_router
from app.api.v1 import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [GRANIAN] Iniciando motor HiperDios...")

    erp_app = Application()
    await erp_app.boot(discover_modules("modules"))

    # Exponemos la app viva en el estado de FastAPI
    app.state.erp_app = erp_app

    # El kernel ya ancla el graph en Model._graph; lo dejamos explícito por claridad
    Model._graph = erp_app.kernel.graph

    # Solo arrancamos el oído distribuido que NO forma parte del boot constitucional
    await PostgresGraphStorage.start_ormcache_listener()

    print(f"🧠 [MAIN] ID de Memoria Anclado a la API: {id(Model._graph)}")

    try:
        nodes_count = len(getattr(Model._graph, "_nodes", []))
        print(f"📊 [MAIN] Nodos base en memoria: {nodes_count}")
    except Exception:
        pass

    try:
        yield
    finally:
        print("🔌 Apagado.")
        await erp_app.shutdown()


app = FastAPI(lifespan=lifespan)

# 🛡️ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "online",
        "graph_id": id(Model._graph),
    }


app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])