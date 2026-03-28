# backend/modules/core_system/models/ir_rule.py
import json
from typing import Union
from app.core.orm import Model, Field
from app.core.env import Context
from app.core.ormcache import ormcache # 💎 Importamos el nuevo motor de caché global

class IrRule(Model):
    """
    ⚖️ REGLAS DE SEGURIDAD (Row-Level Security / ir.rule)
    Define qué registros puede leer, escribir o borrar un usuario 
    inyectando dominios invisibles en el ORM.
    """
    _name = 'ir.rule'
    _rec_name = 'name'
    
    name = Field(type_='string', label='Nombre de la Regla', required=True)
    
    # Identificador del modelo sobre el que aplica la regla (ej: 'sale.order')
    model_name = Field(type_="string", label="Modelo Técnico", required=True, index=True)
    
    # El dominio en formato JSON: '[["create_uid", "=", "{user_id}"]]'
    domain_force = Field(type_='string', label='Dominio (JSON)', default="[]", required=True)
    
    # Flags de aplicación de la regla
    perm_read = Field(type_='bool', default=True, label='Aplica para Lectura')
    perm_write = Field(type_='bool', default=True, label='Aplica para Escritura')
    perm_create = Field(type_='bool', default=True, label='Aplica para Creación')
    perm_unlink = Field(type_='bool', default=True, label='Aplica para Eliminación')
    
    # Flag para activar/desactivar la regla sin borrarla
    active = Field(type_='bool', default=True, label='Activo')

    @classmethod
    @ormcache('ir.rule') # 🚀 ACELERADOR MÁXIMO: Caché Global con Invalidación vía Postgres
    async def get_domain(cls, target_model: str, user_id: Union[int, str]) -> list:
        """
        🛡️ MOTOR DE INTERCEPTACIÓN
        Busca las reglas activas para el modelo y las fusiona.
        Reemplaza la variable {user_id} dinámicamente en tiempo de ejecución.
        Con Caché Multi-Capa (Global y de Sesión) para evitar N+1 en la Base de Datos.
        """
        # 0. 🤖 PROCESOS INTERNOS: El sistema no tiene restricciones.
        if str(user_id) == 'system':
            return []

        env = Context.get_env()
        
        # 💎 CAPA 2: CACHÉ EN RAM NIVEL SESIÓN (Para acelerar aún más peticiones complejas locales)
        cache_key = f"rls_{target_model}_{user_id}"
        admin_cache_key = f"admin_{user_id}"

        if env and hasattr(env.graph, '_rls_cache') and cache_key in env.graph._rls_cache:
            return env.graph._rls_cache[cache_key]

        # 1. 👑 MODO DIOS: El Administrador Supremo tiene acceso absoluto.
        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        conn_or_pool = await storage.get_connection()
        
        is_admin = False
        if env and hasattr(env.graph, '_admin_cache') and admin_cache_key in env.graph._admin_cache:
            is_admin = env.graph._admin_cache[admin_cache_key]
        else:
            query = 'SELECT login FROM "res_users" WHERE id = $1'
            try:
                # 💎 FIX DEFINITIVO: Casteo seguro a Entero para no romper el BIGSERIAL de Postgres
                safe_uid = int(user_id) if str(user_id).isdigit() else user_id

                # Soporte seguro tanto para conexiones directas como para Pools
                if hasattr(conn_or_pool, 'acquire'):
                    async with conn_or_pool.acquire() as conn:
                        user_row = await conn.fetchrow(query, safe_uid)
                else:
                    user_row = await conn_or_pool.fetchrow(query, safe_uid)
                    
                if user_row and user_row['login'] == 'admin':
                    is_admin = True
            except Exception:
                pass # Silenciamos si recibimos tokens basura/antiguos del frontend
            
            # Guardamos si es admin en el grafo de esta sesión
            if env:
                if not hasattr(env.graph, '_admin_cache'): env.graph._admin_cache = {}
                env.graph._admin_cache[admin_cache_key] = is_admin

        if is_admin:
            if env:
                if not hasattr(env.graph, '_rls_cache'): env.graph._rls_cache = {}
                env.graph._rls_cache[cache_key] = []
            return []

        # 2. 🛡️ MORTALES: Buscamos las reglas activas aplicables al modelo y a la acción
        rules = await cls.search([
            ('model_name', '=', target_model),
            ('perm_read', '=', True),
            ('active', '=', True)
        ])
        
        combined_domain = []
        for rule in rules:
            df = rule.domain_force
            
            # Adaptabilidad: Manejo de tipos para asegurar la inyección de variables
            if isinstance(df, (list, dict)):
                df_str = json.dumps(df)
            else:
                df_str = str(df)

            # Inyección dinámica del ID del usuario actual en la regla
            raw_domain = df_str.replace("{user_id}", str(user_id))
            
            try:
                # Convertimos el string procesado en una lista real para el Domain Engine
                parsed_domain = json.loads(raw_domain)
                
                # Combinación de reglas restrictivas (AND implícito)
                if combined_domain:
                    combined_domain = ['&'] + combined_domain + parsed_domain
                else:
                    combined_domain = parsed_domain
            except Exception as e:
                print(f"🔥 Error parseando regla de seguridad '{rule.name}': {e}")
                
        # Guardamos el dominio final calculado en la caché de sesión
        if env:
            if not hasattr(env.graph, '_rls_cache'): env.graph._rls_cache = {}
            env.graph._rls_cache[cache_key] = combined_domain

        return combined_domain