# backend/modules/core_system/models/ir_model_fields.py
from app.core.orm import Model, Field, RelationField
from typing import List

# backend/modules/core_system/models/ir_model_fields.py
from app.core.orm import Model, Field, RelationField

class IrModelFields(Model):
    """
    ⚙️ DICCIONARIO DE CAMPOS (ir.model.fields)
    """
    _rec_name = "name"

    # Ahora 'required=True' será aceptado por el __init__ de RelationField
    model_id = RelationField("IrModel", label="Modelo Padre", required=True)
    
    name = Field(type_='string', label='Nombre Técnico', required=True)
    field_description = Field(type_='string', label='Etiqueta')
    ttype = Field(type_='string', label='Tipo de Campo', required=True)
    
    relation = Field(type_='string', label='Modelo Relacionado')
    required = Field(type_='bool', default=False, label='Obligatorio')
    readonly = Field(type_='bool', default=False, label='Solo Lectura')
    index = Field(type_='bool', default=False, label='Indexado')
    state = Field(type_='string', default='base', label='Estado')

    # =========================================================
    # MÉTODOS DE NEGOCIO (DSL)
    # =========================================================

    @classmethod
    async def get_fields_by_model(cls, model_name: str) -> List['IrModelFields']:
        """
        🔍 Busca todos los campos pertenecientes a un modelo técnico específico.
        """
        from .ir_model import IrModel
        
        # 1. Obtenemos el ID del modelo
        model_record = await IrModel.get_model_by_name(model_name)
        if not model_record:
            return []
            
        # 2. Buscamos los campos que tengan ese model_id
        return await cls.search([('model_id', '=', model_record.id)])

    def ensure_one(self):
        """🛡️ Seguridad: Garantiza que no operamos sobre un conjunto vacío."""
        if not self.id:
            raise ValueError("Acción requerida sobre un registro único, pero el registro está vacío.")
        return True