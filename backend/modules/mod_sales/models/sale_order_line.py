# backend/modules/mod_sales/models/sale_order_line.py
from app.core.orm import Field, SelectionField, RelationField, compute, onchange
from app.core.abstract_models import AbstractDocumentLine
from app.core.registry import Registry

class SaleOrderLine(AbstractDocumentLine):
    """
    ===========================================================================
    2. LÍNEAS DE PEDIDO (Con Motor Onchange Inyectado)
    ===========================================================================
    """
    _name = "sale.order.line"
    _rec_name = "name" 
    _description = 'Línea de Pedido de Venta'

    order_id = RelationField("sale.order", label="Pedido", required=True, ondelete="cascade")
    product_id = RelationField("product.product", label="Producto")
    
    product_uom_qty = Field(type_='float', default=1.0, label='Cantidad')
    price_unit = Field(type_='float', default=0.0, label='Precio Unitario')
    price_subtotal = Field(type_='float', default=0.0, readonly=True, label='Subtotal')
    display_type = Field(type_='string', default=None)
    
    qty_delivered = Field(type_='float', default=0.0, label='Cantidad Entregada')
    qty_invoiced = Field(type_='float', default=0.0, label='Cantidad Facturada')
    qty_to_invoice = Field(type_='float', default=0.0, label='A Facturar', readonly=True)
    
    invoice_status = SelectionField(
        options=[
            ('upselling', 'Oportunidad de Upselling'), 
            ('invoiced', 'Totalmente Facturado'), 
            ('to invoice', 'A Facturar'), 
            ('no', 'Nada que Facturar')
        ],
        default='no', label="Estado de Facturación"
    )

    # 🧠 MOTOR ONCHANGE: Inteligencia Delegada al Servidor
    @onchange('product_id')
    async def _onchange_product_id(self):
        if not getattr(self, 'product_id', None):
            return
            
        try:
            # ⚡ FIX ARQUITECTÓNICO: Latencia ultrabaja consultando directo a Postgres
            # Evita fallos de "Not Found" en el Grafo virtual de sesión
            from app.core.storage.postgres_storage import PostgresGraphStorage
            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            
            clean_product_id = int(self.product_id)
            
            # Ejecutamos el query explícito (Asumiendo que list_price está en product.product)
            row = await conn.fetchrow('SELECT name, list_price FROM "product_product" WHERE id = $1', clean_product_id)
            
            if row:
                # Inyección a los campos de la línea
                self.name = row['name'] or 'Producto sin nombre'
                self.price_unit = float(row['list_price'] or 0.0)
                
                # El cálculo temporal rápido (el @compute general hará el reajuste después)
                qty = float(self.product_uom_qty or 1.0)
                self.price_subtotal = qty * self.price_unit
                
        except Exception as e:
            print(f"⚠️ [ONCHANGE ERROR] Fallo al cargar precio del producto: {e}")

    @onchange('product_uom_qty', 'price_unit')
    def _onchange_quantity_or_price(self):
        if not getattr(self, 'display_type', None):
            qty = float(self.product_uom_qty or 0.0)
            price = float(self.price_unit or 0.0)
            self.price_subtotal = qty * price

    @compute(depends=['product_uom_qty', 'price_unit', 'display_type'])
    def _compute_subtotal(self):
        if getattr(self, 'display_type', None):
            self.price_subtotal = 0.0
        else:
            q = float(getattr(self, 'product_uom_qty', 1.0) or 1.0)
            p = float(getattr(self, 'price_unit', 0.0) or 0.0)
            self.price_subtotal = q * p

    @compute(depends=['product_uom_qty', 'qty_invoiced', 'display_type'])
    def _compute_qty_to_invoice(self):
        if getattr(self, 'display_type', None):
            self.qty_to_invoice = 0.0
        else:
            q = float(getattr(self, 'product_uom_qty', 1.0) or 1.0)
            self.qty_to_invoice = max(0.0, q - float(getattr(self, 'qty_invoiced', 0.0) or 0.0))

    @compute(depends=['product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced', 'display_type'])
    def _compute_invoice_status(self):
        q = float(getattr(self, 'product_uom_qty', 1.0) or 1.0)
        
        if getattr(self, 'display_type', None):
            self.invoice_status = 'no'
        elif float(getattr(self, 'qty_to_invoice', 0.0) or 0.0) > 0:
            self.invoice_status = 'to invoice'
        elif float(getattr(self, 'qty_invoiced', 0.0) or 0.0) >= q and q > 0:
            self.invoice_status = 'invoiced'
        elif float(getattr(self, 'qty_delivered', 0.0) or 0.0) > q:
            self.invoice_status = 'upselling'
        else:
            self.invoice_status = 'no'