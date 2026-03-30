# backend/app/core/ingestor.py

class DataIngestor:
    """
    ⚰️ TUMBA ARQUITECTÓNICA

    Este archivo se conserva solo para detectar imports legacy.
    A partir de A6, la única vía válida para cargar modules/*/data es:

        Kernel.load_data()
        -> Kernel._execute_init_data(module_name)

    NO vuelvas a implementar bootstrap paralelo aquí.
    """

    @classmethod
    async def bootstrap_module_data(cls, module_name: str, module_path: str):
        raise RuntimeError(
            "❌ DataIngestor está retirado por arquitectura. "
            "Usa Kernel.load_data() como única vía oficial de ingesta de data."
        )