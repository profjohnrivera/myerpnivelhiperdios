# backend/app/core/module_manager.py
class ModuleManager:
    """
    Usa el inventario técnico real, no el launcher visual.
    """

    @classmethod
    async def sync_modules_status(cls, kernel):
        from app.core.registry import Registry

        IrModule = Registry.get_model("ir.module")

        for mod_name in kernel.modules.keys():
            existing = await IrModule.search([("name", "=", mod_name)])
            if not existing:
                print(f"   🆕 Detectado nuevo módulo: {mod_name}. Instalando...")
                await IrModule.create({
                    "name": mod_name,
                    "state": "installed",
                    "version": "1.0.0",
                    "shortdesc": mod_name.replace("_", " ").title(),
                })