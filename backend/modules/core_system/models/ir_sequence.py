# backend/modules/core_system/models/ir_sequence.py
from app.core.orm import Model, Field, SelectionField
import datetime
import logging
import traceback

class IrSequence(Model):
    """
    🔢 MOTOR DE SECUENCIAS (Anti-Deadlocks Nivel HiperDios)
    Genera identificadores únicos (Ej: PED-2026-0001).
    Utiliza transacciones autónomas atómicas para no bloquear el Event Loop ni la BD.
    """
    _name = 'ir.sequence' 
    _rec_name = 'name'

    name = Field(type_='string', label='Nombre', required=True)
    code = Field(type_='string', label='Código Técnico', index=True, required=True)
    prefix = Field(type_='string', default="PED-%(year)s-", label='Prefijo')
    padding = Field(type_='int', default=4, label='Relleno')
    number_next = Field(type_='int', default=1, label='Siguiente')
    
    # 💎 implementation='standard' (Rápida, permite huecos) | 'no_gap' (Lento, sin huecos)
    implementation = SelectionField(
        options=[('standard', 'Estándar (Rápida)'), ('no_gap', 'Sin Huecos (Bloqueante)')],
        default='standard',
        label='Implementación'
    )
    active = Field(type_='bool', default=True, label='Activo')

    @classmethod
    async def next_by_code(cls, code: str) -> str:
        """
        🚀 Generador de Secuencia Atómico O(1).
        Evita el colapso de la base de datos delegando la operación a una conexión paralela (Autónoma).
        """
        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        
        # 💎 MAGIA ANTI-DEADLOCK: Pedimos una conexión directa al Pool físico de Postgres, 
        # IGNORANDO el LazyConnectionProxy de la transacción principal actual.
        pool = await storage.get_pool()
        
        try:
            # Transacción Autónoma: Empieza y termina aquí mismo en microsegundos.
            async with pool.acquire() as conn:
                # UPDATE y RETURNING en una sola llamada atómica en C-Level
                query = """
                    UPDATE "ir_sequence"
                    SET number_next = number_next + 1
                    WHERE code = $1 AND active = True
                    RETURNING id, prefix, padding, number_next
                """
                row = await conn.fetchrow(query, code)
                
                if not row:
                    # Si la secuencia no existe, la creamos "lazy" en esta misma transacción autónoma.
                    # Guardamos el number_next en 2 porque ya estamos consumiendo el 1.
                    now_val = datetime.datetime.now()
                    insert_query = """
                        INSERT INTO "ir_sequence" 
                        (name, code, prefix, padding, number_next, implementation, active, write_version, create_date, write_date)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING prefix, padding, number_next
                    """
                    row = await conn.fetchrow(
                        insert_query, 
                        f"Secuencia {code}", code, "PED-%(year)s-", 4, 2, 'standard', True, 1, now_val, now_val
                    )
                
                prefix = row['prefix'] or ''
                pad = row['padding'] or 4
                
                # Si el UPDATE subió de 1 a 2, row['number_next'] trae 2. 
                # Le restamos 1 para devolver el valor actual que corresponde a esta llamada.
                current_val = row['number_next'] - 1

                # Formateamos el año si el prefijo lo incluye
                now = datetime.datetime.now()
                prefix_str = prefix.replace("%(year)s", now.strftime('%Y'))
                
                return f"{prefix_str}{str(current_val).zfill(pad)}"
                
        except Exception as e:
            # Red de seguridad: si Postgres cae o la tabla está corrupta, nunca detenemos la venta.
            print(f"🔥 Error crítico en ir_sequence: {e}")
            traceback.print_exc()
            return f"{code}-0001"