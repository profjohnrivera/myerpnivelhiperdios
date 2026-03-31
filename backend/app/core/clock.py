# backend/app/core/clock.py

from __future__ import annotations

from datetime import datetime, timezone, date


def utc_now_aware() -> datetime:
    """
    Fuente canónica de tiempo técnico del backend.
    Devuelve datetime aware en UTC.
    """
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """
    Devuelve UTC naive compatible con columnas Postgres TIMESTAMP
    que este backend persiste sin tzinfo.
    """
    return utc_now_aware().replace(tzinfo=None)


def utc_now_iso() -> str:
    """
    ISO8601 del timestamp UTC naive canónico del backend.
    """
    return utc_now_naive().isoformat()


def utc_today() -> date:
    """
    Fecha UTC canónica del sistema.
    """
    return utc_now_aware().date()