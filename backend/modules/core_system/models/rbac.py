# backend/modules/core_system/models/rbac.py
from typing import Union
from app.core.orm import Model, Field, RelationField
from app.core.env import Context

class ResGroups(Model):
    """ 🎭 ROLES DE USUARIO (Grupos) """
    _name = 'res.groups'
    _rec_name = 'name'
    
    name = Field(type_='string', label='Nombre del Rol', required=True)

class IrModelAccess(Model):
    """ 
    🚦 MATRIZ DE ACCESO (ACL)
    Define qué puede hacer cada Rol sobre cada Modelo Técnico.
    """
    _name = 'ir.model.access'
    _rec_name = 'name'
    
    name = Field(type_='string', label='Descripción', required=True)
    model_id = RelationField('ir.model', label='Modelo Técnico', required=True, ondelete='cascade')
    group_id = RelationField('res.groups', label='Rol Requerido') 
    
    perm_read = Field(type_='bool', default=False, label='Lectura')
    perm_write = Field(type_='bool', default=False, label='Escritura')
    perm_create = Field(type_='bool', default=False, label='Creación')
    perm_unlink = Field(type_='bool', default=False, label='Eliminación')

    @classmethod
    async def check_permissions(cls, env, target_model: str, operation: str, user_id: Union[int, str]) -> bool:
        """ 
        🧠 MOTOR DE EVALUACIÓN RBAC (Nivel HiperDios) 
        Agnóstico de tipos, protegido contra Lazy-Loading y Recordsets.
        """
        # 1. 👑 BYPASS CRÍTICO: El instalador y el Modo SUDO pasan directo
        if str(user_id) == 'system' or Context.is_sudo(): 
            return True
            
        sudo_env = env.sudo()

        # 2. 🛡️ CARGAR EL USUARIO A LA RAM
        users = sudo_env['res.users'].browse([user_id])
        await users.load_data() 
        if not users: return False
        user = users[0]

        if getattr(user, 'login', '') == 'admin': 
            return True

        # 3. 🎯 IDENTIFICAR EL ID TÉCNICO DEL MODELO
        IrModel = sudo_env['ir.model']
        target_model_rec = await IrModel.search([('model', '=', target_model)])
        if not target_model_rec: 
            return True # Si no existe, permitimos para no frenar el Boot
        m_id = target_model_rec[0].id

        # 4. 🪪 EXTRACCIÓN BLINDADA DE GAFETES (Resolución del Recordset Bug)
        user_groups = set()
        # Buscamos group_ids, o su nombre legacy role_id
        raw_groups = getattr(user, 'group_ids', None) or getattr(user, 'role_id', None)
        
        if raw_groups:
            # Si tiene __iter__ (es Recordset, Lista o Set) y no es String ni Dict
            if hasattr(raw_groups, '__iter__') and not isinstance(raw_groups, (str, dict)):
                items = raw_groups
            else:
                items = [raw_groups]
                
            for g in items:
                # 💎 FIX FASE 4: Guardamos los permisos en Sets de ENTEROS
                if hasattr(g, 'id'): user_groups.add(int(g.id) if str(g.id).isdigit() else g.id)
                elif isinstance(g, dict) and 'id' in g: user_groups.add(int(g['id']) if str(g['id']).isdigit() else g['id'])
                elif g: user_groups.add(int(g) if str(g).isdigit() else g)

        # 5. 🚦 BUSCAR REGLAS PARA LA TABLA Y OPERACIÓN
        # 💎 FIX FASE 4: m_id ya es numérico, mantenemos tipado seguro
        rules = await sudo_env['ir.model.access'].search([
            ('model_id', '=', m_id),
            (f'perm_{operation}', '=', True)
        ])
        
        if not rules: 
            return False # CLOSED BY DEFAULT
            
        await rules.load_data()

        # 6. 🔓 EVALUACIÓN DE CERRADURAS
        for rule in rules:
            r_group = getattr(rule, 'group_id', None)
            
            # Si no exige grupo, es regla GLOBAL
            if not r_group: 
                return True 
            
            # Extraer ID del grupo exigido y castearlo a INT
            r_group_id = None
            if hasattr(r_group, 'id'): r_group_id = int(r_group.id) if str(r_group.id).isdigit() else r_group.id
            elif isinstance(r_group, (list, tuple)) and r_group: r_group_id = int(r_group[0]) if str(r_group[0]).isdigit() else r_group[0]
            elif r_group: r_group_id = int(r_group) if str(r_group).isdigit() else r_group

            # Cruzar Gafete (user_groups) con Cerradura (r_group_id)
            if r_group_id and r_group_id in user_groups:
                return True
                
        return False