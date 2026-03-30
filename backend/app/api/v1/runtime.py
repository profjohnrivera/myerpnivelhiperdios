# backend/app/api/v1/runtime.py

from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from app.core.env import Env, Context
from app.core.orm import Model
from app.core.graph import Graph


@asynccontextmanager
async def request_env(user_id: int | str) -> AsyncIterator[Tuple[Env, Graph]]:
    """
    Crea un session graph aislado por request y activa el Env en ContextVar.
    """
    session_graph = Model._graph.clone_for_session()
    env = Env(user_id=user_id, graph=session_graph)
    token = Context.set_env(env)
    try:
        yield env, session_graph
    finally:
        Context.restore(token)