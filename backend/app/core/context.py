# backend/app/core/context.py
import contextvars
from typing import Optional, Dict, Any, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from app.core.graph import Graph

# --- 1. Definición del Environment (El Contexto Rico) ---

class Environment:
    """
    🌍 CONTEXTO DE EJECUCIÓN (Enterprise Scope)
    Viaja a través de toda la request encapsulando:
    - Identidad (User ID)
    - Modo Superusuario (Sudo)
    - Preferencias (Idioma, Compañía)
    - Contexto del Grafo (Para cálculos aislados)
    """
    # 💎 FIX FASE Final: Soporte nativo para Integers en user_id
    def __init__(
        self, 
        user_id: Optional[Union[int, str]] = None, 
        su: bool = False, 
        context: Dict[str, Any] = None,
        graph: Optional['Graph'] = None
    ):
        # Identidad
        self.user_id = user_id or "public"
        self.su = su  # SuperUser Mode (Bypass reglas)
        
        # Preferencias & Estado
        self.context = context or {}
        
        # 🔥 Conexión al Grafo Vivo (Tu ERP es un Grafo, no solo SQL)
        self.graph = graph 

    # --- Atajos Mágicos ---
    
    @property
    def uid(self) -> Union[int, str]:
        return self.user_id

    @property
    def lang(self):
        return self.context.get('lang', 'es_PE')

    def sudo(self):
        """Retorna una copia de este entorno con permisos de Dios."""
        return Environment(
            user_id=self.user_id, # Conservamos el ID, solo subimos el privilegio
            su=True,
            context=self.context,
            graph=self.graph
        )

    def with_context(self, **kwargs):
        """Retorna un nuevo entorno con contexto modificado."""
        new_ctx = {**self.context, **kwargs}
        return Environment(
            user_id=self.user_id,
            su=self.su,
            context=new_ctx,
            graph=self.graph
        )

    def __repr__(self):
        mode = "⚡SUDO" if self.su else "👤USER"
        return f"<{mode} id={self.user_id} ctx={self.context}>"

# --- 2. Gestión Global del Contexto (Thread-Safe & Async-Safe) ---

# Variable mágica que vive en el ciclo de eventos de Python, aislada por cada request
_current_env: contextvars.ContextVar[Environment] = contextvars.ContextVar("current_env", default=None)

class Context:
    """
    🧠 GESTOR DE CONTEXTO AISLADO (Nivel HiperDios)
    Maneja la identidad y la memoria (Grafo) de forma segura en entornos concurrentes.
    Cero variables globales. Cero fugas de datos entre usuarios.
    """
    
    @staticmethod
    def set_env(env: Environment) -> contextvars.Token:
        """Inyecta el entorno actual (Env) en la burbuja de la petición."""
        return _current_env.set(env)
        
    @staticmethod
    def get_env() -> Optional[Environment]:
        """Obtiene el objeto Environment completo de la petición actual."""
        return _current_env.get()

    @staticmethod
    def get_user() -> Optional[Union[int, str]]:
        """Extrae el ID del usuario directamente del entorno aislado."""
        env = _current_env.get()
        return env.user_id if env else None

    @staticmethod
    def get_graph() -> Optional['Graph']:
        """Extrae la memoria (Grafo) de la petición actual."""
        env = _current_env.get()
        return env.graph if env else None

    # Métodos de compatibilidad por si algún módulo los sigue llamando
    @staticmethod
    def set_user(user_id: Union[int, str]):
        current = _current_env.get()
        if current:
            new_env = Environment(
                user_id=user_id, 
                su=current.su, 
                context=current.context,
                graph=current.graph
            )
            _current_env.set(new_env)
        else:
            _current_env.set(Environment(user_id=user_id))
            
    @staticmethod
    def clear():
        """Resetea el contexto (útil para tests)."""
        _current_env.set(None)