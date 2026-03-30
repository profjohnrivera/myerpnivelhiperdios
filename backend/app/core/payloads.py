# backend/app/core/payloads.py

from __future__ import annotations

import base64
import datetime
import decimal
from typing import Any, Dict, Iterable, Optional


_SKIP_CHANGE_FIELDS = {
    "write_version",
    "write_date",
    "write_uid",
    "create_date",
    "create_uid",
    "id",
}


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return repr(value)


def _normalize_decimal(value: decimal.Decimal) -> int | float:
    try:
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    except Exception:
        return float(value)


def _normalize_datetime(value: Any) -> str:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return _safe_str(value)


def _normalize_bytes(value: bytes | bytearray | memoryview) -> dict:
    raw = bytes(value)
    preview = base64.b64encode(raw[:48]).decode("ascii")
    return {
        "_type": "bytes",
        "length": len(raw),
        "preview_b64": preview,
        "truncated": len(raw) > 48,
    }


def _normalize_model_ref(value: Any) -> dict:
    model_name = None
    try:
        if hasattr(value, "_get_model_name"):
            model_name = value._get_model_name()
    except Exception:
        model_name = None

    res_id = getattr(value, "id", None)

    display_name = None
    try:
        display_name = getattr(value, "display_name", None)
    except Exception:
        display_name = None

    payload = {
        "_type": "record",
        "model": model_name or value.__class__.__name__,
        "id": int(res_id) if str(res_id).isdigit() else res_id,
    }

    if display_name:
        payload["display_name"] = display_name

    return payload


def _normalize_recordset(value: Any, *, depth: int, max_depth: int) -> dict:
    model_name = None
    try:
        if getattr(value, "_model_class", None):
            model_name = value._model_class._get_model_name()
    except Exception:
        model_name = None

    try:
        records = list(value)
    except Exception:
        records = []

    preview = [normalize_payload(r, depth=depth + 1, max_depth=max_depth) for r in records[:20]]

    return {
        "_type": "recordset",
        "model": model_name,
        "count": len(records),
        "preview": preview,
        "truncated": len(records) > 20,
    }


def normalize_payload(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    """
    Convierte cualquier valor a una forma JSON-safe y estable.

    Reglas:
    - primitives -> intactos
    - Decimal -> int/float
    - datetime/date -> ISO8601
    - bytes -> metadata compacta
    - record -> ref técnica {model, id, display_name}
    - recordset -> preview acotado
    - dict/list/set/tuple -> recursivo
    - objetos arbitrarios -> repr segura
    """
    if depth > max_depth:
        return {"_type": "max_depth", "repr": _safe_str(value)}

    if _is_primitive(value):
        return value

    if isinstance(value, decimal.Decimal):
        return _normalize_decimal(value)

    if isinstance(value, (datetime.datetime, datetime.date)):
        return _normalize_datetime(value)

    if isinstance(value, (bytes, bytearray, memoryview)):
        return _normalize_bytes(value)

    if isinstance(value, dict):
        normalized: Dict[str, Any] = {}
        for k, v in value.items():
            normalized[_safe_str(k)] = normalize_payload(v, depth=depth + 1, max_depth=max_depth)
        return normalized

    if isinstance(value, (list, tuple, set, frozenset)):
        return [normalize_payload(v, depth=depth + 1, max_depth=max_depth) for v in list(value)]

    # Recordset-like
    if hasattr(value, "_records") and hasattr(value, "_model_class"):
        return _normalize_recordset(value, depth=depth, max_depth=max_depth)

    # Record/model-like
    if hasattr(value, "id") and hasattr(value, "_get_model_name"):
        return _normalize_model_ref(value)

    return {
        "_type": value.__class__.__name__,
        "repr": _safe_str(value),
    }


def normalize_changes(
    changes: Optional[Dict[str, Any]],
    *,
    skip_fields: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Normaliza un payload de changes a:

        {
          "campo": {"old": ..., "new": ...}
        }

    Compatible con:
    - formato ya estructurado {"old": x, "new": y}
    - formato legacy {"campo": valor}
    """
    if not changes:
        return None

    skip = set(_SKIP_CHANGE_FIELDS)
    if skip_fields:
        skip.update(skip_fields)

    cleaned: Dict[str, Dict[str, Any]] = {}

    for field, value in changes.items():
        if field in skip:
            continue

        if isinstance(value, dict) and "old" in value and "new" in value:
            old_val = normalize_payload(value.get("old"))
            new_val = normalize_payload(value.get("new"))
            if old_val != new_val:
                cleaned[field] = {"old": old_val, "new": new_val}
        else:
            cleaned[field] = {
                "old": None,
                "new": normalize_payload(value),
            }

    return cleaned if cleaned else None