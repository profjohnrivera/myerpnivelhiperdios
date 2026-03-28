# backend/modules/core_system/module.py
from app.core.module import Module

from modules.core_system.models.ir_model import IrModel
from modules.core_system.models.ir_model_fields import IrModelFields
from modules.core_system.models.ir_sequence import IrSequence
from modules.core_system.models.ir_rule import IrRule
from modules.core_system.models.ir_audit import IrAuditLog
from modules.core_system.models.ir_module import IrModule, IrModuleDependency
from modules.core_system.models.ir_model_data import IrModelData
from modules.core_system.models.ir_actions import IrActionActWindow, IrActionServer
from modules.core_system.models.ir_ui_menu import IrUiMenu
from modules.core_system.models.ir_model_access import IrModelAccess
from modules.core_system.models.ir_ui_view import IrUiView
from modules.core_system.models.ir_config_parameter import IrConfigParameter
from modules.core_system.models.ir_queue import IrQueue


class CoreSystemModule(Module):
    name = "core_system"
    depends = ["core_base"]
    icon = "settings"
    label = "Ajustes"

    def register(self):
        self.publish_meta()

        self.register_models(
            IrModel,
            IrModelFields,
            IrSequence,
            IrRule,
            IrAuditLog,
            IrModule,
            IrModuleDependency,
            IrModelData,
            IrActionActWindow,
            IrActionServer,
            IrUiMenu,
            IrModelAccess,
            IrUiView,
            IrConfigParameter,
            IrQueue,
        )

    async def boot(self):
        from app.core.event_bus import EventBus

        bus = EventBus()

        try:
            from modules.core_system.services.sequence_service import on_sequence_created
            bus.subscribe("SequenceCreated", on_sequence_created)
        except Exception:
            pass

        print("💎 [CORE] Estructuras de control y seguridad inicializadas.")