# backend/modules/core_base/module.py
from app.core.module import Module
from .models import ResPartner, ResCompany, ResUsers, ResGroups

class CoreBaseModule(Module):
    name = "core_base"

    def register(self):
        # Presentamos explícitamente los modelos al Registry
        self.register_model(ResPartner)
        self.register_model(ResCompany)
        self.register_model(ResUsers)
        self.register_model(ResGroups)

        # Meta de UI
        self.bus.publish_meta(module="core_base", icon="users", label="Contactos")

    def boot(self):
        print(f"🚀 [CORE BASE] Identidades y Empresas en línea.")