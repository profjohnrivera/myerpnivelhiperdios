# backend/app/core/env.py
import contextvars
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

from app.core.registry import Registry

if TYPE_CHECKING:
    from app.core.graph import Graph

_current_env: contextvars.ContextVar[Optional["Env"]] = contextvars.ContextVar("current_env", default=None)


class Env:
    """
    Único entorno oficial del ERP.
    """

    def __init__(
        self,
        user_id: Union[int, str] = "public",
        graph: Optional["Graph"] = None,
        su: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.graph = graph
        self.su = su or (str(user_id) == "system")
        self.context = context or {}

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
        return Env(
            user_id=self.user_id,
            su=True,
            context=self.context.copy(),
            graph=self.graph,
        )

    def with_context(self, **kwargs) -> "Env":
        new_ctx = {**self.context, **kwargs}
        return Env(
            user_id=self.user_id,
            su=self.su,
            context=new_ctx,
            graph=self.graph,
        )

    def __repr__(self):
        return f"<Env(user={self.user_id}, su={self.su}, ctx={self.context})>"


class Context:
    """
    Fachada estática única.
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
    def set_user(user_id: Union[int, str]):
        current = _current_env.get()
        if current:
            Env(
                user_id=user_id,
                su=current.su,
                context=current.context.copy(),
                graph=current.graph,
            )
        else:
            Env(user_id=user_id)

    @staticmethod
    def clear():
        _current_env.set(None)