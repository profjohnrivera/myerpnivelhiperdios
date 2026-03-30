# backend/app/core/security.py
import os
import jwt
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


# --- CONFIGURACIÓN DE CRIPTOGRAFÍA NIVEL ENTERPRISE ---
pwd_context = CryptContext(
    schemes=["pbkdf2_sha512", "bcrypt"],
    deprecated="auto",
    pbkdf2_sha512__rounds=300_000,
)


def is_password_hash(value: Optional[str]) -> bool:
    """
    Detecta si el valor ya parece un hash soportado por passlib.
    Evita re-hashear un hash ya existente.
    """
    if not value or not isinstance(value, str):
        return False
    try:
        return pwd_context.identify(value) is not None
    except Exception:
        return False


async def hash_password(password: str) -> str:
    """
    Convierte una contraseña plana en un hash irreversible.
    Usa asyncio.to_thread para no bloquear el event loop
    (pbkdf2_sha512 con 300k rounds es CPU-intensivo).
    """
    if password is None:
        raise ValueError("No se puede hashear una contraseña vacía.")
    return await asyncio.to_thread(pwd_context.hash, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña plana coincide con el hash guardado.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return await asyncio.to_thread(pwd_context.verify, plain_password, hashed_password)
    except Exception:
        print("🛡️ [SECURITY SHIELD] Intento de login bloqueado por hash inválido o texto plano.")
        return False


# --- CONFIGURACIÓN JWT ---
SECRET_KEY = os.getenv("ERP_SECRET_KEY", "DEV_ONLY_CHANGE_ME_HIPERDIOS")
ALGORITHM = os.getenv("ERP_JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ERP_ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Empaqueta el ID del usuario en un token JWT firmado.
    """
    to_encode = data.copy()

    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])

    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Union[int, str]:
    """
    MIDDLEWARE DE SEGURIDAD:
    Decodifica el token JWT y devuelve el ID real del usuario.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        user_id = int(user_id_str) if str(user_id_str).isdigit() else user_id_str
    except jwt.PyJWTError:
        raise credentials_exception

    return user_id