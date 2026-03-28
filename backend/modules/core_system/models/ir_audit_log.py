# backend/app/core/models/ir_audit_log.py
from app.core.orm import Model, Field, datetime

class IrAuditLog(Model):
    _name = 'ir.audit.log'
    
    res_model = Field(type_='string', index=True, required=True)
    
    # 💎 FIX FASE 3: Ahora audita IDs enteros
    res_id = Field(type_='integer', index=True, required=True)
    user_id = Field(type_='integer', index=True)
    
    action = Field(type_='selection', options=[('create', 'Creación'), ('write', 'Modificación'), ('unlink', 'Eliminación')])
    changes = Field(type_='jsonb') # Almacena: {"field": [old_val, new_val]}
    timestamp = Field(type_='datetime', default=datetime.datetime.utcnow)