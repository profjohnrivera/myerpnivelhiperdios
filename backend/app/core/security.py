# backend/app/core/security.py
import jwt
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Union
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# --- CONFIGURACIÓN DE CRIPTOGRAFÍA NIVEL ENTERPRISE ---
pwd_context = CryptContext(
    schemes=["pbkdf2_sha512", "bcrypt"],
    deprecated="auto",
    pbkdf2_sha512__rounds=300_000 
)

async def hash_password(password: str) -> str:
    """
    Convierte una contraseña plana en un hash irreversible.
    Ej: 'admin' -> '$pbkdf2-sha512$...'
    Ejecución delegada a ThreadPool para no asfixiar el Event Loop.
    """
    return await asyncio.to_thread(pwd_context.hash, password)

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña plana coincide con el hash guardado.
    Devuelve True o False de forma SEGURA.
    Ejecución delegada a ThreadPool.
    """
    if not hashed_password:
        return False
        
    try:
        # 🛡️ FIX HiperDios: Offloading del cálculo pesado de CPU
        return await asyncio.to_thread(pwd_context.verify, plain_password, hashed_password)
    except Exception as e:
        print(f"🛡️ [SECURITY SHIELD] Intento de login bloqueado por Hash inválido o texto plano.")
        return False

# --- CONFIGURACIÓN JWT (El Candado de la API) ---
SECRET_KEY = "HIPERDIOS_ULTRA_SECRET_KEY_100_YEARS_VIGENCY" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 días de sesión activa

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Empaqueta el ID del usuario en un token encriptado que viaja al frontend.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Union[int, str]:
    """
    MIDDLEWARE DE SEGURIDAD: 
    Intercepta cada petición a la API, decodifica el token y devuelve el ID real del usuario.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 🚀 Operación I/O rápida, el decode de JWT es suficientemente ligero para el hilo principal
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        # 💎 FIX: Si el Token trae un ID numérico, lo convertimos a entero para el Backend
        user_id = int(user_id_str) if str(user_id_str).isdigit() else user_id_str
            
    except jwt.PyJWTError:
        raise credentials_exception
        
    return user_id