# backend/app/api/v1/actions.py

import traceback

from fastapi import APIRouter, HTTPException, Body, Depends

from app.core.security import get_current_user
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.transaction import transaction
from app.core.worker import WorkerEngine

from .runtime import request_env
from .serializers import _serialize_record

router = APIRouter()


@router.post("/data/{model_name}/{record_id}/call/{method}")
async def call_action(
    model_name: str,
    record_id: int,
    method: str,
    params: dict = Body(default={}),
    current_user_id: int = Depends(get_current_user),
):
    print(f"\n🎯 [API] {model_name}.{method}() → ID: {record_id}")

    try:
        actual_method = method

        if "wrapper" in method.lower():
            if model_name in ["sale.order", "sale_order"]:
                actual_method = params.get("action_name", "action_confirm")
            print(f"🔧 [REDIRECCIÓN] {method} → {actual_method}")

        if actual_method.endswith("_async"):
            params["record_id"] = record_id
            await WorkerEngine.enqueue(
                model_name=model_name,
                method_name=actual_method,
                kwargs=params,
            )
            return {
                "status": "success",
                "type": "notification",
                "title": "Procesando Tarea",
                "message": "La operación se está ejecutando en segundo plano.",
            }

        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                records = env[model_name].browse([record_id], context=session_graph)
                if not records:
                    raise HTTPException(status_code=404, detail="No encontrado")

                await records.load_data()

                if not hasattr(records[0], actual_method):
                    if hasattr(records[0], actual_method + "_async"):
                        actual_method = actual_method + "_async"
                    else:
                        raise HTTPException(status_code=405, detail=f"Método '{actual_method}' no definido")

                print(f"⚡ [EJECUCIÓN] {actual_method}")
                result = await getattr(records[0], actual_method)(**params)

                storage = PostgresGraphStorage()
                await storage.save(session_graph)

                return {
                    "status": "success",
                    "result": result,
                    "data": await _serialize_record(env, records[0], model_name),
                }

    except Exception as e:
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))