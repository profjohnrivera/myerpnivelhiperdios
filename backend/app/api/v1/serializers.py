# backend/app/api/v1/serializers.py

from typing import Any, Dict, List

from app.core.registry import Registry


def _find_inverse_field(child_model_name: str, parent_model_name: str, parent_field_name: str | None = None) -> str:
    """
    Se conserva por compatibilidad con otros módulos/helpers.
    La verdad de lectura ya no vive aquí.
    """
    if parent_field_name:
        parent_cls = Registry.get_model(parent_model_name)
        parent_attr = getattr(parent_cls, parent_field_name, None)
        if parent_attr and hasattr(parent_attr, "inverse_name") and parent_attr.inverse_name:
            return parent_attr.inverse_name

    child_cls = Registry.get_model(child_model_name)
    for fname in dir(child_cls):
        attr = getattr(child_cls, fname, None)
        if hasattr(attr, "get_meta"):
            meta = attr.get_meta()
            if meta.get("type") in ("relation", "many2one"):
                target = getattr(attr, "related_model", "") or meta.get("target", "")
                if Registry._resolve_name(str(target)) == parent_model_name:
                    return fname

    return parent_model_name.split(".")[-1] + "_id"


async def _serialize_records(env, records, model_name: str, fields: List[str] | None = None) -> List[dict]:
    """
    P1-B:
    serializers.py deja de ser un segundo motor de lectura.
    Toda la materialización se delega a Recordset.read().
    """
    if not records:
        return []

    try:
        if hasattr(records, "read"):
            return await records.read(fields=fields)
    except Exception:
        pass

    if not hasattr(records, "__iter__"):
        records = [records]

    records = list(records)
    if not records:
        return []

    model_cls = Registry.get_model(model_name)

    try:
        from app.core.orm.recordset import Recordset
    except Exception:
        Recordset = None

    if Recordset is not None:
        rs = Recordset(model_cls, records, env)
        return await rs.read(fields=fields)

    return []


async def _serialize_record(env, record, model_name: str) -> dict:
    """
    Serializa un solo registro.

    Casos:
    - persistido -> delega a Recordset.read()
    - virtual/new -> serializa desde graph/defaults sin tocar BD
    """
    if record is None:
        return {}

    if str(getattr(record, "id", "")).isdigit():
        results = await _serialize_records(env, [record], model_name)
        return results[0] if results else {}

    model_cls = Registry.get_model(model_name)
    result: Dict[str, Any] = {"id": getattr(record, "id", None)}

    for fname in dir(model_cls):
        attr = getattr(model_cls, fname, None)
        if not hasattr(attr, "get_meta"):
            continue

        try:
            value = getattr(record, fname)
        except Exception:
            value = None

        meta = attr.get_meta()
        ftype = meta.get("type")

        if ftype in ("relation", "many2one"):
            if value and hasattr(value, "id"):
                result[fname] = [value.id, getattr(value, "display_name", None) or str(value.id)]
            elif value:
                result[fname] = value
            else:
                result[fname] = False

        elif ftype == "one2many":
            child_payload = []
            try:
                if value and hasattr(value, "__iter__"):
                    for child in list(value):
                        child_payload.append(await _serialize_record(env, child, attr.related_model))
            except Exception:
                child_payload = []
            result[fname] = child_payload

        elif ftype == "many2many":
            tags = []
            try:
                if value and hasattr(value, "__iter__"):
                    for item in list(value):
                        if hasattr(item, "id"):
                            tag = {
                                "id": item.id,
                                "name": getattr(item, "display_name", None) or getattr(item, "name", None) or str(item.id),
                            }
                            if hasattr(item, "color"):
                                try:
                                    tag["color"] = getattr(item, "color")
                                except Exception:
                                    pass
                            tags.append(tag)
            except Exception:
                tags = []
            result[fname] = tags

        else:
            result[fname] = value

    result["display_name"] = (
        result.get("name")
        or result.get("display_name")
        or f"{model_name}({getattr(record, 'id', 'new')})"
    )

    return result


def _clean_m2o_payload(vals: dict, model_name: str | None = None) -> dict:
    """
    Limpia el payload del frontend:

    - Many2One [id, "nombre"] -> id
    - Many2Many [1,2] o [{id:1}] -> lista de IDs
    - *_id escalares -> entero
    - listas de dicts (one2many) -> limpieza recursiva de hijos
    - elimina campos de presentación/runtime que no pertenecen al dominio
    """
    forbidden_keys = {
        "display_name",
        "__typename",
        "_virtual",
        "_label",
        "_meta",
    }

    m2m_field_names = set()

    if model_name:
        try:
            model_cls = Registry.get_model(model_name)
            for fname in dir(model_cls):
                attr = getattr(model_cls, fname, None)
                if hasattr(attr, "get_meta") and attr.get_meta().get("type") == "many2many":
                    m2m_field_names.add(fname)
        except Exception:
            pass

    def _clean_nested(value):
        if isinstance(value, dict):
            cleaned = {}
            for nk, nv in value.items():
                if nk in forbidden_keys:
                    continue

                if nk == "id":
                    cleaned[nk] = nv
                    continue

                if isinstance(nv, list) and nv and isinstance(nv[0], dict):
                    cleaned[nk] = [_clean_nested(item) for item in nv]

                elif isinstance(nv, list) and len(nv) >= 1 and not isinstance(nv[0], dict):
                    clean_id = nv[0]
                    cleaned[nk] = int(clean_id) if str(clean_id).isdigit() else clean_id

                elif nk.endswith("_id") and isinstance(nv, (int, float, str)):
                    cleaned[nk] = int(nv) if str(nv).isdigit() else nv

                else:
                    cleaned[nk] = _clean_nested(nv)

            return cleaned

        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                return [_clean_nested(item) for item in value]
            return value

        return value

    safe_vals: dict = {}

    for k, v in vals.items():
        if k == "id":
            continue

        if k in forbidden_keys:
            continue

        if k in m2m_field_names:
            if isinstance(v, list):
                clean = []
                for item in v:
                    if isinstance(item, dict):
                        _id = item.get("id")
                        if _id is not None and str(_id).isdigit():
                            clean.append(int(_id))
                    elif str(item).isdigit():
                        clean.append(int(item))
                safe_vals[k] = clean
            else:
                safe_vals[k] = v

        elif isinstance(v, list) and v and isinstance(v[0], dict):
            safe_vals[k] = [_clean_nested(item) for item in v]

        elif isinstance(v, list) and len(v) >= 2:
            clean_id = v[0]
            safe_vals[k] = int(clean_id) if str(clean_id).isdigit() else clean_id

        elif k.endswith("_id") and isinstance(v, (int, float, str)):
            safe_vals[k] = int(v) if str(v).isdigit() else v

        elif isinstance(v, dict):
            safe_vals[k] = _clean_nested(v)

        else:
            safe_vals[k] = v

    return safe_vals