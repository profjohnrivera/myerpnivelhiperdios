# backend/app/api/v1/auth.py
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.storage.postgres_storage import PostgresGraphStorage

router = APIRouter()


@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login rápido por SQL crudo, pero con normalización y validaciones fuertes.
    """
    username = (form_data.username or "").strip().lower()
    password = form_data.password or ""

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    storage = PostgresGraphStorage()
    conn_or_pool = await storage.get_connection()

    query = """
        SELECT *
        FROM "res_users"
        WHERE LOWER(TRIM(login)) = $1
          AND active = TRUE
        LIMIT 1
    """

    try:
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                row = await conn.fetchrow(query, username)
        else:
            row = await conn_or_pool.fetchrow(query, username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible validar credenciales en este momento",
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = dict(row)

    if "x_ext" in user_data and user_data["x_ext"]:
        extra = (
            json.loads(user_data["x_ext"])
            if isinstance(user_data["x_ext"], str)
            else dict(user_data["x_ext"])
        )
        user_data.update(extra)

    hashed_password = user_data.get("password") or ""
    if not await verify_password(password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    display_name = (
        user_data.get("name")
        or user_data.get("display_name")
        or user_data.get("login")
        or "Usuario"
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user_data["id"]),
            "name": display_name,
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "uid": user_data["id"],
        "name": display_name,
        "company_id": user_data.get("company_id"),
    }