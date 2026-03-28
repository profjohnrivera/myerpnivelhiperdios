# backend/modules/core_system/module.py
from app.core.module import Module
from .models import IrModel, IrModelFields, IrRule, IrSequence, IrAuditLog, IrModule, IrModuleDependency, IrModelData, IrActionsServer,IrUiMenu, IrModelAccess, IrUiView, IrConfigParameter
from .handlers import on_sequence_created
from .events import SequenceCreated

class CoreSystemModule(Module):
    name = "core_system"

    def register(self):
        # 1. Presentamos los modelos al Registry
        self.register_model(IrModel)
        self.register_model(IrModelFields)
        self.register_model(IrRule)
        self.register_model(IrSequence)
        self.register_model(IrAuditLog)
        self.register_model(IrModule)
        self.register_model(IrModuleDependency)
        self.register_model(IrModelData)
        self.register_model(IrActionsServer)
        self.register_model(IrUiMenu)
        self.register_model(IrModelAccess)
        self.register_model(IrUiView)
        self.register_model(IrConfigParameter)


        # 2. Metadatos de la Interfaz (SDUI)
        self.bus.publish_meta(module="core_system", icon="settings", label="Ajustes")
        self.bus.publish_menu(parent="core_system", action="sequence", label="Secuencias")

    def boot(self):
        # 3. Suscripción a Eventos
        self.bus.subscribe(SequenceCreated, on_sequence_created)
        print("💎 [CORE] Estructuras de control y seguridad inicializadas.")