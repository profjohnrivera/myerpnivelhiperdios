# backend/modules/mod_products/models.py
from app.core.orm import Model, Field, SelectionField

class ProductProduct(Model):
    """
    📦 CATÁLOGO MAESTRO DE PRODUCTOS
    Equivalente a product.product / product.template en Odoo
    """
    _name = "product.product"
    _rec_name = "name"

    name = Field(type_='string', label='Nombre del Producto', required=True)
    
    # Tipo de producto: Almacenable (físico), Consumible o Servicio
    type = SelectionField(
        options=[('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')],
        default='product',
        label='Tipo de Producto'
    )
    
    # Precio de venta al público
    list_price = Field(type_='float', default=1.0, label='Precio de Venta')
    
    # Costo interno
    standard_price = Field(type_='float', default=0.0, label='Costo')
    
    # Referencia interna (SKU)
    default_code = Field(type_='string', label='Referencia Interna (SKU)')
    
    # Código de barras
    barcode = Field(type_='string', label='Código de Barras')