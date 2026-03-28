# backend/app/core/abstract_models.py
from app.core.orm import Model, Field, SelectionField, RelationField, compute

class AbstractDocument(Model):
    """
    📄 Plantilla Maestra para Cabeceras de Documentos (Ventas, Compras, Facturas)
    Hereda de Model (que ya inyecta el Bloqueo Optimista: write_version, write_date).
    No crea tabla en Postgres (_abstract = True).
    """
    _abstract = True

    name = Field(type_='string', label='Referencia', default='Nuevo', readonly=True)
    
    # 🚀 ESTADO BASE: Garantiza que la regla de inmutabilidad del ORM siempre funcione
    state = SelectionField(
        options=[('draft', 'Borrador'), ('done', 'Completado'), ('cancel', 'Cancelado')],
        default='draft', label='Estado'
    )
    
    # ⚡ LA SOLUCIÓN SDUI: El motor inyectará automáticamente la compañía 1 en el default_get
    # En un entorno multi-tenant avanzado, esto sería: default=lambda self: self.env.user.company_id
    company_id = RelationField("res.company", label="Compañía", required=True, default=1)
    
    # Nota: El partner_id NO tiene default. El usuario ESTÁ OBLIGADO a seleccionarlo en la UI.
    partner_id = RelationField("res.partner", label="Contacto", required=True)
    
    amount_total = Field(type_='float', label='Total', default=0.0, readonly=True)


class AbstractDocumentLine(Model):
    """
    📑 Plantilla Maestra para Líneas de Detalle.
    Contiene la lógica matemática universal de Subtotales y Tipos de Línea.
    """
    _abstract = True

    # 🚀 MOTOR DE ORDENAMIENTO: Vital para que el Drag & Drop del frontend se guarde en Postgres
    sequence = Field(type_='int', default=10, label='Secuencia')

    display_type = SelectionField(
        options=[('line_section', 'Sección'), ('line_note', 'Nota')], 
        default=None, label='Tipo de Visualización'
    )
    
    name = Field(type_='string', label='Descripción') 
    product_id = RelationField("product.product", label='Producto')
    
    qty = Field(type_='float', default=1.0, label='Cantidad')
    price_unit = Field(type_='float', default=0.0, label='Precio Unitario')
    
    price_subtotal = Field(type_='float', label='Subtotal', default=0.0, readonly=True)

    @compute(depends=['qty', 'price_unit', 'display_type'])
    def _compute_subtotal(self):
        """
        Matemática Universal: Si es una sección/nota, el subtotal es 0.
        Usamos float() para garantizar compatibilidad total en el motor de RAM.
        """
        if self.display_type:
            self.price_subtotal = 0.0
        else:
            # Blindaje contra valores None y conversión de tipos estricta
            quantity = float(self.qty if self.qty is not None else 0.0)
            unit_price = float(self.price_unit if self.price_unit is not None else 0.0)
            self.price_subtotal = quantity * unit_price