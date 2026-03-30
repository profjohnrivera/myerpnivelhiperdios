# backend/app/api/v1/data_read.py

import json
import traceback

from fastapi import APIRouter, HTTPException, Body, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.registry import Registry
from app.core.security import get_current_user
from app.core.storage.postgres_storage import PostgresGraphStorage

from .runtime import request_env
from .serializers import _serialize_records, _serialize_record

router = APIRouter()


@router.get("/data/{model_name}/default_get")
async def default_get(model_name: str, current_user_id: int = Depends(get_current_user)):
    try:
        async with request_env(current_user_id) as (env, session_graph):
            ModelClass = Registry.get_model(model_name)
            virtual_record = ModelClass(context=session_graph)
            return await _serialize_record(env, virtual_record, model_name)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{model_name}/name_search")
async def name_search(
    model_name: str,
    q: str = Query(default="", description="Texto a buscar"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with request_env(current_user_id) as (env, session_graph):
            ModelClass = Registry.get_model(model_name)
            return await ModelClass.name_search(query=q, limit=limit, context=session_graph)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/{model_name}/search")
async def search_data(
    model_name: str,
    payload: dict = Body(default={}),
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with request_env(current_user_id) as (env, session_graph):
            domain = payload.get("domain", [])
            limit = payload.get("limit", 80)
            offset = payload.get("offset", 0)
            order_by = payload.get("order_by", None)
            fields = payload.get("fields", None)

            if not fields:
                model_cls = Registry.get_model(model_name)
                fields = [
                    fname for fname in dir(model_cls)
                    if hasattr(getattr(model_cls, fname, None), "get_meta")
                    and getattr(model_cls, fname).get_meta().get("type") != "one2many"
                ]

            records = await env[model_name].search(
                domain=domain,
                limit=limit,
                offset=offset,
                order_by=order_by,
                context=session_graph,
            )

            if len(records) < limit:
                total = offset + len(records)
            else:
                storage = PostgresGraphStorage()
                all_ids = await storage.search_domain(model_name, domain)
                total = len(all_ids)

            async def generate_json_stream():
                yield f'{{"total": {total}, "data": ['
                chunk_size = 500
                first = True

                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    serialized_chunk = await _serialize_records(env, chunk, model_name, fields=fields)

                    for item in serialized_chunk:
                        if not first:
                            yield ","
                        yield json.dumps(item, default=str)
                        first = False

                yield "]}"

            return StreamingResponse(generate_json_stream(), media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{model_name}/{record_id}")
async def read_record(
    model_name: str,
    record_id: int,
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with request_env(current_user_id) as (env, session_graph):
            records = env[model_name].browse([record_id], context=session_graph)
            if not records:
                raise HTTPException(status_code=404, detail="No encontrado")
            return await _serialize_record(env, records[0], model_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))