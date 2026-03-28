# backend/app/core/ingestor.py
import importlib.util
import os
from app.core.env import Env
from app.core.orm import Model

class DataIngestor:
    """
    💿 MOTOR DE INGESTIÓN UNIVERSAL
    Ejecuta las configuraciones iniciales de cada módulo.
    """
    @classmethod
    async def bootstrap_module_data(cls, module_name: str, module_path: str):
        data_dir = os.path.join(module_path, "data")
        if not os.path.exists(data_dir):
            return

        # Entorno de sistema para escrituras iniciales
        env = Env(user_id="system", graph=Model._graph)

        for file in os.listdir(data_dir):
            if file.endswith(".py") and not file.startswith("__"):
                try:
                    spec = importlib.util.spec_from_file_location(f"data_{file}", os.path.join(data_dir, file))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Buscamos funciones de inicialización (ej. init_menus, init_rules)
                    for func_name in dir(module):
                        if func_name.startswith("init_"):
                            func = getattr(module, func_name)
                            print(f"   💿 [INGESTOR] Cargando {module_name} -> {func_name}...")
                            await func(env)
                except Exception as e:
                    print(f"   ⚠️ Error en ingesta de {file}: {e}")