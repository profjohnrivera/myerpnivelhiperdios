# backend/modules/mod_products/module.py

from app.core.module import Module
from .models import ProductProduct, ProductCategory


class ProductsModule(Module):
    """
    📦 MÓDULO DE PRODUCTOS

    Regla:
    - modelos y launcher aquí
    - menús en data/menus.py
    """
    name = "mod_products"
    depends = ["core_base", "core_system"]

    def register(self) -> None:
        self.register_model(ProductProduct)
        self.register_model(ProductCategory)

        self.bus.publish_meta(
            module=self.name,
            icon="Package",
            label="Productos",
        )

    def boot(self) -> None:
        print(f"📦 [{self.name.upper()}] Catálogo de productos en línea.")