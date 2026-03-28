# backend/app/core/exceptions.py
import traceback
import logging
from typing import Optional
from app.core.env import Context

class ERPException(Exception):
    """Base para todos los errores del ecosistema."""
    def __init__(self, message: str, code: str = "GENERIC_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class SecurityError(ERPException):
    """Errores de RLS o permisos."""
    def __init__(self, message: str = "Acceso Denegado"):
        super().__init__(message, code="SECURITY_DENIED")

class ValidationError(ERPException):
    """Errores de integridad de datos (@constrains)."""
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_FAILED")

class ExceptionHandler:
    """
    🕵️ MANEJADOR FORENSE
    Captura el error, lo formatea y decide si debe ir a Auditoría.
    """
    @staticmethod
    async def handle(e: Exception, model_name: Optional[str] = None):
        env = Context.get_env()
        error_type = e.__class__.__name__
        full_trace = traceback.format_exc()
        
        # Log en consola con estilo
        print(f"\n🔥 [FORENSIC ERROR] {error_type} en {model_name or 'Kernel'}")
        print(f"📝 Mensaje: {str(e)}")
        
        # Si el sistema ya está arriba, guardamos en la tabla de auditoría
        if env and model_name != 'ir.audit.log':
            try:
                AuditLog = env['ir.audit.log']
                await AuditLog.create({
                    'name': f"CRASH: {error_type}",
                    'res_model': model_name or 'system',
                    'old_value': 'OPERATIONAL',
                    'new_value': 'CRASHED',
                    'field_name': 'system_health',
                    'message': f"{str(e)}\n\n{full_trace}"
                })
            except:
                pass # Evitar bucle infinito si falla la auditoría
        
        return {"error": str(e), "code": getattr(e, 'code', 'UNKNOWN')}