# backend/app/core/env.py
# ============================================================
# DISEÑO DEFINITIVO DEL CONTEXTO DE EJECUCIÓN
#
# REGLAS ARQUITECTURALES:
#
# 1. Env.__init__ SÍ auto-activa el ContextVar.
#    Razón: asyncio.Task aísla contextvars automáticamente.
#    Cada request/tarea tiene su propia copia → sin race conditions.
#    El boot también funciona correctamente sin ningún cambio extra.
#
# 2. sudo() / with_context() / with_user() NO auto-activan ContextVar.
#    Retornan un Env nuevo usando _make() que saltea el auto-set.
#    Activarlos accidentalmente corrompería el contexto del task actual.
#    Para activarlos temporalmente, usar env_scope().
#
# 3. env_scope(env) → async context manager que activa/restaura ContextVar.
#    Único mecanismo correcto para override temporal (sudo en process_nested_records).
#
# 4. Context.set_env / Context.restore → para endpoints que necesitan
#    gestión explícita del ciclo de vida (set al inicio, restore en finally).
#
# USO CORRECTO:
#   # Boot / init (auto-set):
#   env = Env(user_id="system", graph=graph)  → ContextVar activo ✓
#
#   # Endpoint (explícito):
#   env = Env(user_id=uid, graph=session_graph)  → ContextVar activo ✓
#   token = Context.set_env(env)  → redundante pero inofensivo
#   try: ...
#   finally: Context.restore(token)
#
#   # Sudo temporal:
#   async with env_scope(env.sudo()) as su_env:
#       await child[0].write(vals)  # ContextVar = sudo env
#   # ContextVar restaurado al salir ✓
# ============================================================

import contextvars
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, TYPE_CHECKING, Union

from app.core.registry import Registry

if TYPE_CHECKING:
    from app.core.graph import Graph

_current_env: contextvars.ContextVar[Optional["Env"]] = contextvars.ContextVar(
    "current_env",
    default=None,
)


class Env:
    """
    Entorno de ejecución del ERP.

    Env.__init__ activa el ContextVar automáticamente.
    asyncio.Task aísla contextvars por tarea → seguro para requests concurrentes.

    Para override temporal (sudo, with_context), usa env_scope().
    sudo() y compañía retornan un Env nuevo SIN activar el ContextVar.
    """

    # Flag interno para saltar el auto-set en constructores derivados
    _auto_set: bool = True

    def __init__(
        self,
        user_id: Union[int, str] = "public",
        graph: Optional["Graph"] = None,
        su: bool = False,
        context: Optional[Dict[str, Any]] = None,
        _skip_autoset: bool = False,
    ):
        self.user_id = user_id
        self.graph = graph
        self.su = su or (str(user_id) == "system")
        self.context = dict(context or {})

        # Auto-activa el ContextVar en el task actual.
        # Solo se salta cuando se construye un env derivado (sudo, with_context, etc.)
        # que NO debe reemplazar el contexto activo del task.
        if not _skip_autoset:
            _current_env.set(self)

    def __getitem__(self, model_name: str):
        return Registry.get_model(model_name)

    @property
    def uid(self) -> Union[int, str]:
        return self.user_id

    @property
    def lang(self) -> str:
        return self.context.get("lang", "es_PE")

    @property
    def user(self):
        if not self.user_id or self.user_id in ["public", "system"]:
            return None
        return self["res.users"].browse([self.user_id], context=self.graph)

    def sudo(self) -> "Env":
        """
        Retorna un Env con su=True SIN activar el ContextVar.
        Usar con env_scope() para activarlo temporalmente:
            async with env_scope(env.sudo()) as su_env: ...
        """
        return Env(
            user_id=self.user_id,
            su=True,
            context=self.context.copy(),
            graph=self.graph,
            _skip_autoset=True,
        )

    def with_context(self, **kwargs) -> "Env":
        """Retorna un Env con contexto extendido SIN activar el ContextVar."""
        return Env(
            user_id=self.user_id,
            su=self.su,
            context={**self.context, **kwargs},
            graph=self.graph,
            _skip_autoset=True,
        )

    def with_user(self, user_id: Union[int, str]) -> "Env":
        """Retorna un Env con usuario diferente SIN activar el ContextVar."""
        return Env(
            user_id=user_id,
            su=self.su if str(user_id) != "system" else True,
            context=self.context.copy(),
            graph=self.graph,
            _skip_autoset=True,
        )

    def clone(self) -> "Env":
        """Copia del Env sin activar ContextVar."""
        return Env(
            user_id=self.user_id,
            su=self.su,
            context=self.context.copy(),
            graph=self.graph,
            _skip_autoset=True,
        )

    def __repr__(self):
        return f"<Env(user={self.user_id}, su={self.su})>"


@asynccontextmanager
async def env_scope(env: "Env") -> AsyncIterator["Env"]:
    """
    Context manager que activa un Env temporalmente y lo restaura al salir.

    Uso:
        async with env_scope(env.sudo()) as su_env:
            await child[0].write(vals)
        # ContextVar restaurado al env anterior ✓

    Garantiza restauración incluso si ocurre una excepción.
    """
    token = _current_env.set(env)
    try:
        yield env
    finally:
        _current_env.reset(token)


class Context:
    """
    Fachada estática del contexto activo.
    """

    @staticmethod
    def set_env(env: "Env") -> contextvars.Token:
        """
        Activa explícitamente un env. Retorna un token para restaurar.
        Usar en endpoints: token = Context.set_env(env) ... finally: Context.restore(token)
        """
        return _current_env.set(env)

    @staticmethod
    def restore(token: contextvars.Token) -> None:
        """Restaura el ContextVar al estado previo al set_env()."""
        _current_env.reset(token)

    @staticmethod
    def get_env() -> Optional["Env"]:
        return _current_env.get()

    @staticmethod
    def get_user() -> Optional[Union[int, str]]:
        env = _current_env.get()
        return env.user_id if env else None

    @staticmethod
    def get_graph() -> Optional["Graph"]:
        env = _current_env.get()
        return env.graph if env else None

    @staticmethod
    def get_lang() -> str:
        env = _current_env.get()
        return env.lang if env else "es_PE"

    @staticmethod
    def is_sudo() -> bool:
        env = _current_env.get()
        return bool(env and env.su)

    @staticmethod
    def clear() -> None:
        _current_env.set(None)