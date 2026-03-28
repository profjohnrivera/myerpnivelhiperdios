# backend/modules/core_base/models/res_users.py
from app.core.orm import Model, Field, RelationField, Many2manyField
from app.core.security import hash_password, verify_password

class ResUsers(Model):
    """
    👤 USUARIOS DEL SISTEMA (HiperDios Core)
    Identidad digital vinculada a un Partner con seguridad criptográfica nativa.
    """
    _name = 'res.users'
    _rec_name = 'name' # Usamos el nombre para mostrar en la interfaz

    # Delegación: Un usuario "es" un partner en el mundo real
    partner_id = RelationField("res.partner", label="Contacto Asociado")
    
    # 🏢 FIX: Compañía principal del usuario (vital para multi-empresa y fix_db.py)
    company_id = RelationField("res.company", label="Compañía Principal")
    
    # Mantenemos el nombre a nivel de usuario para la interfaz rápida
    name = Field(type_='string', label='Nombre Completo', required=True)
    login = Field(type_='string', label='Login / Usuario', required=True, index=True)
    
    # 🛡️ Seguridad Nativa
    password = Field(type_='string', label='Password Hash')
    active = Field(type_='bool', default=True, label='Activo')

    # 🪪 FIX: Relación Many2many con los roles (RBAC) - El motor de seguridad lee de aquí
    group_ids = Many2manyField('res.groups', label='Roles / Grupos')

    # =========================================================
    # 🪝 HOOKS DE CICLO DE VIDA
    # =========================================================
    @classmethod
    async def create(cls, vals: dict, context=None):
        # 💡 Adaptado para recibir el context del Grafo si el ORM lo envía
        if 'password' in vals and vals['password']:
            # 🛡️ Aplicamos await porque la función criptográfica ahora está en un hilo secundario
            vals['password'] = await hash_password(vals['password'])
        return await super().create(vals, context=context)

    async def write(self, vals: dict):
        if 'password' in vals and vals['password']:
            # 🛡️ Aplicamos await
            vals['password'] = await hash_password(vals['password'])
        return await super().write(vals)

    # =========================================================
    # 🔐 VALIDACIÓN ENCAPSULADA
    # =========================================================
    async def _check_credentials(self, password: str) -> bool:
        """
        Valida la contraseña del usuario instanciado.
        Transformado a async para no bloquear el Event Loop.
        """
        if not self.password:
            raise PermissionError("Usuario sin contraseña asignada.")
        
        # 🛡️ Aplicamos await
        is_valid = await verify_password(password, self.password)
        if not is_valid:
            raise PermissionError("Contraseña incorrecta.")
        
        return True