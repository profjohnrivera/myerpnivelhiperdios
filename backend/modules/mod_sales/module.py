# backend/modules/mod_sales/module.py
from app.core.module import Module
from app.core.registry import Registry
from app.core.ui_registry import UIRegistry  # 💎 Importación del cerebro visual en RAM

# 🔥 IMPORTACIÓN SEGURA: Separamos los modelos para evitar colisiones
from .models import SaleOrder, SaleOrderLine, ProductCategory
from .views import SaleOrderFormView  # 💎 Importación de la vista personalizada

class SalesModule(Module):
    """
    📦 MÓDULO DE VENTAS (Nivel HiperDios)
    Descriptor de aplicación para el Kernel de autodescubrimiento.
    """
    name = "mod_sales"
    
    # 💎 FIX: Ventas necesita obligatoriamente a Productos para funcionar
    depends = ["core_base", "core_system", "mod_products"]

    def register(self) -> None:
        """
        Fase de Registro: Presentamos el ADN y la Interfaz al Cerebro (Registry).
        """
        # 🧬 PASO 1: Registrar modelos en el Registry
        # Al registrarlos aquí, el Registry escanea sus Mixins (Trazable, Aprobable) 
        # y el Scaffolder sabe qué componentes inyectar en la UI.
        self.register_model(ProductCategory)
        self.register_model(SaleOrder)
        self.register_model(SaleOrderLine)

        # 🎨 PASO 2: Registrar Vistas Explícitas (Data-as-Code)
        # Esto le dice al Motor SDUI que use este diseño perfecto en lugar del autogenerador.
        UIRegistry.register_view(SaleOrderFormView())

        # 🚀 PASO 3: Registrar el Lanzador en el Dashboard
        # Usamos el bus de eventos unificado para inyectar el icono principal
        self.bus.publish_meta(
            module=self.name, 
            icon="ShoppingCart", 
            label="Ventas"
        )

        # 🗂️ PASO 4: Definir la navegación SDUI (En Memoria RAM)
        # Creamos el menú raíz de la aplicación.
        # ⚡ FIX: Añadimos action="sale.order"
        Registry.register_menu(
            id="menu_sales_root",
            label="Ventas",
            icon="ShoppingCart",
            sequence=10,
            is_category=True,
            action="sale.order" 
        )

        # Creamos el acceso directo a los Pedidos de Venta.
        Registry.register_menu(
            id="menu_sale_order",
            parent_id="menu_sales_root", 
            label="Pedidos",
            action="sale.order", 
            icon="FileText",
            sequence=1
        )
        
        # Creamos el acceso directo a las Categorías de Producto
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
        Fase de Arranque: El Kernel ya sincronizó la BBDD y cargó los Mixins.
        """
        print(f"🚀 [{self.name.upper()}] Motor de ventas sincronizado y listo para operar.")