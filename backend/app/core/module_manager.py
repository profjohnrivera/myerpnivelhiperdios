# backend/app/core/module_manager.py
from app.core.registry import Registry

class ModuleManager:
    """
    🧬 GESTOR DE EVOLUCIÓN
    Controla qué módulos están instalados y maneja sus actualizaciones.
    """
    @classmethod
    async def sync_modules_status(cls):
        """Sincroniza el estado de los archivos físicos con la Base de Datos."""
        IrModule = Registry.get_model('ir.module')
        
        # 1. Buscamos qué módulos tenemos en la carpeta 'modules'
        all_modules = Registry._modules.keys() # Los registrados en el arranque
        
        for mod_name in all_modules:
            # Buscamos si ya existe en la DB
            existing = await IrModule.search([('name', '=', mod_name)])
            if not existing:
                print(f"   🆕 Detectado nuevo módulo: {mod_name}. Instalando...")
                await IrModule.create({
                    'name': mod_name,
                    'state': 'installed',
                    'latest_version': '1.0.0'
                })
            else:
                # Aquí iría la lógica de 'Upgrade' si la versión cambia
                pass