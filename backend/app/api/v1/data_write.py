# backend/app/api/v1/data_write.py

import traceback

from fastapi import APIRouter, HTTPException, Body, Depends

from app.core.registry import Registry
from app.core.security import get_current_user
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.transaction import transaction

from .runtime import request_env
from .serializers import _serialize_record, _clean_m2o_payload
from .x2many import extract_x2many_data, process_nested_records

router = APIRouter()


async def _recalculate_totals_from_db(record, model_name: str, storage: PostgresGraphStorage):
    """
    Después de storage.save(), recalcula amount_total directamente en SQL
    sumando price_subtotal de líneas persistidas.
    """
    try:
        ModelClass = Registry.get_model(model_name)
        if not ModelClass:
            return

        total_fields = {}
        for fname in dir(ModelClass):
            attr = getattr(ModelClass, fname, None)
            if not hasattr(attr, "get_meta"):
                continue

            meta = attr.get_meta()
            if meta.get("type") == "one2many":
                child_model = getattr(attr, "related_model", None) or meta.get("target")
                inverse = getattr(attr, "inverse_name", None) or f"{model_name.split('.')[-1]}_id"
                if not child_model:
                    continue

                ChildClass = Registry.get_model(child_model)
                if not ChildClass:
                    continue

                if hasattr(ChildClass, "price_subtotal"):
                    total_fields[fname] = (child_model.replace(".", "_"), inverse)

        if not total_fields:
            return

        record_id = int(record._id_val)
        table_name = model_name.replace(".", "_")
        conn_or_pool = await storage.get_connection()

        for _, (child_table, inverse_field) in total_fields.items():
            sum_query = f"""
                SELECT COALESCE(SUM(price_subtotal), 0.0)
                FROM "{child_table}"
                WHERE "{inverse_field}" = $1
                  AND (display_type IS NULL OR display_type = '')
            """
            update_query = f"""
                UPDATE "{table_name}"
                SET amount_total = $1
                WHERE id = $2
            """

            try:
                if hasattr(conn_or_pool, "acquire"):
                    async with conn_or_pool.acquire() as conn:
                        total = await conn.fetchval(sum_query, record_id)
                        await conn.execute(update_query, float(total or 0.0), record_id)
                else:
                    total = await conn_or_pool.fetchval(sum_query, record_id)
                    await conn_or_pool.execute(update_query, float(total or 0.0), record_id)

                print(f"   💰 Total recalculado: {model_name}[{record_id}].amount_total = {total}")
            except Exception as e:
                print(f"   ⚠️ Error recalculando total para {model_name}[{record_id}]: {e}")

    except Exception as e:
        print(f"   ⚠️ _recalculate_totals_from_db error: {e}")


@router.post("/data/{model_name}/create")
async def create_data(
    model_name: str,
    vals: dict = Body(...),
    current_user_id: int = Depends(get_current_user),
):
    try:
        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                x2many_data, x2many_meta = extract_x2many_data(model_name, vals)
                safe_vals = _clean_m2o_payload(vals, model_name)

                if "id" in safe_vals and not safe_vals["id"]:
                    del safe_vals["id"]

                new_record = await env[model_name].create(safe_vals, context=session_graph)

                if x2many_data:
                    await process_nested_records(env, model_name, new_record, x2many_data, x2many_meta)

                storage = PostgresGraphStorage()
                id_mapping = await storage.save(session_graph)

                if str(new_record.id) in id_mapping:
                    new_record._id_val = id_mapping[str(new_record.id)]

                if x2many_data and str(new_record._id_val).isdigit():
                    await _recalculate_totals_from_db(new_record, model_name, storage)

                return {"status": "success", "data": await _serialize_record(env, new_record, model_name)}
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
    try:
        async with transaction():
            async with request_env(current_user_id) as (env, session_graph):
                records = env[model_name].browse([record_id], context=session_graph)
                if not records:
                    raise HTTPException(status_code=404, detail="Registro no encontrado")

                await records.load_data()

                x2many_data, x2many_meta = extract_x2many_data(model_name, vals)
                safe_vals = _clean_m2o_payload(vals, model_name)

                if "id" in safe_vals:
                    del safe_vals["id"]

                await records[0].write(safe_vals)

                if x2many_data:
                    await process_nested_records(env, model_name, records[0], x2many_data, x2many_meta)

                storage = PostgresGraphStorage()
                await storage.save(session_graph)

                if x2many_data:
                    await _recalculate_totals_from_db(records[0], model_name, storage)

                return {"status": "success", "data": await _serialize_record(env, records[0], model_name)}
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