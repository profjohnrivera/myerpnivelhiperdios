# backend/app/core/orm.py
from typing import Any, Dict, List, Optional, Type, Callable, Union
import datetime
import decimal  
import uuid
import re
import asyncio
import json
from app.core.graph import Graph
from app.core.env import Context, Env
from app.core.event_bus import EventBus
from app.core.decorators import action
from app.core.ormcache import ormcache

# =========================================================================
# 🛡️ UNIT OF WORK: ROLLBACK IN-MEMORY & SQL SAVEPOINTS
# =========================================================================
class AsyncGraphSavepoint:
    """
    💎 MEMENTO PATTERN + SQL SAVEPOINT
    Garantiza consistencia absoluta. Si hay error, revierte la RAM y 
    deshace la sub-transacción de Postgres para no bloquear conexiones.
    """
    def __init__(self, env: Env):
        self.env = env
        self.graph = env.graph if env else Context.get_graph()
        self._snap_vals = None
        self._snap_vers = None
        self._snap_dirty = None
        self.db_transaction = None

    def _clone_storage(self, storage_obj):
        if storage_obj is None: return {}
        if hasattr(storage_obj, 'copy'): return storage_obj.copy()
        if hasattr(storage_obj, 'items'): return {k: v for k, v in storage_obj.items()}
        elif hasattr(storage_obj, 'cache'): return storage_obj.cache.copy()
        return dict(storage_obj)

    async def __aenter__(self):
        self._snap_vals = self._clone_storage(getattr(self.graph, '_values', None))
        self._snap_vers = self._clone_storage(getattr(self.graph, '_versions', None))
        dirty = getattr(self.graph, '_dirty_nodes', None)
        self._snap_dirty = dirty.copy() if hasattr(dirty, 'copy') else set(dirty) if dirty else set()
        
        from app.core.transaction import transaction_conn
        conn = transaction_conn.get()
        if conn and hasattr(conn, 'transaction'):
            self.db_transaction = conn.transaction()
            await self.db_transaction.start()
            
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self.db_transaction:
                await self.db_transaction.rollback()
                
            if hasattr(self.graph, '_values'):
                v_store = self.graph._values
                if hasattr(v_store, 'clear'): v_store.clear()
                for k, v in self._snap_vals.items(): v_store[k] = v

            if hasattr(self.graph, '_versions'):
                ver_store = self.graph._versions
                if hasattr(ver_store, 'clear'): ver_store.clear()
                for k, v in self._snap_vers.items(): ver_store[k] = v

            if hasattr(self.graph, '_dirty_nodes'):
                self.graph._dirty_nodes = self._snap_dirty.copy() if hasattr(self._snap_dirty, 'copy') else set(self._snap_dirty)
        else:
            if self.db_transaction:
                await self.db_transaction.commit()


class Recordset:
    def __init__(self, model_class: Type, records: List[Any], env: Optional[Env] = None):
        self._model_class = model_class
        self._records = records
        self._env = env or Context.get_env()

    def __iter__(self): return iter(self._records)
    def __len__(self): return len(self._records)
    def __bool__(self): return bool(self._records)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Recordset(self._model_class, self._records[index], self._env)
        return self._records[index]

    def sudo(self):
        sudo_env = self._env.sudo() if self._env else Env(su=True)
        return Recordset(self._model_class, self._records, sudo_env)

    async def _run_computes(self):
        if not self._records: return
        
        computes = {}
        for attr_name in dir(self._model_class):
            attr = getattr(self._model_class, attr_name, None)
            if isinstance(attr, ComputedField):
                computes[attr_name] = attr
                
        if not computes: return

        visited = set()
        temp_mark = set()
        ordered = []

        def visit(node):
            if node in temp_mark: return
            if node not in visited:
                temp_mark.add(node)
                attr = computes.get(node)
                if attr and getattr(attr, 'depends_on', None):
                    for dep in attr.depends_on:
                        dep_base = dep.split('.')[0]
                        if dep_base in computes:
                            visit(dep_base)
                temp_mark.remove(node)
                visited.add(node)
                ordered.append(node)

        for node in computes.keys():
            visit(node)

        for attr_name in ordered:
            attr = computes[attr_name]
            if asyncio.iscoroutinefunction(attr.func): await attr.func(self)
            else: attr.func(self)

    async def _check_access(self) -> None:
        if not self._records: return
        env = self._env or Context.get_env()
        if not env or getattr(env, 'su', False): return
        
        model_name = self._model_class._get_model_name()
        if model_name in ['ir.rule', 'ir.model', 'ir.model.fields', 'res.users', 'ir.sequence']: return
        
        from app.core.registry import Registry
        IrRuleModel = Registry.get_model('ir.rule')
        if not IrRuleModel: return
        
        user_domain = await IrRuleModel.get_domain(model_name, env.uid)
        if not user_domain: return 
        
        ids = [r.id for r in self._records if str(r.id).isdigit()]
        if not ids: return

        allowed_records = await self._model_class.search(['&', ('id', 'in', ids)] + user_domain)
        
        if len(allowed_records) != len(ids):
            raise PermissionError(f"🛑 [SECURITY BLOCK] Intento de vulneración de acceso en bloque al modelo {model_name}. Acceso Denegado.")

    async def load_data(self) -> 'Recordset':
        if not self._records: return self
        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        conn = await storage.get_connection()
        
        model_name = self._model_class._get_model_name()
        table_name = model_name.replace('.', '_')
        
        ids = [r.id for r in self._records if str(r.id).isdigit()]
        if not ids: return self

        try:
            query = f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])'
            rows = await conn.fetch(query, ids)
            dirty_nodes = getattr(self._env.graph, '_dirty_nodes', set())
            
            for row in rows:
                row_id = row['id']
                for k, v in row.items():
                    if k == 'x_ext' and v:
                        extra = v if isinstance(v, dict) else (json.loads(v) if isinstance(v, str) else dict(v))
                        for ek, ev in extra.items():
                            node_name = (model_name, row_id, ek) 
                            if node_name not in dirty_nodes:
                                self._env.graph._values[node_name] = ev
                    else:
                        parsed_v = storage._parse_db_value(v) if hasattr(storage, '_parse_db_value') else v
                        node_name = (model_name, row_id, k) 
                        if node_name not in dirty_nodes:
                            self._env.graph._values[node_name] = parsed_v
        except Exception as e:
            print(f"⚠️ Error en Bulk Load de {model_name}: {e}")
            
        return self

    async def prefetch_related(self, fields: List[str]) -> 'Recordset':
        if not self._records: return self
        await self.load_data()
        
        from app.core.registry import Registry
        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        conn = await storage.get_connection()

        for path in fields:
            parts = path.split('.')
            current_rs = self

            for part in parts:
                if not current_rs: break
                
                model_cls = current_rs._model_class
                attr = getattr(model_cls, part, None)
                if not attr or not hasattr(attr, 'get_meta'): break
                
                meta = attr.get_meta()
                f_type = meta.get('type')
                target_model_name = getattr(attr, 'related_model', None) or meta.get('target')
                if not target_model_name: break
                
                TargetModel = Registry.get_model(target_model_name)
                target_table = target_model_name.replace('.', '_')
                
                next_rs_records = []

                if f_type in ['relation', 'many2one']:
                    target_ids = set()
                    for rec in current_rs:
                        val = rec.graph.get(rec._get_node_name(part))
                        if val is None and hasattr(rec, '_id_val'):
                            val = getattr(rec, part, None)
                            
                        if val and hasattr(val, 'id'): target_ids.add(str(val.id))
                        elif val and isinstance(val, list): target_ids.add(str(val[0]))
                        elif val and isinstance(val, str): target_ids.add(val)
                        elif val and isinstance(val, int): target_ids.add(str(val))

                    target_ids = list(filter(None, target_ids))
                    target_int_ids = [int(i) for i in target_ids if str(i).isdigit()]

                    if target_int_ids:
                        query = f'SELECT * FROM "{target_table}" WHERE id = ANY($1::bigint[])'
                        rows = await conn.fetch(query, target_int_ids)
                        dirty_nodes = getattr(self._env.graph, '_dirty_nodes', set())
                        for row in rows:
                            row_id = row['id']
                            next_rs_records.append(TargetModel(_id=row_id, context=self._env.graph))
                            for k, v in row.items():
                                if k == 'x_ext' and v:
                                    extra = v if isinstance(v, dict) else (json.loads(v) if isinstance(v, str) else dict(v))
                                    for ek, ev in extra.items():
                                        node_name = (target_model_name, row_id, ek)
                                        if node_name not in dirty_nodes:
                                            self._env.graph._values[node_name] = ev
                                else:
                                    parsed_v = storage._parse_db_value(v) if hasattr(storage, '_parse_db_value') else v
                                    node_name = (target_model_name, row_id, k)
                                    if node_name not in dirty_nodes:
                                        self._env.graph._values[node_name] = parsed_v

                elif f_type == 'one2many':
                    inverse = attr.inverse_name or f"{model_cls._get_model_name().split('.')[-1]}_id"
                    parent_ids = [r.id for r in current_rs if str(r.id).isdigit()]
                    
                    if parent_ids:
                        query = f'SELECT * FROM "{target_table}" WHERE "{inverse}" = ANY($1::bigint[])'
                        rows = await conn.fetch(query, parent_ids)
                        
                        grouped = {pid: [] for pid in parent_ids}
                        dirty_nodes = getattr(self._env.graph, '_dirty_nodes', set())
                        for row in rows:
                            row_id = row['id']
                            p_id = row[inverse]
                            if p_id in grouped: grouped[p_id].append(row_id)
                            next_rs_records.append(TargetModel(_id=row_id, context=self._env.graph))
                            
                            for k, v in row.items():
                                if k == 'x_ext' and v:
                                    extra = v if isinstance(v, dict) else (json.loads(v) if isinstance(v, str) else dict(v))
                                    for ek, ev in extra.items():
                                        node_name = (target_model_name, row_id, ek)
                                        if node_name not in dirty_nodes:
                                            self._env.graph._values[node_name] = ev
                                else:
                                    parsed_v = storage._parse_db_value(v) if hasattr(storage, '_parse_db_value') else v
                                    node_name = (target_model_name, row_id, k)
                                    if node_name not in dirty_nodes:
                                        self._env.graph._values[node_name] = parsed_v
                        
                        for rec in current_rs:
                            if not str(rec.id).isdigit(): continue
                            children_ids = grouped.get(rec.id, [])
                            children_instances = [TargetModel(_id=cid, context=self._env.graph) for cid in children_ids]
                            rec.graph.set_fact(("virtual", rec._get_model_name(), rec.id, part), children_instances)
                            rec.graph.set_fact(rec._get_node_name(part), children_ids)

                current_rs = Recordset(TargetModel, next_rs_records, self._env)
                
        return self

    async def read(self, fields: List[str] = None) -> List[Dict[str, Any]]:
        await self._check_access()
        if not self._records: return []

        from app.core.registry import Registry
        from app.core.storage.postgres_storage import PostgresGraphStorage

        storage = PostgresGraphStorage()
        conn = await storage.get_connection()

        model_name = self._model_class._get_model_name()
        table_name = model_name.replace('.', '_')
        ids = [r.id for r in self._records if str(r.id).isdigit()]

        if not ids: return []

        query = f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])'
        rows = await conn.fetch(query, ids)
        
        db_data = {row['id']: dict(row) for row in rows}
        
        m2o_fields = {}
        o2m_fields = {}
        
        for name in dir(self._model_class):
            if fields and name not in fields and name != 'id': continue
            attr = getattr(self._model_class, name, None)
            if hasattr(attr, 'get_meta'):
                meta = attr.get_meta()
                f_type = meta.get('type')
                if f_type in ['relation', 'many2one']:
                    t_model = getattr(attr, 'related_model', None) or meta.get('target')
                    if t_model: m2o_fields[name] = t_model
                elif f_type == 'one2many':
                    t_model = attr.related_model
                    inv_name = attr.inverse_name or f"{model_name.split('.')[-1]}_id"
                    o2m_fields[name] = (t_model, inv_name)

        m2o_cache = {} 
        for f_name, t_model in m2o_fields.items():
            t_table = t_model.replace('.', '_')
            target_ids = list({db_data[rid][f_name] for rid in ids if db_data.get(rid) and db_data[rid].get(f_name)})
            target_int_ids = [int(x) for x in target_ids if str(x).isdigit()]
            
            if target_int_ids:
                try:
                    m2o_query = f'SELECT id, name, display_name FROM "{t_table}" WHERE id = ANY($1::bigint[])'
                    m2o_rows = await conn.fetch(m2o_query, target_int_ids)
                    m2o_cache[t_model] = {
                        r['id']: [r['id'], r.get('name') or r.get('display_name') or str(r['id'])] 
                        for r in m2o_rows
                    }
                except Exception: m2o_cache[t_model] = {}

        o2m_cache = {}
        for f_name, (t_model, inv_name) in o2m_fields.items():
            t_table = t_model.replace('.', '_')
            try:
                o2m_query = f'SELECT * FROM "{t_table}" WHERE "{inv_name}" = ANY($1::bigint[])'
                o2m_rows = await conn.fetch(o2m_query, ids)
                
                grouped = {rid: [] for rid in ids}
                for r in o2m_rows:
                    p_id = r[inv_name]
                    if p_id in grouped:
                        c_dict = {k: v for k, v in dict(r).items() if not isinstance(v, (list, dict))}
                        c_dict['id'] = r['id']
                        grouped[p_id].append(c_dict)
                o2m_cache[f_name] = grouped
            except Exception: o2m_cache[f_name] = {rid: [] for rid in ids}

        env = self._env
        lang = getattr(env, 'lang', 'en_US') if env else 'en_US'
        results = []

        for rec in self._records:
            if not str(rec.id).isdigit(): continue
            rec_id = rec.id
            if rec_id not in db_data: continue
            row = db_data[rec_id]
            res = {'id': rec_id}
            
            for f_name in dir(self._model_class):
                if fields and f_name not in fields and f_name != 'id': continue
                attr = getattr(self._model_class, f_name, None)
                if not hasattr(attr, 'get_meta'): continue
                
                meta = attr.get_meta()
                f_type = meta.get('type')
                
                if f_type in ['relation', 'many2one']:
                    val = row.get(f_name)
                    if val and m2o_fields.get(f_name) in m2o_cache:
                        res[f_name] = m2o_cache[m2o_fields[f_name]].get(val, val)
                    else: res[f_name] = False
                
                elif f_type == 'one2many':
                    res[f_name] = o2m_cache.get(f_name, {}).get(rec_id, [])
                    
                else:
                    val = row.get(f_name)
                    if meta.get('translate') and isinstance(val, dict):
                        val = val.get(lang, list(val.values())[0] if val else "")
                    
                    if isinstance(val, decimal.Decimal): res[f_name] = float(val)
                    elif isinstance(val, datetime.datetime): res[f_name] = val.isoformat()
                    else: res[f_name] = val
                    
            res['display_name'] = res.get('name') or res.get('display_name') or f"{model_name}({rec_id})"
            results.append(res)

        return results

    # =========================================================================
    # ⚡ BATCH PROCESSING CON ROLLBACK IN-MEMORY & SQL (ANTI-CONCURRENCY)
    # =========================================================================
    async def write(self, vals: Dict[str, Any]) -> bool:
        if not self._records: return True
        await self._check_access()
        
        env = self._env or Context.get_env()
        model_name = self._model_class._get_model_name()

        async with AsyncGraphSavepoint(env):
            
            # 🛡️ FIX HIPERDIOS: Si `vals` está vacío, es un recálculo interno del motor. 
            # Ignoramos la restricción universal de 'done' / 'cancel' para permitir la consistencia.
            if vals and 'state' not in vals and not (env and getattr(env, 'su', False)):
                for rec in self._records:
                    if hasattr(rec, 'state'):
                        current_state = getattr(rec, "state", None)
                        if current_state in ['done', 'cancel']:
                            raise PermissionError(f"⛔ Acción 'write' bloqueada. El registro está cerrado.")

            # 🛡️ BLOQUEO OPTIMISTA (ANTI-CONCURRENCY COLLISION)
            from app.core.storage.postgres_storage import PostgresGraphStorage
            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            table_name = model_name.replace(".", "_")
            ids = [int(r.id) for r in self._records if str(r.id).isdigit()]
            
            frontend_version = vals.pop('write_version', None)
            db_versions = {}

            if ids:
                rows = await conn.fetch(f'SELECT id, write_version FROM "{table_name}" WHERE id = ANY($1::bigint[]) FOR UPDATE', ids)
                db_versions = {row['id']: row['write_version'] for row in rows}
                
                for rec in self._records:
                    if str(rec.id).isdigit():
                        db_version = db_versions.get(int(rec.id))
                        base_version = frontend_version if frontend_version is not None else getattr(rec, 'write_version', 1)
                        
                        if db_version is not None and db_version > int(base_version):
                            raise ValueError(f"⚠️ [CONCURRENCY_CONFLICT] El registro {model_name}({rec.id}) ha sido modificado por otro usuario. Por favor, recarga la página.")

            o2m_data = {}
            for key in list(vals.keys()):
                attr = getattr(self._model_class, key, None)
                if isinstance(attr, One2manyField):
                    o2m_data[key] = (attr, vals.pop(key))

            now = datetime.datetime.utcnow().isoformat()
            uid = env.uid if env else 'system'

            for rec in self._records:
                local_vals = vals.copy()
                
                if str(rec.id).isdigit() and int(rec.id) in db_versions:
                    local_vals['write_version'] = db_versions[int(rec.id)] + 1
                else:
                    current_version = getattr(rec, 'write_version', 1)
                    local_vals['write_version'] = current_version + 1

                local_vals.update({'write_date': now, 'write_uid': uid})

                for key, value in local_vals.items():
                    if key != 'id' and hasattr(rec, key):
                        setattr(rec, key, value)

            if o2m_data:
                from app.core.registry import Registry
                for rec in self._records:
                    for key, (attr, lines) in o2m_data.items():
                        if not isinstance(lines, list): continue
                        ChildModel = Registry.get_model(attr.related_model)
                        if not ChildModel: continue
                        
                        inverse_name = attr.inverse_name or f"{model_name.split('.')[-1]}_id"
                        
                        current_children = await ChildModel.search([(inverse_name, '=', rec.id)])
                        current_ids = {c.id for c in current_children if str(c.id).isdigit()}
                        processed_ids = set()
                        
                        for line in lines:
                            if isinstance(line, dict):
                                line_id = line.get('id', '')
                                line_vals = {k: v for k, v in line.items() if k != 'id'}
                                line_vals[inverse_name] = rec.id
                                
                                if line_id and str(line_id).isdigit() and int(line_id) in current_ids:
                                    child_rec = await ChildModel.search([('id', '=', int(line_id))], context=rec.graph)
                                    if child_rec:
                                        await child_rec.load_data()
                                        await child_rec.write(line_vals)
                                        processed_ids.add(int(line_id))
                                else:
                                    new_child = await ChildModel.create(line_vals, context=rec.graph)
                                    processed_ids.add(new_child.id)
                            elif isinstance(line, int) or (isinstance(line, str) and str(line).isdigit()):
                                line_int = int(line)
                                processed_ids.add(line_int)
                                child_rec = await ChildModel.search([('id', '=', line_int)], context=rec.graph)
                                if child_rec:
                                    await child_rec.load_data()
                                    await child_rec.write({inverse_name: rec.id})

                        orphans = current_ids - processed_ids
                        if orphans:
                            for orphan_id in orphans:
                                orphan_rec = await ChildModel.search([('id', '=', orphan_id)], context=rec.graph)
                                if orphan_rec:
                                    await orphan_rec.load_data()
                                    await orphan_rec.unlink()
                        
                        setattr(rec, key, list(processed_ids))

            await self._run_computes()
            await env.graph.recalculate()

            for rec in self._records:
                local_vals_to_send = vals.copy()
                for f_name in dir(self._model_class):
                    f_attr = getattr(self._model_class, f_name, None)
                    if hasattr(f_attr, 'get_meta'):
                        meta = f_attr.get_meta()
                        if meta.get('store', True) and meta.get('type') not in ['one2many', 'many2many']:
                            node_name = rec._get_node_name(f_name)
                            val = rec.graph.get(node_name)
                            if isinstance(val, dict) and meta.get('translate'):
                                lang = getattr(Context.get_env(), 'lang', 'en_US')
                                local_vals_to_send[f_name] = val.get(lang, list(val.values())[0] if val else "")
                            elif val is not None: 
                                local_vals_to_send[f_name] = val
                
                for attr_name in dir(rec):
                    attr = getattr(self._model_class, attr_name, None)
                    if hasattr(attr, "_constrain_fields"):
                        if any(f in vals for f in attr._constrain_fields):
                            if asyncio.iscoroutinefunction(attr): await getattr(rec, attr_name)()
                            else: getattr(rec, attr_name)()
                
                await EventBus().publish(f"{model_name}.updated", record=rec, changes=local_vals_to_send)

            return True

    async def unlink(self) -> bool:
        if not self._records: return True
        await self._check_access()
        
        model_name = self._model_class._get_model_name()
        env = self._env or Context.get_env()

        async with AsyncGraphSavepoint(env):
            if not (env and getattr(env, 'su', False)):
                for rec in self._records:
                    if hasattr(rec, 'state'):
                        current_state = getattr(rec, "state", None)
                        if current_state not in ['draft', 'cancel', None]:
                             raise PermissionError(f"⛔ Acción 'Eliminar' bloqueada. Hay registros en uso.")

            from app.core.storage.postgres_storage import PostgresGraphStorage
            storage = PostgresGraphStorage()
            conn = await storage.get_connection()
            table_name = model_name.replace(".", "_")
            
            ids = [r.id for r in self._records if str(r.id).isdigit()]

            if ids:
                try:
                    await conn.execute(f'DELETE FROM "{table_name}" WHERE id = ANY($1::bigint[])', ids)
                except Exception as e:
                    raise ValueError(f"❌ No se pueden eliminar los registros. Probablemente estén vinculados a otras operaciones (Integridad Referencial).")

            graph = env.graph
            keys_to_remove = [k for k in list(graph._values.keys()) if isinstance(k, tuple) and k[0] == model_name and k[1] in ids]
            
            for k in keys_to_remove:
                try: del graph._values[k]
                except KeyError: graph._values[k] = None  
                
                if hasattr(graph, '_versions'):
                    try: del graph._versions[k]
                    except KeyError: graph._versions[k] = None

                if hasattr(graph, '_dirty_nodes'):
                    graph._dirty_nodes.discard(k)

            for rec_id in ids:
                await EventBus().publish(f"{model_name}.unlinked", record_id=rec_id)
                
            return True

    def mapped(self, field_name: str) -> List[Any]:
        return [getattr(rec, field_name) for rec in self._records]

    def filtered(self, func: Callable[[Any], bool]) -> 'Recordset':
        return Recordset(self._model_class, [r for r in self._records if func(r)], self._env)

    def __getattr__(self, name):
        if len(self._records) == 1:
            return getattr(self._records[0], name)
        elif len(self._records) == 0:
            raise ValueError(f"❌ Recordset vacío: No se puede leer '{name}'.")
        else:
            raise ValueError(f"❌ Error Singleton: Tienes {len(self._records)} registros. Usa .read()")
            
    def __repr__(self):
        name = self._model_class.__name__ if self._model_class else "Unknown"
        return f"<{name}Recordset({len(self._records)} records)>"

# =============================================================================
# CAMPOS CON SOPORTE i18n NATIVO (JSONB)
# =============================================================================
class Field:
    def __init__(self, default: Any = None, label: str = None, type_: str = "string", required: bool = False, readonly: bool = False, index: bool = False, store: bool = True, translate: bool = False, **kwargs):
        self.name: str = ""
        self.default = default
        self.label = label
        self.type = type_
        self.required = required
        self.readonly = readonly
        self.index = index
        self.store = store
        self.translate = translate
        self.extra_meta = kwargs

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None: return self
        if self.name == 'id': return instance._id_val
        
        node_name = instance._get_node_name(self.name)
        val = instance.graph.get(node_name)
        
        if val is not None and self.translate:
            if isinstance(val, dict):
                env = Context.get_env()
                lang = getattr(env, 'lang', 'en_US') if env else 'en_US'
                return val.get(lang, list(val.values())[0] if val else "")
            return val
            
        if val is None:
            return self.default() if callable(self.default) else self.default
        return val

    def __set__(self, instance, value):
        if self.name == 'id':
            if not hasattr(instance, '_id_val') or instance._id_val is None:
                instance._id_val = int(value) if str(value).isdigit() else str(value)
            return

        if self.required and (value is None or value == "" or value is False):
            if not (self.type == 'bool' and value is False):
                raise ValueError(f"❌ Campo '{self.label or self.name}' es obligatorio.")
        
        node_name = instance._get_node_name(self.name)
        
        if self.translate and value is not None:
            env = Context.get_env()
            lang = getattr(env, 'lang', 'en_US') if env else 'en_US'
            current_dict = instance.graph.get(node_name) or {}
            if isinstance(current_dict, dict):
                current_dict[lang] = value
                value = current_dict
            else:
                value = {lang: value}

        if isinstance(value, datetime.datetime): value = value.isoformat()
        instance.graph.set_fact(node_name, value)

    def get_meta(self) -> Dict:
        return {
            "type": "jsonb" if self.translate else self.type,
            "logical_type": self.type,
            "label": self.label or self.name.replace('_', ' ').title(),
            "required": self.required,
            "readonly": self.readonly,
            "index": self.index,
            "store": self.store,
            "translate": self.translate,
            "**": self.extra_meta
        }

class DecimalField(Field):
    def __init__(self, digits=(16, 4), type_="decimal", **kwargs):
        super().__init__(type_=type_, digits=digits, **kwargs)
        self.digits = digits

    def __set__(self, instance, value):
        if value is not None:
            try:
                value = decimal.Decimal(str(value))
            except (decimal.InvalidOperation, ValueError, TypeError):
                raise ValueError(f"❌ Valor inválido para campo Decimal '{self.name}': {value}")
        super().__set__(instance, value)

class MonetaryField(DecimalField):
    def __init__(self, currency_field='currency_id', digits=(16, 2), **kwargs):
        super().__init__(digits=digits, type_="monetary", currency_field=currency_field, **kwargs)

class SelectionField(Field):
    def __init__(self, options: List[str], **kwargs):
        super().__init__(type_="selection", options=options, **kwargs)
        self.options = options
        
    def __set__(self, instance, value):
        val_to_check = value[0] if isinstance(value, (list, tuple)) else value
        valid_keys = [opt[0] if isinstance(opt, (list, tuple)) else opt for opt in self.options]
        if val_to_check and val_to_check not in valid_keys:
            raise ValueError(f"❌ Valor '{val_to_check}' inválido. Opciones: {valid_keys}")
        super().__set__(instance, val_to_check)

class ComputedField(Field):
    def __init__(self, func: Callable, depends_on: List[str], store: bool = False, **kwargs):
        readonly = kwargs.pop('readonly', True)
        super().__init__(type_="computed", store=store, readonly=readonly, **kwargs)
        self.func = func
        self.depends_on = depends_on

class RelationField(Field):
    def __init__(self, model_cls: Union[Type, str], ondelete: str = 'set null', **kwargs):
        super().__init__(type_="relation", target=str(model_cls), ondelete=ondelete, **kwargs)
        self.related_model = model_cls

    def __get__(self, instance, owner):
        if instance is None: return self
        related_id = super().__get__(instance, owner)
        if not related_id: return None
        from app.core.registry import Registry
        target = self.related_model if self.related_model != 'self' else instance._get_model_name()
        ModelClass = Registry.get_model(target)
        return ModelClass(_id=related_id, context=instance.graph)
    
    def __set__(self, instance, value):
        if hasattr(value, 'id'): 
            super().__set__(instance, value.id)
        else: 
            val = int(value) if str(value).isdigit() else value
            super().__set__(instance, val)

class One2manyField(Field):
    def __init__(self, related_model: str, inverse_name: str = None, **kwargs):
        super().__init__(type_="one2many", target=related_model, store=False, **kwargs)
        self.related_model = related_model
        self.inverse_name = inverse_name
        
    def __get__(self, instance, owner):
        if instance is None: return self
        ids = super().__get__(instance, owner) or []
        
        virtual_records = instance.graph.get(("virtual", instance._get_model_name(), instance.id, self.name))
        from app.core.registry import Registry
        try:
            ModelClass = Registry.get_model(self.related_model)
            if virtual_records is not None:
                return Recordset(ModelClass, virtual_records, Context.get_env())
            return Recordset(ModelClass, [ModelClass(_id=i, context=instance.graph) for i in ids])
        except Exception: return Recordset(None, [])

    def __set__(self, instance, value):
        clean_ids = []
        virtual_records = []
        from app.core.registry import Registry
        try: ChildModel = Registry.get_model(self.related_model)
        except Exception: ChildModel = None

        if isinstance(value, (list, Recordset)):
            for item in value:
                if isinstance(item, dict) and ChildModel:
                    v_id = item.get('id') or f"new_{uuid.uuid4().hex[:8]}"
                    v_rec = ChildModel(_id=v_id, context=instance.graph)
                    for k, v in item.items():
                        if hasattr(v_rec, k): setattr(v_rec, k, v)
                    virtual_records.append(v_rec)
                    clean_ids.append(v_id)
                elif hasattr(item, 'id'):
                    clean_ids.append(item.id)
                    virtual_records.append(item)
                else:
                    val = int(item) if str(item).isdigit() else str(item)
                    clean_ids.append(val)
                    if ChildModel:  
                        virtual_records.append(ChildModel(_id=val, context=instance.graph))
        
        super().__set__(instance, clean_ids)
        instance.graph.set_fact(("virtual", instance._get_model_name(), instance.id, self.name), virtual_records)

class Many2manyField(Field):
    def __init__(self, related_model: str, **kwargs):
        super().__init__(type_="many2many", target=related_model, store=True, **kwargs)
        self.related_model = related_model

    def __get__(self, instance, owner):
        if instance is None: return self
        ids = super().__get__(instance, owner) or []
        from app.core.registry import Registry
        try:
            ModelClass = Registry.get_model(self.related_model)
            return Recordset(ModelClass, [ModelClass(_id=i, context=instance.graph) for i in ids])
        except Exception: return Recordset(None, [])

    def __set__(self, instance, value):
        clean_ids = []
        if isinstance(value, (list, Recordset)):
            for item in value:
                clean_ids.append(item.id if hasattr(item, 'id') else (int(item) if str(item).isdigit() else item))
        super().__set__(instance, clean_ids)

class PasswordField(Field):
    def __init__(self, **kwargs): super().__init__(type_="password", **kwargs)

# =============================================================================
# DECORADORES DEL MOTOR (Magia DSL)
# =============================================================================
def compute(depends: List[str], store: bool = False):
    def decorator(func): return ComputedField(func, depends, store=store)
    return decorator

def constrains(*fields):
    def decorator(func):
        func._constrain_fields = fields
        return func
    return decorator

def check_state(allowed_states: List[str]):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            current_state = getattr(self, "state", None)
            if current_state and current_state not in allowed_states:
                raise PermissionError(f"⛔ Acción '{func.__name__}' bloqueada. Estado '{current_state}' no permitido.")
            return await func(self, *args, **kwargs)
        wrapper._is_action = True
        return wrapper
    return decorator

def onchange(*fields):
    def decorator(func):
        func._onchange_fields = fields
        return func
    return decorator

# =============================================================================
# MODEL – HIPERDIOS EDITION FINAL
# =============================================================================
class Model:
    _name = None
    _inherit = None
    _abstract = False  
    _rec_name = 'name'
    
    _sql_constraints = []
    
    id = Field(type_='int', primary_key=True, readonly=True)
    active = Field(default=True, type_="bool")
    write_version = Field(type_='int', default=1, readonly=True)
    create_date = Field(type_="datetime", readonly=True)
    write_date = Field(type_="datetime", readonly=True)
    create_uid = Field(type_="string", readonly=True)
    write_uid = Field(type_="string", readonly=True)

    def __init__(self, _id: Union[int, str] = None, context: Optional[Graph] = None, env: Optional[Env] = None):
        if _id is not None:
            self._id_val = int(_id) if str(_id).isdigit() else str(_id)
        else:
            self._id_val = f"new_{uuid.uuid4().hex[:8]}"
            
        self.graph = context if context else (Context.get_graph() or Graph())
        self._env = env or Context.get_env()

    @classmethod
    @ormcache('ir.ui.view')  
    async def get_view(cls, view_type: str = 'form'):
        from app.core.scaffolder import ViewScaffolder
        return await ViewScaffolder.get_default_view(cls._get_model_name(), view_type)

    def _get_node_name(self, field_name: str) -> tuple:
        return (self._get_model_name(), self._id_val, field_name)

    @classmethod
    def _get_model_name(cls):
        if cls._name: return cls._name
        if not hasattr(cls, '_auto_name'):
            cls._auto_name = re.sub(r'(?<!^)(?=[A-Z])', '.', cls.__name__).lower().replace('ir.', 'ir.').replace('res.', 'res.')
        return cls._auto_name

    @property
    def display_name(self) -> str:
        for field in [self._rec_name, 'name', 'display_name', 'login']:
            try:
                val = self.graph.get(self._get_node_name(field))
                if val: 
                    if isinstance(val, dict):
                        lang = getattr(self._env, 'lang', 'en_US') if self._env else 'en_US'
                        return str(val.get(lang, list(val.values())[0] if val else ""))
                    return str(val)
            except: continue
        return f"{self._get_model_name()}({self._id_val})"

    @classmethod
    async def _auto_init(cls):
        if cls._abstract: return

        from app.core.storage.postgres_storage import PostgresGraphStorage
        storage = PostgresGraphStorage()
        conn = await storage.get_connection()
        table_name = cls._get_model_name().replace('.', '_')

        PG_TYPES = {
            'string': 'VARCHAR(255)',
            'password': 'VARCHAR(255)',
            'text': 'TEXT',
            'int': 'INTEGER',
            'float': 'DOUBLE PRECISION',
            'decimal': 'NUMERIC',
            'monetary': 'NUMERIC',
            'bool': 'BOOLEAN',
            'datetime': 'TIMESTAMP',
            'date': 'DATE',
            'relation': 'BIGINT',   
            'many2one': 'BIGINT',   
            'selection': 'VARCHAR(255)',
            'jsonb': 'JSONB'
        }

        try:
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                table_name
            )

            fields_meta = {}
            for name in dir(cls):
                attr = getattr(cls, name, None)
                if hasattr(attr, 'get_meta'):
                    meta = attr.get_meta()
                    if meta.get('store', True) and meta.get('type') not in ['one2many', 'many2many']:
                        fields_meta[name] = meta

            if not table_exists:
                print(f"🛠️ [DDL] Evolución Inicial: Creando tabla {table_name}...")
                columns_sql = []
                for f_name, meta in fields_meta.items():
                    pg_type = PG_TYPES.get(meta['type'], 'VARCHAR(255)')
                    if f_name == 'id':
                        columns_sql.append(f'"{f_name}" BIGSERIAL PRIMARY KEY')
                    else:
                        columns_sql.append(f'"{f_name}" {pg_type}')
                
                if 'x_ext' not in fields_meta:
                    columns_sql.append('"x_ext" JSONB')
                    
                create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns_sql)})'
                await conn.execute(create_sql)
                
                await conn.execute(f'CREATE INDEX "idx_{table_name}_x_ext_gin" ON "{table_name}" USING GIN ("x_ext")')
            else:
                existing_cols = await conn.fetch(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
                    table_name
                )
                db_cols = {col['column_name'] for col in existing_cols}

                for f_name, meta in fields_meta.items():
                    if f_name not in db_cols:
                        pg_type = PG_TYPES.get(meta['type'], 'VARCHAR(255)')
                        print(f"✨ [DDL] Mutación Detectada en {table_name}: Agregando columna '{f_name}' ({pg_type})")
                        await conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{f_name}" {pg_type}')
                        
                if 'x_ext' not in db_cols:
                    await conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "x_ext" JSONB')
                    await conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_x_ext_gin" ON "{table_name}" USING GIN ("x_ext")')

        except Exception as e:
            print(f"❌ Error crítico de DDL en la tabla {table_name}: {e}")

    @staticmethod
    def _normalize_domain(domain: List[Any]) -> List[Any]:
        if not domain: return []
        normalized = []
        
        ALLOWED_OPERATORS = {'=', '!=', '>', '<', '>=', '<=', 'in', 'not in', 'like', 'ilike', 'not ilike', 'child_of', 'parent_of'}
        
        for item in domain:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, op, value = item
                if str(op).lower() not in ALLOWED_OPERATORS:
                    raise ValueError(f"🛑 [SECURITY BLOCK] Intento de inyección detectado. Operador SQL no permitido: {op}")
                normalized.append(tuple(item))
            else:
                if str(item) not in ['&', '|', '!']:
                    pass
                normalized.append(item)
        return normalized

    @classmethod
    async def create(cls, vals: Dict[str, Any], context: Optional[Graph] = None) -> 'Model':
        model_name = cls._get_model_name()
        env = Context.get_env()
        now = datetime.datetime.utcnow().isoformat()
        graph = context if context else (Context.get_graph() or Graph())

        async with AsyncGraphSavepoint(env):
            o2m_data = {}
            for key in list(vals.keys()):
                attr = getattr(cls, key, None)
                if isinstance(attr, One2manyField):
                    o2m_data[key] = (attr, vals.pop(key))

            record_id = vals.get('_id') or vals.get('id')
            record = cls(_id=record_id, context=graph)
            record._is_new = True

            if hasattr(cls, 'name') and (not vals.get('name') or vals.get('name') in ['Nuevo', 'New', '']):
                vals['name'] = f"DOC-{str(uuid.uuid4().int)[:4]}"

            vals.update({
                'id': record.id,
                'create_date': now, 'write_date': now,
                'create_uid': env.uid if env else 'system',
                'write_uid': env.uid if env else 'system',
                'write_version': 1
            })

            for name in dir(cls):
                attr = getattr(cls, name)
                if isinstance(attr, Field) and name not in vals:
                    vals[name] = attr.default() if callable(attr.default) else attr.default

            for key, value in vals.items():
                if key != 'id' and hasattr(record, key):
                    setattr(record, key, value)

            if o2m_data:
                from app.core.registry import Registry
                for key, (attr, lines) in o2m_data.items():
                    if not isinstance(lines, list): continue
                    ChildModel = Registry.get_model(attr.related_model)
                    if not ChildModel: continue
                    
                    inverse_name = attr.inverse_name or f"{model_name.split('.')[-1]}_id"
                    saved_ids = []
                    
                    for line in lines:
                        if isinstance(line, dict):
                            line_vals = {k: v for k, v in line.items() if k != 'id'}
                            line_vals[inverse_name] = record.id
                            new_child = await ChildModel.create(line_vals, context=graph)
                            saved_ids.append(new_child.id)
                    setattr(record, key, saved_ids)

            rs = Recordset(cls, [record], env)
            await rs._run_computes()
            await record.graph.recalculate()

            for f_name in dir(cls):
                f_attr = getattr(cls, f_name, None)
                if hasattr(f_attr, 'get_meta'):
                    meta = f_attr.get_meta()
                    if meta.get('store', True) and meta.get('type') not in ['one2many', 'many2many']:
                        node_name = record._get_node_name(f_name)
                        val = record.graph.get(node_name)
                        if val is not None: vals[f_name] = val

            for attr_name in dir(record):
                attr = getattr(cls, attr_name, None)
                if hasattr(attr, "_constrain_fields"):
                    if asyncio.iscoroutinefunction(attr): await getattr(record, attr_name)()
                    else: getattr(record, attr_name)()

            record._is_new = False
            await EventBus().publish(f"{model_name}.created", record=record)
            return record

    async def write(self, vals: Dict[str, Any]) -> bool:
        rs = Recordset(self.__class__, [self], self._env)
        return await rs.write(vals)

    async def unlink(self) -> bool:
        rs = Recordset(self.__class__, [self], self._env)
        return await rs.unlink()

    async def read(self) -> dict:
        rs = Recordset(self.__class__, [self], self._env)
        results = await rs.read()
        return results[0] if results else {}

    @action(label="Archivar", icon="archive", variant="secondary")
    async def action_archive(self):
        if hasattr(self, 'active'):
            await self.write({'active': False})
            
    @action(label="Restaurar", icon="archive_restore", variant="secondary")
    async def action_unarchive(self):
        if hasattr(self, 'active'):
            await self.write({'active': True})

    @classmethod
    async def search(cls, domain: List = None, limit: int = None, offset: int = None, order_by: str = None, context: Optional[Graph] = None) -> Recordset:
        from app.core.storage.postgres_storage import PostgresGraphStorage
        from app.core.registry import Registry
        
        domain = cls._normalize_domain(domain or [])
        env = Context.get_env()
        model_name = cls._get_model_name()

        if hasattr(cls, 'active'):
            has_active_filter = any(isinstance(d, tuple) and d[0] == 'active' for d in domain if isinstance(d, (tuple, list)))
            if not has_active_filter:
                if domain:
                    domain = ['&', ('active', '=', True)] + domain
                else:
                    domain = [('active', '=', True)]

        if env and not env.su and model_name not in ['ir.rule', 'ir.model', 'ir.model.fields', 'res.users']:
            try:
                IrRuleModel = Registry.get_model('ir.rule')
                user_domain = await IrRuleModel.get_domain(model_name, env.uid)
                if user_domain: domain = ['&'] + user_domain + domain if domain else user_domain
            except Exception: pass

        storage = PostgresGraphStorage()
        ids = await storage.search_domain(model_name, domain, limit, offset, order_by)
        
        records = [cls(_id=rid, context=context or Context.get_graph()) for rid in ids]
        return Recordset(cls, records, env)

    @classmethod
    def browse(cls, ids: List[Union[int, str]], context: Optional[Graph] = None) -> Recordset:
        unique_ids = []
        for i in ids:
            if i not in unique_ids: unique_ids.append(i)
        return Recordset(cls, [cls(_id=i, context=context or Context.get_graph()) for i in unique_ids])

    def __repr__(self):
        return f"<{self.__class__.__name__}({self._id_val})>"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        if '_abstract' not in cls.__dict__:
            cls._abstract = False

        try:
            from app.core.registry import Registry
            Registry.register_model(cls)
            
            if not getattr(cls, '_inherit', None) and not cls._abstract:
                model_name = cls._get_model_name()
                for name in dir(cls):
                    attr = getattr(cls, name, None)
                    if hasattr(attr, 'get_meta'):
                        meta = attr.get_meta()
                        if meta.get('store', True):
                            Registry.register_field(model_name, name, meta)
        except Exception: pass