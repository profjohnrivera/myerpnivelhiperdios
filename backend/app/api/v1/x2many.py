# backend/app/api/v1/x2many.py

from app.core.registry import Registry
from app.core.env import env_scope
from app.core.storage.postgres_storage import PostgresGraphStorage

from .serializers import _find_inverse_field


def extract_x2many_data(model_name: str, vals: dict):
    x2many_data, x2many_meta = {}, {}
    model_cls = Registry.get_model(model_name)

    for fname in list(vals.keys()):
        attr = getattr(model_cls, fname, None)
        if hasattr(attr, "get_meta"):
            meta = attr.get_meta()
            if meta.get("type") == "one2many":
                x2many_data[fname] = vals.pop(fname)
                meta["target"] = getattr(attr, "related_model", None) or meta.get("target")
                x2many_meta[fname] = meta

    return x2many_data, x2many_meta


async def process_nested_records(env, parent_model_name: str, parent_record, x2many_data: dict, x2many_meta: dict):
    """
    Guarda registros hijo (One2Many) del padre en scope sudo para respetar
    la frontera de seguridad del documento padre.
    """
    storage = PostgresGraphStorage()
    session_graph = parent_record.graph
    sudo_env = env.sudo()

    for fname, items in x2many_data.items():
        meta = x2many_meta.get(fname, {})
        target_model_name = meta.get("target")
        if not target_model_name:
            continue

        target_model = sudo_env[target_model_name]
        inverse_field = _find_inverse_field(target_model_name, parent_model_name, fname)
        valid_fields = [
            f for f in dir(target_model)
            if hasattr(getattr(target_model, f, None), "get_meta")
        ]

        existing_recs = await storage.search_domain(
            target_model_name,
            [(inverse_field, "=", parent_record.id)],
            check_access=False,
        )
        existing_ids = set(existing_recs)
        incoming_ids = {
            int(i.get("id")) for i in items
            if isinstance(i, dict) and i.get("id") and str(i.get("id")).isdigit()
        }

        async with env_scope(sudo_env):
            for del_id in (existing_ids - incoming_ids):
                child = target_model.browse([del_id], context=session_graph)
                if child:
                    await child.load_data()
                    await child[0].unlink()

        final_child_ids = []

        async with env_scope(sudo_env):
            for item in items:
                if not isinstance(item, dict):
                    continue

                for k, v in list(item.items()):
                    if isinstance(v, list) and len(v) >= 2:
                        clean_id = v[0]
                        item[k] = int(clean_id) if str(clean_id).isdigit() else clean_id
                    elif k.endswith("_id") and isinstance(v, (int, float, str)):
                        item[k] = int(v) if str(v).isdigit() else v

                product_val = item.get("product_id")
                if product_val and isinstance(product_val, str) and not str(product_val).isdigit():
                    item["product_id"] = None

                try:
                    item["product_uom_qty"] = float(item.get("product_uom_qty") or 1.0)
                except Exception:
                    item["product_uom_qty"] = 1.0

                try:
                    item["price_unit"] = float(item.get("price_unit") or 0.0)
                except Exception:
                    item["price_unit"] = 0.0

                item_id = item.pop("id", None)
                item.pop("isNew", None)

                clean_item = {k: v for k, v in item.items() if k in valid_fields}
                clean_item[inverse_field] = parent_record.id

                if item_id and str(item_id).isdigit():
                    child = target_model.browse([int(item_id)], context=session_graph)
                    if child:
                        await child.load_data()
                        await child[0].write(clean_item)
                        final_child_ids.append(int(item_id))
                else:
                    new_child = await target_model.create(clean_item, context=session_graph)
                    final_child_ids.append(new_child.id)

        setattr(parent_record, fname, final_child_ids)