# backend/modules/mod_test/module.py
from app.core.module import Module

# 🔌 1. EL CABLE: Importamos el motor SDUI directamente
from app.core.scaffolder import ViewScaffolder

from .models import TestRecord, TestLine, TestTag
from .views import TestRecordFormView

class TestModule(Module):
    name = "mod_test"
    depends = ["core_base", "core_system"] 

    def register(self) -> None:
        # Registramos las tablas en la Base de Datos
        self.register_model(TestRecord)
        self.register_model(TestLine)
        self.register_model(TestTag)
        
        # 💎 2. LA CONEXIÓN: Le entregamos el plano en la mano al Scaffolder
        ViewScaffolder.register_view(TestRecordFormView())

        self.bus.publish_meta(
            module=self.name, 
            icon="Beaker",     
            label="Laboratorio"
        )

    def boot(self) -> None:
        print(f"🚀 [{self.name.upper()}] Laboratorio relacional en línea.")