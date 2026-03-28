# backend/modules/core_base/module.py
from app.core.module import Module
from .models import ResPartner, ResCompany, ResUsers, ResGroups


class CoreBaseModule(Module):
    name = "core_base"
    depends = []

    def register(self):
        """
        Registra explícitamente los modelos base del sistema.
        """
        self.register_model(ResPartner)
        self.register_model(ResCompany)
        self.register_model(ResUsers)
        self.register_model(ResGroups)

        # Meta de UI / launcher
        self.bus.publish_meta(
            module="core_base",
            icon="users",
            label="Contactos"
        )

    def boot(self):
        print("🚀 [CORE BASE] Identidades y Empresas en línea.")