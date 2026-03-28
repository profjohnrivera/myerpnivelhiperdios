# backend/app/core/mixins.py
from app.core.orm import Field, SelectionField

class TrazableMixin:
    """
    👁️ MIXIN DE TRAZABILIDAD
    Indica al Core que este modelo debe ser vigilado por el Auditor Universal.
    """
    # El Registry detectará este nombre de clase para activar la auditoría.
    _track_visibility = True 

class AprobableMixin:
    """
    ⚖️ MIXIN DE APROBACIÓN
    Inyecta automáticamente un flujo de estados y lógica de validación.
    """
    state = SelectionField(
        options=['draft', 'waiting', 'approved', 'rejected'], 
        default='draft', 
        label='Estado'
    )
    
    async def action_approve(self):
        """Método heredado para aprobar registros."""
        await self.write({'state': 'approved'})

    async def action_reject(self):
        """Método heredado para rechazar registros."""
        await self.write({'state': 'rejected'})

    async def action_set_draft(self):
        """Método heredado para volver a borrador."""
        await self.write({'state': 'draft'})