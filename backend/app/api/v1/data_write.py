# backend/app/api/v1/data_write.py

import traceback

from fastapi import APIRouter, HTTPException, Body, Depends

from app.core.security import get_current_user
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.transaction import transaction

from .runtime import request_env
from .serializers import _serialize_record, _clean_m2o_payload

router = APIRouter()


@router.post("/data/{model_name}/create")
async def create_data(
    model_name: str,
    vals: dict = Body(...),
    current_user_id: int = Depends(get_current_user),
):
    """
    Frontera de escritura:
    - la API NO reinterpreta el dominio
    - limpia payload
    - delega a create() del modelo
    - persiste el graph
    """
    try:
        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                safe_vals = _clean_m2o_payload(vals, model_name)

                if "id" in safe_vals and not safe_vals["id"]:
                    del safe_vals["id"]

                new_record = await env[model_name].create(safe_vals, context=session_graph)

                storage = PostgresGraphStorage()
                id_mapping = await storage.save(session_graph)

                if str(new_record.id) in id_mapping:
                    new_record._id_val = id_mapping[str(new_record.id)]

                return {
                    "status": "success",
                    "data": await _serialize_record(env, new_record, model_name),
                }

    except Exception as e:
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Error del Servidor: {str(e)}")


@router.post("/data/{model_name}/{record_id}/write")
async def write_data(
    model_name: str,
    record_id: int,
    vals: dict = Body(...),
    current_user_id: int = Depends(get_current_user),
):
    """
    Frontera de escritura:
    - la API NO extrae x2many
    - la API NO recalcula totales por SQL
    - el dominio es el único dueño de la mutación
    """
    try:
        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                records = env[model_name].browse([record_id], context=session_graph)
                if not records:
                    raise HTTPException(status_code=404, detail="Registro no encontrado")

                await records.load_data()

                safe_vals = _clean_m2o_payload(vals, model_name)

                if "id" in safe_vals:
                    del safe_vals["id"]

                await records[0].write(safe_vals)

                storage = PostgresGraphStorage()
                await storage.save(session_graph)

                return {
                    "status": "success",
                    "data": await _serialize_record(env, records[0], model_name),
                }

    except Exception as e:
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Error del Servidor: {str(e)}")


@router.delete("/data/{model_name}/{record_id}")
async def delete_record(
    model_name: str,
    record_id: int,
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                records = env[model_name].browse([record_id], context=session_graph)
                if not records:
                    raise HTTPException(status_code=404, detail="No encontrado")

                await records.load_data()
                await records[0].unlink()

                storage = PostgresGraphStorage()
                await storage.save(session_graph)

                return {"status": "success"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))