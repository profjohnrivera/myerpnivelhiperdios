# backend/modules/mod_sales/module.py

from app.core.module import Module
from app.core.scaffolder import ViewScaffolder

from .models import SaleOrder, SaleOrderLine
from .views import SaleOrderFormView


class SalesModule(Module):
    """
    📦 MÓDULO DE VENTAS
    Solo contiene modelos de ventas, no catálogo.
    """
    name = "mod_sales"
    depends = ["core_base", "core_system", "mod_products"]

    def register(self) -> None:
        self.register_model(SaleOrder)
        self.register_model(SaleOrderLine)

        ViewScaffolder.register_view(SaleOrderFormView())

        self.bus.publish_meta(
            module=self.name,
            icon="ShoppingCart",
            label="Ventas",
        )

    def boot(self) -> None:
        print(f"🚀 [{self.name.upper()}] Motor de ventas sincronizado y listo para operar.")