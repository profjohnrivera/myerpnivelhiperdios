# backend/app/api/v1/onchange.py

import asyncio
import traceback
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Body, Depends

from app.core.registry import Registry
from app.core.security import get_current_user

from .runtime import request_env
from .serializers import _serialize_record, _clean_m2o_payload

router = APIRouter()


def _declared_fields_for_model(model_cls) -> Dict[str, Any]:
    """
    Devuelve solo campos declarados del modelo.
    No properties, no helpers, no display_name.
    """
    if hasattr(model_cls, "_declared_fields"):
        try:
            return model_cls._declared_fields() or {}
        except Exception:
            pass

    fields = {}
    for name in dir(model_cls):
        attr = getattr(model_cls, name, None)
        if hasattr(attr, "get_meta"):
            fields[name] = attr
    return fields


def _sanitize_onchange_payload(model_cls, data: dict, model_name: str) -> dict:
    """
    Limpia relaciones y luego filtra a SOLO campos declarados.
    """
    cleaned = _clean_m2o_payload(data or {}, model_name=model_name)
    declared = _declared_fields_for_model(model_cls)

    safe = {}
    for key, value in cleaned.items():
        if key in declared:
            safe[key] = value
    return safe


async def _deep_trigger_onchanges(record, payload_data: dict):
    """
    Dispara onchange del registro y de hijos existentes si el payload toca x2many.
    """
    declared = _declared_fields_for_model(record.__class__)

    # Recorre hijos anidados solo si el campo realmente existe y es one2many
    for field_name, field_value in payload_data.items():
        field_def = declared.get(field_name)
        if not field_def or not hasattr(field_def, "get_meta"):
            continue

        meta = field_def.get_meta() or {}
        if meta.get("type") != "one2many":
            continue

        if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
            try:
                nested_records = getattr(record, field_name, None)
            except Exception:
                nested_records = None

            if nested_records and hasattr(nested_records, "__iter__"):
                nested_list = list(nested_records)
                for i, item_payload in enumerate(field_value):
                    if i < len(nested_list):
                        await _deep_trigger_onchanges(nested_list[i], item_payload)

    # Dispara onchange methods del propio modelo
    for attr_name in dir(record.__class__):
        method = getattr(record.__class__, attr_name, None)
        if hasattr(method, "_onchange_fields"):
            if any(f in payload_data for f in method._onchange_fields):
                bound_method = getattr(record, attr_name)
                if asyncio.iscoroutinefunction(bound_method):
                    await bound_method()
                else:
                    result = bound_method()
                    if asyncio.iscoroutine(result):
                        await result


@router.post("/data/{model_name}/onchange")
async def onchange_record(
    model_name: str,
    payload: dict = Body(...),
    current_user_id: int = Depends(get_current_user),
):
    """
    Onchange seguro:
    - solo acepta campos declarados del modelo
    - no escribe properties/helpers
    - limpia payload relacional antes de aplicarlo
    """
    try:
        async with request_env(current_user_id) as (env, session_graph):
            ModelClass = Registry.get_model(model_name)
            record_id = payload.get("id")

            data = _sanitize_onchange_payload(
                ModelClass,
                payload.get("data", {}) or {},
                model_name=model_name,
            )

            if record_id and str(record_id).isdigit():
                record = ModelClass(_id=int(record_id), context=session_graph, env=env)
                rs = record.__class__.browse([int(record_id)], context=session_graph)
                await rs.load_data()
            else:
                record = ModelClass(context=session_graph, env=env)

            declared = _declared_fields_for_model(ModelClass)

            for field_name, field_value in data.items():
                if field_name not in declared:
                    continue
                try:
                    setattr(record, field_name, field_value)
                except Exception:
                    # Onchange nunca debe romper por un setter no aplicable;
                    # solo ignora la mutación inválida y sigue evaluando.
                    pass

            await _deep_trigger_onchanges(record, data)
            return await _serialize_record(env, record, model_name)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))