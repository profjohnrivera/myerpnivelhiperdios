# backend/modules/core_system/policies.py
from app.core.policies import Policy
from app.core.env import Context
from app.core.registry import Registry
from typing import Dict, Any

class SequenceAccess(Policy):
    """
    🛡️ MOTOR DE SEGURIDAD HÍBRIDO (RBAC + Dynamic Rules)
    Controla el acceso a las Secuencias del sistema.
    """
    def __init__(self):
        super().__init__()
        self.name = "policy:core_system:sequence"
        # Dependencias: lo que el grafo debe darnos para evaluar
        self.depends_on = {"data:sequence:*:state", "data:sequence:*:active"}

    async def evaluate(self, inputs: Dict[str, Any], mode='read') -> bool:
        """
        Punto de entrada de evaluación.
        """
        # 1. BYPASS: Modo Sudo o Admin (Nivel Dios)
        if Context.is_sudo() or inputs.get('is_admin'):
            return True

        # 2. EVALUACIÓN DINÁMICA (Réplica de Odoo ir.rule)
        # Aquí consultamos las reglas guardadas en SecurityRule para el modelo 'Sequence'
        if not await self._check_dynamic_rules(inputs, mode):
            return False

        # 3. CONTROL DE LECTURA
        if mode == 'read':
            return self._check_read(inputs)

        # 4. CONTROL DE ESCRITURA / BORRADO
        if mode in ['write', 'unlink']:
            return self._check_write(inputs)
        
        return True

    def _check_read(self, inputs: Dict[str, Any]) -> bool:
        # Evitar lectura de secuencias archivadas a menos que sea admin
        return inputs.get(f'data:sequence:{inputs.get("id")}:active', True)

    def _check_write(self, inputs: Dict[str, Any]) -> bool:
        # A. State Locking: Las secuencias no suelen tener estados como 'done', 
        # pero si se implementan, bloqueamos edición.
        state = inputs.get(f'data:sequence:{inputs.get("id")}:state')
        if state in ['confirmed', 'done', 'locked']: 
            return False
            
        # B. Verificación de Roles
        user_groups = inputs.get('groups', [])
        if 'group_system_admin' in user_groups or 'group_manager' in user_groups:
            return True
        
        # Por defecto, un usuario normal NO edita secuencias de sistema
        return False

    async def _check_dynamic_rules(self, inputs: Dict[str, Any], mode: str) -> bool:
        """
        💎 EL CORAZÓN DE LA SEGURIDAD (TODO Resuelto): 
        Consulta al Registry/Grafo si hay SecurityRules activas para 'Sequence'
        y usa el compilador SQL para bloquear a nivel de base de datos.
        """
        env = Context.get_env()
        if not env or not env.uid:
            return True # Si no hay entorno, asumimos que es el Kernel operando en fase de Boot

        try:
            IrRule = Registry.get_model('ir.rule')
            domain = await IrRule.get_domain('ir.sequence', env.uid)
            
            if domain:
                record_id = inputs.get('id')
                if record_id:
                    # Validamos si el ID del registro que intentan tocar cumple con el dominio de seguridad
                    from app.core.storage.postgres_storage import PostgresGraphStorage
                    storage = PostgresGraphStorage()
                    
                    # Le enviamos el dominio de la regla + el ID al compilador SQL que creamos antes
                    valid_ids = await storage.search_domain('ir.sequence', domain + [('id', '=', record_id)])
                    if record_id not in valid_ids:
                        print(f"🛑 [SECURITY BLOCK] Usuario {env.uid} intentó acceder a ir.sequence({record_id}) pero RLS lo bloqueó.")
                        return False
        except Exception as e:
            print(f"⚠️ Error evaluando regla dinámica: {e}")
            pass
            
        return True

    async def can_trigger_action(self, inputs: Dict[str, Any], action: str) -> bool:
        """
        Controla quién puede pulsar el botón 'Generar Siguiente'.
        """
        # Solo usuarios autorizados pueden disparar el contador de una secuencia
        return await self.evaluate(inputs, mode='write')