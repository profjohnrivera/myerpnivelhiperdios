# backend/modules/mod_sales/module.py
from app.core.module import Module
from app.core.registry import Registry
from app.core.ui_registry import UIRegistry

from .models import SaleOrder, SaleOrderLine, ProductCategory
from .views import SaleOrderFormView


class SalesModule(Module):
    """
    📦 MÓDULO DE VENTAS (Nivel HiperDios)
    Descriptor de aplicación para el Kernel de autodescubrimiento.
    """
    name = "mod_sales"
    depends = ["core_base", "core_system", "mod_products"]

    def __init__(self, kernel):
        super().__init__(kernel)
        self._view_registered = False

    def register(self) -> None:
        """
        Fase 1: registrar ADN técnico y navegación.
        Aquí NO compilamos vistas todavía.
        """
        # 1. Registrar modelos
        self.register_model(ProductCategory)
        self.register_model(SaleOrder)
        self.register_model(SaleOrderLine)

        # 2. Registrar launcher/app
        self.bus.publish_meta(
            module=self.name,
            icon="ShoppingCart",
            label="Ventas"
        )

        # 3. Registrar menús
        Registry.register_menu(
            id="menu_sales_root",
            label="Ventas",
            icon="ShoppingCart",
            sequence=10,
            is_category=True,
            action="sale.order"
        )

        Registry.register_menu(
            id="menu_sale_order",
            parent_id="menu_sales_root",
            label="Pedidos",
            action="sale.order",
            icon="FileText",
            sequence=1
        )

        Registry.register_menu(
            id="menu_product_category",
            parent_id="menu_sales_root",
            label="Cat. de Productos",
            action="product.category",
            icon="Tags",
            sequence=2
        )

    def boot(self) -> None:
        """
        Fase 2: el kernel ya terminó prepare()/load_data() y el Registry
        ya debe conocer los modelos. Recién aquí registramos la vista explícita.
        """
        if not self._view_registered:
            UIRegistry.register_view(SaleOrderFormView())
            self._view_registered = True

        print(f"🚀 [{self.name.upper()}] Motor de ventas sincronizado y listo para operar.")