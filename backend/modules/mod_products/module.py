# backend/modules/mod_products/module.py
from app.core.module import Module
from app.core.registry import Registry
from .models import ProductProduct

class ProductsModule(Module):
    name = "mod_products"
    depends = ["core_base"] # Solo depende de la base

    def register(self) -> None:
        Registry.register_model(ProductProduct)
        
        # Opcional: Un menú propio para gestionar los productos fuera de ventas
        Registry.register_menu(
            id="menu_products_root",
            label="Productos",
            icon="Package",
            sequence=15
        )
        Registry.register_menu(
            id="menu_product_product",
            parent="menu_products_root",
            label="Catálogo",
            action="product.product",
            sequence=1
        )

    def boot(self) -> None:
        print(f"📦 [{self.name.upper()}] Catálogo de Productos en línea.")