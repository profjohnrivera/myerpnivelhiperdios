# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.orm import Model
from app.core.registry import Registry  # 💎 Importación necesaria para leer los modelos
from app.core.storage.postgres_storage import PostgresGraphStorage # 💎 Para arrancar el Listener

# 💡 Importación explícita del router
from app.api.v1.endpoints import router as api_router
from app.api.v1 import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [GRANIAN] Iniciando motor HiperDios...")
    erp_app = Application()
    
    # 1. EJECUTAMOS EL BOOT PRIMERO (Carga clases Python en la RAM)
    await erp_app.boot(discover_modules("modules"))
    
    # 2. EL FIX MAESTRO: ANCLAJE POST-ARRANQUE
    Model._graph = erp_app.kernel.graph
    
    # 3. 🧬 MOTOR DE MIGRACIONES (DDL EVOLUTION)
    # Ejecutamos la sincronización de tablas antes de aceptar conexiones web
    print("✨ [DDL] Verificando e inyectando estructura en PostgreSQL...")
    models_dict = Registry.get_all_models()
    for model_name, model_cls in models_dict.items():
        if hasattr(model_cls, '_auto_init'):
            await model_cls._auto_init()
    print("✅ [DDL] Evolución de tablas completada exitosamente.")
    
    # 4. 💎 ENCENDER OÍDO DISTRIBUIDO (ormcache)
    await PostgresGraphStorage.start_ormcache_listener()
    
    # 🕵️ Logs de confirmación vitales
    print(f"🧠 [MAIN] ID de Memoria Anclado a la API: {id(Model._graph)}")
    
    # 💎 FIX DEL ERROR: Usamos el atributo o método correcto según la clase Graph
    try:
        # Intentamos acceder a _nodes o a la forma segura
        nodes_count = len(getattr(Model._graph, '_nodes', [])) 
        print(f"📊 [MAIN] Nodos base en memoria: {nodes_count}")
    except Exception:
        pass # Si falla, ignoramos silenciosamente para no interrumpir el arranque
    
    yield
    print("🔌 Apagado.")

app = FastAPI(lifespan=lifespan)

# 🛡️ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔌 RUTA DE PRUEBA
@app.get("/health")
def health(): 
    return {
        "status": "online",
        "graph_id": id(Model._graph)
    }

# 🔌 CONEXIÓN DEL ROUTER
app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])