# backend/app/core/tree.py
from app.core.orm import Model, Field, RelationField
from app.core.registry import Registry
from app.core.env import Context

class TreeModel(Model):
    """
    🌳 MOTOR DE JERARQUÍAS (Materialized Path)
    Añade capacidades de árbol infinito a cualquier modelo mediante Metaprogramación.
    """
    _abstract = True

    # El path es estándar y universal
    parent_path = Field(type_='string', label='Vector de Ruta', index=True, readonly=True)

    # 💎 MAGIA METAPRÓGRAMÁTICA
    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, '_abstract', False):
            parent_field = RelationField(cls._name, label='Nodo Padre', ondelete='cascade')
            parent_field.name = 'parent_id'
            
            cls.parent_id = parent_field
            if hasattr(cls, '_fields'):
                cls._fields['parent_id'] = parent_field

    @classmethod
    async def create(cls, vals):
        record = await super().create(vals)
        
        if vals.get('parent_id'):
            graph = Context.get_graph()
            parent = cls(_id=vals['parent_id'], context=graph)
            p_path = getattr(parent, 'parent_path', '')
            
            # Fallback de seguridad por si el Grafo aún no ha cargado el path
            if not p_path:
                parents_db = await cls.search([('id', '=', vals['parent_id'])])
                if parents_db: p_path = parents_db[0].parent_path

            parent_path = f"{p_path}{record.id}/"
        else:
            parent_path = f"{record.id}/"
            
        await super(TreeModel, record).write({'parent_path': parent_path})
        return record

    async def write(self, vals):
        old_path = getattr(self, 'parent_path', '')
        
        if 'parent_id' in vals:
            new_parent_id = vals['parent_id']
            if new_parent_id:
                graph = Context.get_graph()
                TargetModel = Registry.get_model(self._name)
                new_parent = TargetModel(_id=new_parent_id, context=graph)
                
                p_path = getattr(new_parent, 'parent_path', '')
                if not p_path:
                    parents_db = await TargetModel.search([('id', '=', new_parent_id)])
                    if parents_db: p_path = parents_db[0].parent_path
                
                # REGLA ANTIMATRIX: No ser hijo de tu hijo
                if old_path and p_path.startswith(old_path):
                    raise ValueError(f"❌ Paradoja Espacio-Temporal: No puedes mover '{self.display_name}' dentro de su propia descendencia.")
                vals['parent_path'] = f"{p_path}{self.id}/"
            else:
                vals['parent_path'] = f"{self.id}/"

        # 1. Actualizamos el propio registro (Cabecera)
        await super().write(vals)

        # 🚀 CASCADA VECTORIZADA (Operación de Conjuntos SQL O(1))
        # Eliminamos el bucle FOR. Delegamos la matemática a PostgreSQL.
        if 'parent_path' in vals and old_path and old_path != vals['parent_path']:
            new_path = vals['parent_path']
            table_name = self._name.replace(".", "_")
            
            from app.core.storage.postgres_storage import PostgresGraphStorage
            storage = PostgresGraphStorage()
            conn_or_pool = await storage.get_connection()
            
            # MATEMÁTICA PURA:
            # En Postgres los strings empiezan en el índice 1.
            # Si old_path = '1/2/' (length 4) y la rama hija es '1/2/99/'.
            # start_pos = 5. SUBSTRING extrae '99/'. 
            # Luego concatenamos (||) con la nueva ruta ('5/2/') -> '5/2/99/'
            start_pos = len(old_path) + 1
            like_pattern = f"{old_path}%"
            
            query = f"""
                UPDATE "{table_name}" 
                SET parent_path = $1 || SUBSTRING(parent_path FROM $2)
                WHERE parent_path LIKE $3 AND id != $4
            """
            
            if hasattr(conn_or_pool, 'acquire'):
                async with conn_or_pool.acquire() as conn:
                    await conn.execute(query, new_path, start_pos, like_pattern, self.id)
            else:
                await conn_or_pool.execute(query, new_path, start_pos, like_pattern, self.id)
                
            # Limpiamos el caché distribuido para obligar a leer la nueva jerarquía
            from app.core.ormcache import ORMCache
            ORMCache.clear(self._name)