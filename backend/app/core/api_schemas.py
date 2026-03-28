# backend/app/core/api_schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union

# --- ESTRUCTURA JSON-RPC 2.0 ---

class RpcRequest(BaseModel):
    jsonrpc: str = Field("2.0", const=True)
    method: str             # Ej: "sale.action_confirm"
    params: Dict[str, Any]  # Ej: {"id": "ORD-001"}
    id: Union[str, int]     # ID de la petición para correlacionar respuesta

class RpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Union[str, int]

# --- Específicos para el ERP ---

class SearchParams(BaseModel):
    pattern: str

class ViewParams(BaseModel):
    view_id: str