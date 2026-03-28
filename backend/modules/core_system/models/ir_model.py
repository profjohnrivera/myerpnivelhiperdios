# backend/modules/core_system/models/ir_model.py
from app.core.orm import Model, Field, One2manyField, RelationField
from typing import Optional

class IrModel(Model):
    """
    🧠 Registro Central de Modelos (El ADN del sistema)
    """
    _name = 'ir.model'
    _rec_name = "name" # 👈 Esto es lo que se mostrará en lugar del UUID

    name = Field(type_='string', label='Nombre del Modelo', required=True)
    model = Field(type_='string', label='Modelo Técnico', required=True) # Ej: sale.order
    info = Field(type_='text', label='Información/Descripción')
    
    # --- Lógica Enterprise ---
    state = Field(type_='string', default='base', label='Origen') # base, manual, custom
    transient = Field(type_='bool', default=False, label='Es Transitorio') # Para Wizards
    
    # Relación: Un modelo tiene muchos campos
    field_ids = One2manyField("ir.model.fields", label="Campos del Modelo")

    # =========================================================
    # MÉTODOS DE NEGOCIO (DSL)
    # =========================================================

    @classmethod
    async def get_model_by_name(cls, model_name: str) -> Optional['IrModel']:
        """Busca la definición técnica por su nombre (ej: 'res.partner')"""
        results = await cls.search([('model', '=', model_name)])
        return results[0] if results else None

    def ensure_one(self):
        """🛡️ Seguridad: Valida que estemos operando sobre un único registro."""
        if not self.id:
            raise ValueError("El registro no existe o está vacío.")
        # En recordsets de Odoo aquí se validaría len(self._ids) == 1
        return True


class IrModelFields(Model):
    """
    🧬 Registro de Campos (Metadatos de cada atributo)
    """
    _name = 'ir.model.fields'
    _rec_name = 'field_description'

    name = Field(type_='string', required=True, label='Nombre Técnico')
    field_description = Field(type_='string', required=True, label='Etiqueta')
    
    # 🧠 EL FIX MAESTRO: RelationField obliga a la BD y al Frontend a usar el _rec_name
    model_id = RelationField('ir.model', required=True, ondelete='cascade', label='Modelo Padre')
    
    ttype = Field(type_='string', required=True, label='Tipo de Campo')
    state = Field(type_='string', default='base', label='Estado')
    
    # Campos adicionales para tener la vista completa idéntica a Odoo
    readonly = Field(type_='bool', default=False, label='Solo Lectura')
    required = Field(type_='bool', default=False, label='Obligatorio')
    index = Field(type_='bool', default=False, label='Indexado')
    relation = Field(type_='string', label='Modelo Relacionado') # Ej: 'res.partner' para Many2one