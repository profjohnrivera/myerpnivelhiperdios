# backend/modules/core_system/models/ir_config_parameter.py
from app.core.orm import Model, Field

class IrConfigParameter(Model):
    """
    ⚙️ PARÁMETROS DEL SISTEMA
    Almacén de variables clave/valor accesibles globalmente por el Kernel.
    Ejemplo: 'web.base.url' -> 'https://mi-erp.com'
    """
    _name = 'ir.config_parameter'
    _rec_name = 'key'

    key = Field(type_='string', label='Clave', required=True, index=True)
    value = Field(type_='string', label='Valor', required=True)
    
    # Opcional: Para categorizar configuraciones (Ventas, Contabilidad, API, etc.)
    group = Field(type_='string', label='Grupo Lógico', default='system')

    @classmethod
    async def get_param(cls, key: str, default: str = None) -> str:
        """
        🛡️ Helper rápido para extraer un parámetro desde cualquier parte del código.
        Uso: await env['ir.config_parameter'].get_param('api.token')
        """
        records = await cls.search([('key', '=', key)], limit=1)
        if records:
            return records[0].value
        return default