# backend/app/api/v1/auth.py
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.storage.postgres_storage import PostgresGraphStorage
from datetime import timedelta

router = APIRouter()

@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 🚀 VELOCIDAD PURA: Buscamos en SQL crudo, saltando el ORM por completo.
    storage = PostgresGraphStorage()
    conn = await storage.get_connection()
    
    try:
        row = await conn.fetchrow(
            "SELECT * FROM res_users WHERE login = $1 AND active = True", 
            form_data.username
        )
    except Exception as e:
        row = None
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = dict(row)
    # Extraemos la data líquida donde inyectamos la contraseña
    if 'x_ext' in user_data and user_data['x_ext']:
        extra = json.loads(user_data['x_ext']) if isinstance(user_data['x_ext'], str) else dict(user_data['x_ext'])
        user_data.update(extra)
        
    hashed_password = user_data.get('password') or ''
    
    if not await verify_password(form_data.password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    display_name = user_data.get('name') or user_data.get('display_name') or user_data.get('login') or 'Admin'
        
    # GENERAR TOKEN DE INMORTALIDAD
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 💎 FIX: Guardamos el ID en el JWT (siempre como string por convención JWT)
    access_token = create_access_token(
        data={"sub": str(user_data['id']), "name": display_name}, 
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "uid": user_data['id'], # 💎 FIX: Retornamos el ID como entero nativo para la app
        "name": display_name
    }