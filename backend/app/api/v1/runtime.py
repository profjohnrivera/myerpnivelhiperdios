# backend/app/api/v1/runtime.py

from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from app.core.env import Env, env_scope
from app.core.orm import Model
from app.core.graph import Graph


@asynccontextmanager
async def request_env(user_id: int | str) -> AsyncIterator[Tuple[Env, Graph]]:
    """
    ÚNICA vía oficial para crear el contexto aislado por request.

    P0:
    - clona exactamente un session graph por request
    - no depende de middleware global
    - no mezcla Env(auto-set) con Context.set_env redundante
    - usa env_scope() para activación/restauración limpia
    """
    master_graph = getattr(Model, "_graph", None)
    if master_graph is None:
        raise RuntimeError("Model._graph no está inicializado.")

    session_graph = master_graph.clone_for_session()
    env = Env(user_id=user_id, graph=session_graph, _skip_autoset=True)

    async with env_scope(env):
        yield env, session_graph