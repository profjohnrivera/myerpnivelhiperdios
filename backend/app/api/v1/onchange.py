# backend/app/api/v1/onchange.py

import asyncio
import traceback

from fastapi import APIRouter, HTTPException, Body, Depends

from app.core.registry import Registry
from app.core.security import get_current_user

from .runtime import request_env
from .serializers import _serialize_record

router = APIRouter()


def _clean_onchange_payload(data):
    cleaned = {}
    for k, v in data.items():
        if isinstance(v, list):
            if len(v) >= 2 and not isinstance(v[0], dict) and (isinstance(v[0], int) or str(v[0]).isdigit()):
                cleaned[k] = int(v[0])
            elif v and isinstance(v[0], dict):
                cleaned[k] = [_clean_onchange_payload(child) for child in v]
            else:
                cleaned[k] = v
        else:
            cleaned[k] = v
    return cleaned


async def _deep_trigger_onchanges(record, payload_data):
    for field_name, field_value in payload_data.items():
        if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
            nested_records = getattr(record, field_name, None)
            if nested_records and hasattr(nested_records, "__iter__"):
                nested_list = list(nested_records)
                for i, item_payload in enumerate(field_value):
                    if i < len(nested_list):
                        await _deep_trigger_onchanges(nested_list[i], item_payload)

    for attr_name in dir(record.__class__):
        method = getattr(record.__class__, attr_name)
        if hasattr(method, "_onchange_fields"):
            if any(f in payload_data for f in method._onchange_fields):
                bound_method = getattr(record, attr_name)
                if asyncio.iscoroutinefunction(bound_method):
                    await bound_method()
                else:
                    bound_method()


@router.post("/data/{model_name}/onchange")
async def onchange_record(
    model_name: str,
    payload: dict = Body(...),
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with request_env(current_user_id) as (env, session_graph):
            ModelClass = Registry.get_model(model_name)
            record_id = payload.get("id")
            data = _clean_onchange_payload(payload.get("data", {}))

            if record_id and str(record_id).isdigit():
                record = ModelClass(_id=int(record_id), context=session_graph, env=env)
                await record.__class__.browse([int(record_id)], context=session_graph).load_data()
            else:
                record = ModelClass(context=session_graph, env=env)

            for field_name, field_value in data.items():
                if hasattr(record, field_name):
                    try:
                        setattr(record, field_name, field_value)
                    except Exception:
                        pass

            await _deep_trigger_onchanges(record, data)
            return await _serialize_record(env, record, model_name)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))