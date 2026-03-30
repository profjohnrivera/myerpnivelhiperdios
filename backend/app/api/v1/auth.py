# backend/app/api/v1/auth.py
# ============================================================
# FIX CRÍTICO-3: Rate limiting en login con bloqueo progresivo.
# Sin dependencias externas (no SlowAPI, no Redis).
# Los contadores viven en x_ext de res_users.
#
# Comportamiento:
#   - 5 intentos fallidos → bloqueo de 15 minutos
#   - Login exitoso → resetea el contador
#   - Respuesta genérica (no revela si el usuario existe)
# ============================================================
import json
import datetime
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.storage.postgres_storage import PostgresGraphStorage

router = APIRouter()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_user_row(conn_or_pool, username: str):
    query = """
        SELECT id, login, password, active, company_id, name, partner_id, x_ext
        FROM "res_users"
        WHERE LOWER(TRIM(login)) = $1 AND active = TRUE
        LIMIT 1
    """
    try:
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                row = await conn.fetchrow(query, username)
        else:
            row = await conn_or_pool.fetchrow(query, username)
    except Exception:
        return None

    if not row:
        return None

    user_data = dict(row)
    if user_data.get("x_ext"):
        try:
            extra = json.loads(user_data["x_ext"]) if isinstance(user_data["x_ext"], str) else dict(user_data["x_ext"])
            for k, v in extra.items():
                if k not in user_data or user_data[k] is None:
                    user_data[k] = v
        except Exception:
            pass

    return user_data


async def _update_counters(conn_or_pool, user_id: int, success: bool):
    if success:
        sql = """
            UPDATE "res_users"
            SET x_ext = COALESCE(x_ext, '{}'::jsonb)
                || '{"failed_login_count": 0, "blocked_until": null}'::jsonb
            WHERE id = $1
        """
        try:
            if hasattr(conn_or_pool, "acquire"):
                async with conn_or_pool.acquire() as conn:
                    await conn.execute(sql, user_id)
            else:
                await conn_or_pool.execute(sql, user_id)
        except Exception:
            pass
        return

    # Fallido: obtener contador actual e incrementar
    check_sql = """
        SELECT COALESCE((x_ext->>'failed_login_count')::int, 0) AS count
        FROM "res_users" WHERE id = $1
    """
    try:
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                row = await conn.fetchrow(check_sql, user_id)
        else:
            row = await conn_or_pool.fetchrow(check_sql, user_id)
        current_count = row["count"] if row else 0
    except Exception:
        current_count = 0

    new_count = current_count + 1
    blocked_until_val = None

    if new_count >= MAX_FAILED_ATTEMPTS:
        blocked_until_val = (_utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()

    new_ext = json.dumps({
        "failed_login_count": new_count,
        "blocked_until": blocked_until_val,
    })

    update_sql = """
        UPDATE "res_users"
        SET x_ext = COALESCE(x_ext, '{}'::jsonb) || $2::jsonb
        WHERE id = $1
    """
    try:
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                await conn.execute(update_sql, user_id, new_ext)
        else:
            await conn_or_pool.execute(update_sql, user_id, new_ext)
    except Exception as e:
        print(f"⚠️ [AUTH] Error actualizando contadores: {e}")


def _check_blocked(user_data: dict):
    blocked_until_str = user_data.get("blocked_until")
    if not blocked_until_str:
        return
    try:
        blocked_until = datetime.datetime.fromisoformat(str(blocked_until_str))
        now = _utcnow()
        if blocked_until > now:
            minutes_left = int((blocked_until - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Cuenta bloqueada por demasiados intentos. "
                    f"Intenta en {minutes_left} minuto(s)."
                ),
                headers={"Retry-After": str(minutes_left * 60)},
            )
    except HTTPException:
        raise
    except Exception:
        pass


@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    username = (form_data.username or "").strip().lower()
    password = form_data.password or ""

    _WRONG = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not username or not password:
        raise _WRONG

    storage = PostgresGraphStorage()
    conn_or_pool = await storage.get_connection()

    user_data = await _get_user_row(conn_or_pool, username)
    if not user_data:
        raise _WRONG

    user_id = user_data["id"]

    # Verificar bloqueo
    _check_blocked(user_data)

    hashed_password = user_data.get("password") or ""
    if not hashed_password:
        await _update_counters(conn_or_pool, user_id, success=False)
        raise _WRONG

    if not await verify_password(password, hashed_password):
        await _update_counters(conn_or_pool, user_id, success=False)
        # Re-leer para ver si el último intento activó el bloqueo
        refreshed = await _get_user_row(conn_or_pool, username)
        if refreshed:
            _check_blocked(refreshed)
        raise _WRONG

    # Éxito: resetear contadores
    await _update_counters(conn_or_pool, user_id, success=True)

    display_name = user_data.get("name") or user_data.get("login") or "Usuario"

    access_token = create_access_token(
        data={"sub": str(user_id), "name": display_name},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "uid": user_id,
        "name": display_name,
        "company_id": user_data.get("company_id"),
    }