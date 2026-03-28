# backend/app/core/env.py
import contextvars
from typing import Any, Optional, Union, Dict, TYPE_CHECKING
from app.core.registry import Registry

if TYPE_CHECKING:
    from app.core.graph import Graph

# 1. 🛡️ Variable de contexto segura para concurrencia asíncrona (Aísla peticiones HTTP/Workers)
_current_env: contextvars.ContextVar[Optional['Env']] = contextvars.ContextVar("current_env", default=None)

class Env:
    """
    🌟 EL ENTORNO (The Environment) UNIFICADO
    Punto de entrada unificado para acceder a modelos y contexto de seguridad.
    Diseñado para ser inyectado en cada tarea asíncrona del ERP.
    
    Este objeto es el puente entre la identidad del usuario y su partición 
    privada de memoria (el Grafo clonado).
    """
    # 💎 FIX: Soporta Integers para ID de usuario (BIGSERIAL)
    def __init__(
        self, 
        user_id: Union[int, str] = "public", 
        graph: Optional['Graph'] = None,
        su: bool = False,
        context: Dict[str, Any] = None
    ):
        """
        Inicializa el entorno y lo ancla al contexto local de la tarea (Thread-safe).
        
        Args:
            user_id: ID del usuario (o 'system' para procesos internos).
            graph: Instancia del Grafo (debe ser un clon_for_session para seguridad).
        """
        self.user_id = user_id
        self.graph = graph
        self.su = su or (str(user_id) == 'system')
        self.context = context or {}
        
        # 💎 SINCRONIZACIÓN DE CONTEXTO (Reemplaza a context.py):
        # Empaquetamos los datos en este mismo objeto y lo subimos al 
        # almacén de variables de contexto (contextvars). 
        # Esto permite que el ORM recupere el grafo correcto sin mutaciones globales.
        _current_env.set(self)

    def __getitem__(self, model_name: str):
        """
        Permite el acceso dinámico a modelos: model = env['res.users']
        Retorna la clase del modelo registrada en el Cerebro (Registry).
        
        🛡️ SEGURIDAD ATÓMICA: No inyectamos el grafo en la clase global model_cls._graph.
        En su lugar, el ORM ahora está diseñado para llamar a Context.get_graph() 
        en tiempo de ejecución, obteniendo el clon que este Env acaba de setear.
        """
        model_cls = Registry.get_model(model_name)
        return model_cls

    @property
    def user(self):
        """
        Retorna el Recordset del usuario que está operando actualmente.
        Permite hacer: print(f"Hola, {env.user.name}")
        """
        if not self.user_id or self.user_id in ["public", "system"]:
            return None
        # Obtenemos la clase y buscamos por ID. 
        # Nota: browse usará internamente el contexto seteado en el __init__
        return self['res.users'].browse([self.user_id], context=self.graph)

    @property
    def uid(self) -> Union[int, str]:
        """Shortcut para obtener el ID del usuario actual."""
        return self.user_id

    def sudo(self) -> 'Env':
        """
        🚀 MODO DIOS: Retorna un nuevo entorno con privilegios de sistema, 
        manteniendo la misma partición de memoria (Grafo) de la sesión actual.
        Útil para bypass de reglas de acceso en procesos automáticos.
        """
        return Env(user_id='system', su=True, context=self.context, graph=self.graph)

    def __repr__(self):
        return f"<Env(user={self.user_id}, su={self.su})>"


# =========================================================================
# 🌐 GESTOR DE CONTEXTO ESTÁTICO (Retrocompatibilidad Pura)
# =========================================================================
class Context:
    """
    Mantiene vivos los métodos estáticos para que no tengas que reescribir 
    todo el código del ORM, Auditores y Decoradores que antes dependían de context.py.
    """
    @staticmethod
    def set_env(env: Env) -> contextvars.Token:
        return _current_env.set(env)
        
    @staticmethod
    def get_env() -> Optional[Env]:
        return _current_env.get()

    @staticmethod
    def get_user() -> Optional[Union[int, str]]:
        env = _current_env.get()
        return env.user_id if env else None

    @staticmethod
    def get_graph() -> Optional['Graph']:
        env = _current_env.get()
        return env.graph if env else None

    @staticmethod
    def set_user(user_id: Union[int, str]):
        current = _current_env.get()
        if current:
            # Recrea el entorno heredando el grafo actual
            Env(
                user_id=user_id, 
                su=current.su, 
                context=current.context,
                graph=current.graph
            )
        else:
            Env(user_id=user_id)