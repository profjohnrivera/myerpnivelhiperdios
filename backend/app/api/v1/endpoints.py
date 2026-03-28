# backend/app/api/v1/endpoints.py
import traceback
import json
from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse 
from app.core.registry import Registry
from app.core.ui_registry import UIRegistry  
from app.core.env import Env
from app.core.orm import Model
from app.core.scaffolder import ViewScaffolder
from app.core.storage.postgres_storage import PostgresGraphStorage
from app.core.transaction import transaction
from app.core.security import get_current_user
from app.core.worker import WorkerEngine 
import asyncio

router = APIRouter()

async def _read_row_from_db(storage: PostgresGraphStorage, model_name: str, record_id: int) -> dict:
    conn_or_pool = await storage.get_connection()
    table_name = model_name.replace(".", "_")
    try:
        if hasattr(conn_or_pool, 'acquire'):
            async with conn_or_pool.acquire() as conn:
                row = await conn.fetchrow(f'SELECT * FROM "{table_name}" WHERE id = $1', record_id)
        else:
            row = await conn_or_pool.fetchrow(f'SELECT * FROM "{table_name}" WHERE id = $1', record_id)
        if not row: return {"id": record_id}

        result = {}
        for col, val in row.items():
            if col == "x_ext" and val:
                extra = json.loads(val) if isinstance(val, str) else dict(val)
                result.update(extra)
            else:
                result[col] = storage._parse_db_value(val)
        return result
    except Exception as e:
        return {"id": record_id}

async def _read_rows_bulk(storage: PostgresGraphStorage, model_name: str, record_ids: list) -> dict:
    clean_ids = [int(i) for i in record_ids if str(i).isdigit()]
    if not clean_ids: return {}
    
    conn_or_pool = await storage.get_connection()
    table_name = model_name.replace(".", "_")
    
    try:
        query = f'SELECT * FROM "{table_name}" WHERE id = ANY($1::bigint[])'
        if hasattr(conn_or_pool, 'acquire'):
            async with conn_or_pool.acquire() as conn:
                rows = await conn.fetch(query, clean_ids)
        else:
            rows = await conn_or_pool.fetch(query, clean_ids)

        result_map = {}
        for row in rows:
            row_dict = {}
            for col, val in row.items():
                if col == "x_ext" and val:
                    extra = json.loads(val) if isinstance(val, str) else dict(val)
                    row_dict.update(extra)
                else:
                    row_dict[col] = storage._parse_db_value(val)
            result_map[row['id']] = row_dict
        return result_map
    except Exception as e:
        return {}

def _find_inverse_field(child_model_name: str, parent_model_name: str, parent_field_name: str = None) -> str:
    if parent_field_name:
        parent_cls = Registry.get_model(parent_model_name)
        parent_attr = getattr(parent_cls, parent_field_name, None)
        if parent_attr and hasattr(parent_attr, 'inverse_name') and parent_attr.inverse_name:
            return parent_attr.inverse_name
            
    child_cls = Registry.get_model(child_model_name)
    for fname in dir(child_cls):
        attr = getattr(child_cls, fname, None)
        if hasattr(attr, 'get_meta'):
            meta = attr.get_meta()
            if meta.get('type') == 'relation':
                target = getattr(attr, 'related_model', '') or meta.get('target', '')
                if Registry._resolve_name(str(target)) == parent_model_name:
                    return fname
    return parent_model_name.split('.')[-1] + '_id'

async def _serialize_records(env, records, model_name: str, fields: list = None) -> list:
    if not records: return []
    storage = PostgresGraphStorage()
    
    record_ids = [r.id for r in records if str(r.id).isdigit()]
    if not record_ids: return []
    
    rows_map = await _read_rows_bulk(storage, model_name, record_ids)
    model_cls = Registry.get_model(model_name)
    
    m2o_fields = {}
    o2m_fields = {}
    m2m_fields = {}
    
    for fname in dir(model_cls):
        if fields and fname not in fields and fname != 'id': continue

        attr = getattr(model_cls, fname, None)
        if not hasattr(attr, 'get_meta'): continue
        meta = attr.get_meta()
        if meta.get('type') in ('relation', 'many2one'):
            m2o_fields[fname] = getattr(attr, 'related_model', None) or meta.get('target')
        elif meta.get('type') == 'one2many':
            o2m_fields[fname] = getattr(attr, 'related_model', None) or meta.get('target')
        elif meta.get('type') == 'many2many':
            m2m_fields[fname] = getattr(attr, 'related_model', None) or meta.get('target')

    base_rows = []
    for r_id in record_ids:
        if r_id in rows_map:
            base_rows.append(rows_map[r_id])
        else:
            base_rows.append({"id": r_id})

    for fname, target_model in m2o_fields.items():
        if not target_model: continue
        target_cls = Registry.get_model(target_model)
        rec_name = getattr(target_cls, '_rec_name', 'name')
        
        target_ids = list(set([row[fname] for row in base_rows if row.get(fname) and not isinstance(row[fname], list)]))
        target_int_ids = [int(i) for i in target_ids if str(i).isdigit()]
        
        if target_int_ids:
            target_rows = await _read_rows_bulk(storage, target_model, target_int_ids)
            for row in base_rows:
                raw_id = row.get(fname)
                if raw_id and str(raw_id).isdigit():
                    raw_id = int(raw_id)
                    if raw_id in target_rows:
                        display = target_rows[raw_id].get(rec_name) or target_rows[raw_id].get('name') or str(raw_id)
                        row[fname] = [raw_id, display]
                    else:
                        row[fname] = [raw_id, str(raw_id)]

    for fname, target_model in o2m_fields.items():
        if not target_model: 
            for row in base_rows: row[fname] = []
            continue
        
        inverse_field = _find_inverse_field(target_model, model_name, fname)
        conn_or_pool = await storage.get_connection()
        table_name = target_model.replace(".", "_")
        
        try:
            query = f'SELECT * FROM "{table_name}" WHERE "{inverse_field}" = ANY($1::bigint[])'
            if hasattr(conn_or_pool, 'acquire'):
                async with conn_or_pool.acquire() as conn:
                    child_rows_raw = await conn.fetch(query, record_ids)
            else:
                child_rows_raw = await conn_or_pool.fetch(query, record_ids)
            
            children_list = []
            for crow in child_rows_raw:
                cdict = {}
                for col, val in crow.items():
                    if col == "x_ext" and val:
                        extra = json.loads(val) if isinstance(val, str) else dict(val)
                        cdict.update(extra)
                    else:
                        cdict[col] = storage._parse_db_value(val)
                children_list.append(cdict)
        except Exception as e:
            children_list = []

        target_cls = Registry.get_model(target_model)
        child_m2o_fields = {}
        for cfname in dir(target_cls):
            cattr = getattr(target_cls, cfname, None)
            if hasattr(cattr, 'get_meta'):
                cmeta = cattr.get_meta()
                if cmeta.get('type') in ('relation', 'many2one'):
                    child_m2o_fields[cfname] = getattr(cattr, 'related_model', None) or cmeta.get('target')
        
        for cfname, crel_model in child_m2o_fields.items():
            if not crel_model: continue
            crel_cls = Registry.get_model(crel_model)
            crec_name = getattr(crel_cls, '_rec_name', 'name')
            
            crel_ids = list(set([c[cfname] for c in children_list if c.get(cfname) and not isinstance(c[cfname], list)]))
            crel_int_ids = [int(i) for i in crel_ids if str(i).isdigit()]
            
            if crel_int_ids:
                crel_rows = await _read_rows_bulk(storage, crel_model, crel_int_ids)
                for c in children_list:
                    raw_id = c.get(cfname)
                    if raw_id and str(raw_id).isdigit():
                        raw_id = int(raw_id)
                        if raw_id in crel_rows:
                            display = crel_rows[raw_id].get(crec_name) or crel_rows[raw_id].get('name') or str(raw_id)
                            c[cfname] = [raw_id, display]
                        else:
                            c[cfname] = [raw_id, str(raw_id)]

        crec_name_field = getattr(target_cls, '_rec_name', 'name')
        grouped_children = {rid: [] for rid in record_ids}
        for c in children_list:
            if crec_name_field and crec_name_field in c and 'name' not in c:
                c['name'] = c[crec_name_field]
            
            p_id = c.get(inverse_field)
            if isinstance(p_id, list) and len(p_id) > 0:
                p_id = p_id[0]
                
            if p_id: 
                grouped_children.setdefault(p_id, []).append(c)
        
        for row in base_rows:
            row[fname] = grouped_children.get(row.get('id'), [])

    for fname, target_model in m2m_fields.items():
        for row in base_rows:
            r_id = row['id']
            rec = next((r for r in records if r.id == r_id), None)
            if rec:
                m2m_val = getattr(rec, fname, [])
                if hasattr(m2m_val, '_records'):
                    row[fname] = [r.id for r in m2m_val._records if str(r.id).isdigit()]
                elif isinstance(m2m_val, list):
                    row[fname] = [int(i) for i in m2m_val if str(i).isdigit()]
                else:
                    row[fname] = []

    return base_rows

async def _serialize_record(env, record, model_name: str) -> dict:
    results = await _serialize_records(env, [record], model_name, fields=None)
    return results[0] if results else {}

def _clean_m2o_payload(vals: dict) -> dict:
    safe_vals = {}
    for k, v in vals.items():
        if k == 'id': continue
        if isinstance(v, list) and len(v) >= 2:
            clean_id = v[0]
            safe_vals[k] = int(clean_id) if str(clean_id).isdigit() else clean_id
        elif k.endswith('_id') and isinstance(v, (int, float, str)):
            safe_vals[k] = int(v) if str(v).isdigit() else v
        else:
            safe_vals[k] = v
    return safe_vals

def extract_x2many_data(model_name, vals):
    x2many_data = {}
    x2many_meta = {}
    model_cls = Registry.get_model(model_name)
    for fname in list(vals.keys()):
        attr = getattr(model_cls, fname, None)
        if hasattr(attr, 'get_meta'):
            meta = attr.get_meta()
            if meta.get('type') == 'one2many':
                x2many_data[fname] = vals.pop(fname)
                meta['target'] = getattr(attr, 'related_model', None) or meta.get('target')
                x2many_meta[fname] = meta
    return x2many_data, x2many_meta

async def process_nested_records(env, parent_model_name, parent_record, x2many_data, x2many_meta):
    storage = PostgresGraphStorage()
    session_graph = parent_record.graph 

    for fname, items in x2many_data.items():
        meta = x2many_meta.get(fname, {})
        target_model_name = meta.get('target')
        if not target_model_name: continue

        target_model = env[target_model_name]
        inverse_field = _find_inverse_field(target_model_name, parent_model_name, fname)
        valid_fields = [f for f in dir(target_model) if hasattr(getattr(target_model, f, None), 'get_meta')]

        existing_recs = await storage.search_domain(target_model_name, [(inverse_field, '=', parent_record.id)])
        existing_ids = set(existing_recs)
        
        incoming_ids = set()
        for i in items:
            if isinstance(i, dict) and i.get('id'):
                i_id = i.get('id')
                if str(i_id).isdigit():
                    incoming_ids.add(int(i_id))

        for del_id in (existing_ids - incoming_ids):
            child = target_model.browse([del_id], context=session_graph)
            if child: 
                await child.load_data()
                await child[0].unlink()

        final_child_ids = []

        for item in items:
            if not isinstance(item, dict): continue

            for k, v in list(item.items()):
                if isinstance(v, list) and len(v) >= 2:
                    clean_id = v[0]
                    item[k] = int(clean_id) if str(clean_id).isdigit() else clean_id
                elif k.endswith('_id') and isinstance(v, (int, float, str)):
                    item[k] = int(v) if str(v).isdigit() else v

            product_val = item.get('product_id') or item.get('name')
            
            if product_val and isinstance(product_val, str) and "-" not in product_val:
                product_val = product_val.strip()
                if len(product_val) <= 2:
                    item['product_id'] = None
                    item['name'] = product_val 
                else:
                    try:
                        ProductModel = env['product.product']
                        existing = await ProductModel.search([('name', '=', product_val)], limit=1, context=session_graph)
                        if existing:
                            item['product_id'] = existing[0].id
                            if not item.get('name'): item['name'] = existing[0].name
                        else:
                            new_prod = await ProductModel.create({'name': product_val, 'list_price': item.get('price_unit', 1.0)}, context=session_graph)
                            item['product_id'] = new_prod.id
                            if not item.get('name'): item['name'] = product_val
                    except Exception as e:
                        item['product_id'] = None

            try: item['product_uom_qty'] = float(item.get('product_uom_qty') or 1.0)
            except: item['product_uom_qty'] = 1.0
                
            try: item['price_unit'] = float(item.get('price_unit') or 0.0)
            except: item['price_unit'] = 0.0

            item_id = item.pop('id', None)
            item.pop('isNew', None)

            clean_item = {k: v for k, v in item.items() if k in valid_fields}
            clean_item[inverse_field] = parent_record.id

            try:
                if item_id and str(item_id).isdigit():
                    child = target_model.browse([int(item_id)], context=session_graph)
                    if child: 
                        await child.load_data()
                        await child[0].write(clean_item)
                        final_child_ids.append(int(item_id)) 
                else:
                    new_child = await target_model.create(clean_item, context=session_graph)
                    final_child_ids.append(new_child.id) 
            except Exception as e:
                pass 
        
        setattr(parent_record, fname, final_child_ids)


# ==============================================================================
# 🎯 ENDPOINTS SDUI: PUENTES REACTIVOS Y DE ESTADO INICIAL
# ==============================================================================

@router.get("/data/{model_name}/default_get")
async def default_get(model_name: str, current_user_id: int = Depends(get_current_user)):
    try:
        session_graph = Model._graph.clone_for_session()
        env = Env(user_id=current_user_id, graph=session_graph)
        ModelClass = Registry.get_model(model_name)
        virtual_record = ModelClass(context=session_graph)
        return await _serialize_record(env, virtual_record, model_name)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# 🛡️ MOTOR RECURSIVO DE REACCIÓN SDUI
# -----------------------------------------------------------------------------
def _clean_onchange_payload(data: dict) -> dict:
    """Limpia recursivamente las tuplas Many2One [id, name] a solo ID para que el ORM lo entienda."""
    cleaned = {}
    for k, v in data.items():
        if isinstance(v, list):
            if len(v) >= 2 and not isinstance(v[0], dict) and (isinstance(v[0], int) or str(v[0]).isdigit()):
                cleaned[k] = int(v[0])
            elif len(v) > 0 and isinstance(v[0], dict):
                cleaned[k] = [_clean_onchange_payload(child) for child in v]
            else:
                cleaned[k] = v
        else:
            cleaned[k] = v
    return cleaned

async def _deep_trigger_onchanges(record, payload_data):
    """
    ⚡ FIX ARQUITECTÓNICO: Ejecución Bottom-Up (De abajo hacia arriba).
    Primero evalúa a los hijos (para que vayan a BD a buscar precios),
    y luego evalúa al padre (para que sume los precios ya calculados).
    """
    # 1. PRIMERO: Cascada a las líneas (Hijos One2Many)
    for field_name, field_value in payload_data.items():
        if isinstance(field_value, list) and len(field_value) > 0 and isinstance(field_value[0], dict):
            nested_records = getattr(record, field_name, None)
            if nested_records and hasattr(nested_records, '__iter__'):
                nested_list = list(nested_records)
                for i, item_payload in enumerate(field_value):
                    if i < len(nested_list):
                        await _deep_trigger_onchanges(nested_list[i], item_payload)

    # 2. DESPUÉS: Onchanges del nivel actual (Padre)
    for attr_name in dir(record.__class__):
        method = getattr(record.__class__, attr_name)
        if hasattr(method, '_onchange_fields'):
            if any(f in payload_data for f in method._onchange_fields):
                bound_method = getattr(record, attr_name)
                if asyncio.iscoroutinefunction(bound_method):
                    await bound_method()
                else:
                    bound_method()

@router.post("/data/{model_name}/onchange")
async def onchange_record(model_name: str, payload: dict = Body(...), current_user_id: int = Depends(get_current_user)):
    try:
        session_graph = Model._graph.clone_for_session()
        env = Env(user_id=current_user_id, graph=session_graph)
        
        ModelClass = Registry.get_model(model_name)
        virtual_record = ModelClass(context=session_graph)
        
        clean_payload = _clean_onchange_payload(payload)
        
        for key, value in clean_payload.items():
            attr = getattr(virtual_record.__class__, key, None)
            is_o2m = False
            target_model_name = None
            
            if hasattr(attr, 'get_meta'):
                meta = attr.get_meta()
                if meta.get('type') == 'one2many':
                    is_o2m = True
                    target_model_name = getattr(attr, 'related_model', None) or meta.get('target')

            if is_o2m and target_model_name and isinstance(value, list):
                ChildModel = Registry.get_model(target_model_name)
                if not ChildModel: continue
                
                virtual_children = []
                for item_data in value:
                    if isinstance(item_data, dict):
                        child_rec = ChildModel(context=session_graph)
                        for ck, cv in item_data.items():
                            if hasattr(child_rec, ck):
                                setattr(child_rec, ck, cv)
                        
                        inverse_name = getattr(attr, 'inverse_name', None)
                        if inverse_name and hasattr(child_rec, inverse_name):
                            setattr(child_rec, inverse_name, virtual_record)
                            
                        virtual_children.append(child_rec)
                    else:
                        virtual_children.append(item_data)
                        
                setattr(virtual_record, key, virtual_children)
            else:
                if hasattr(virtual_record, key):
                    setattr(virtual_record, key, value)
                    
        await _deep_trigger_onchanges(virtual_record, clean_payload)
        await session_graph.recalculate()
        
        db_serialized = await _serialize_record(env, virtual_record, model_name)
        if not db_serialized: db_serialized = {}
        
        for fname in dir(ModelClass):
            meta_attr = getattr(ModelClass, fname, None)
            if not hasattr(meta_attr, 'get_meta'): continue
            meta = meta_attr.get_meta()
            ram_val = getattr(virtual_record, fname, None)
            
            if meta.get('type') == 'one2many' and isinstance(ram_val, list):
                ram_children = []
                for child in ram_val:
                    if hasattr(child, '__dict__'):
                        child_dict = {}
                        for ck, cv in child.__dict__.items():
                            if not ck.startswith('_'): child_dict[ck] = cv
                        ram_children.append(child_dict)
                    elif isinstance(child, dict):
                        ram_children.append(child)
                db_serialized[fname] = ram_children
            elif meta.get('type') not in ('relation', 'many2one'):
                db_serialized[fname] = ram_val
                
        return db_serialized
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 🎯 ENDPOINTS DE UI Y BÚSQUEDA
# ==============================================================================

@router.get("/ui/menu")
async def get_menus(current_user_id: int = Depends(get_current_user)):
    try:
        session_graph = Model._graph.clone_for_session()
        env = Env(user_id=current_user_id, graph=session_graph)
        unique_menus = {}
        
        try:
            db_menus = await env['ir.ui.menu'].search([], context=session_graph)
            if db_menus:
                for m in await db_menus.read(['id', 'name', 'parent_id', 'action', 'icon', 'sequence', 'is_category']):
                    parent = m.get('parent_id')
                    if isinstance(parent, list): 
                        m['parent_id'] = parent[0] if len(parent) > 0 else None
                        
                    m['is_category'] = True if not m.get('parent_id') else False
                    key = str(m.get('id'))
                    unique_menus[key] = m
        except Exception as e: 
            pass

        for m in Registry.get_all_menus():
            key = str(m.get('id') or m.get('name', '')).upper().strip()
            if key not in unique_menus:
                m['is_category'] = True if not m.get('parent_id') else False
                unique_menus[key] = m
                
        return sorted(unique_menus.values(), key=lambda x: (x.get('sequence') or 100))
    except Exception as e: 
        return []


@router.get("/ui/view/{model_name}")
async def get_view_schema(model_name: str, view_type: str = 'form', current_user_id: int = Depends(get_current_user)):
    try: 
        view_id = f"{model_name}.{view_type}"
        custom_view = UIRegistry.get_view(view_id)
        if custom_view:
            return custom_view
            
        return await ViewScaffolder.get_default_view(model_name, view_type)
    except Exception as e: 
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/data/{model_name}/search")
async def search_data(model_name: str, payload: dict = Body(default={}), current_user_id: int = Depends(get_current_user)):
    try:
        session_graph = Model._graph.clone_for_session()
        env = Env(user_id=current_user_id, graph=session_graph)
        
        domain = payload.get('domain', [])
        limit = payload.get('limit', 80)
        offset = payload.get('offset', 0)
        order_by = payload.get('order_by', None)
        fields = payload.get('fields', None)

        if not fields:
            model_cls = Registry.get_model(model_name)
            fields = []
            for fname in dir(model_cls):
                attr = getattr(model_cls, fname, None)
                if hasattr(attr, 'get_meta'):
                    meta = attr.get_meta()
                    if meta.get('type') != 'one2many':
                        fields.append(fname)

        records = await env[model_name].search(
            domain=domain, 
            limit=limit, 
            offset=offset, 
            order_by=order_by, 
            context=session_graph
        )
        
        if len(records) < limit:
            total = offset + len(records)
        else:
            storage = PostgresGraphStorage()
            all_ids = await storage.search_domain(model_name, domain)
            total = len(all_ids)
        
        async def generate_json_stream():
            yield f'{{"total": {total}, "data": ['
            
            chunk_size = 500
            first = True
            
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i + chunk_size]
                serialized_chunk = await _serialize_records(env, chunk, model_name, fields=fields)
                
                for item in serialized_chunk:
                    if not first:
                        yield ','
                    yield json.dumps(item, default=str)
                    first = False
                    
            yield ']}'

        return StreamingResponse(generate_json_stream(), media_type="application/json")

    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/{model_name}/create")
async def create_data(model_name: str, vals: dict = Body(...), current_user_id: int = Depends(get_current_user)):
    try:
        async with transaction(): 
            session_graph = Model._graph.clone_for_session()
            env = Env(user_id=current_user_id, graph=session_graph)
            
            x2many_data, x2many_meta = extract_x2many_data(model_name, vals)
            safe_vals = _clean_m2o_payload(vals)
            
            if 'id' in safe_vals and not safe_vals['id']: del safe_vals['id']
                
            new_record = await env[model_name].create(safe_vals, context=session_graph)
            
            if x2many_data:
                await process_nested_records(env, model_name, new_record, x2many_data, x2many_meta)
                await new_record.write({})
                
            storage = PostgresGraphStorage()
            id_mapping = await storage.save(session_graph) 
            
            if str(new_record.id) in id_mapping:
                new_record._id_val = id_mapping[str(new_record.id)]
            
            return {"status": "success", "data": await _serialize_record(env, new_record, model_name)}
    except Exception as e:
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Error del Servidor: {str(e)}")


@router.post("/data/{model_name}/{record_id}/write")
async def write_data(model_name: str, record_id: int, vals: dict = Body(...), current_user_id: int = Depends(get_current_user)):
    try:
        async with transaction(): 
            session_graph = Model._graph.clone_for_session()
            env = Env(user_id=current_user_id, graph=session_graph)
            
            records = env[model_name].browse([record_id], context=session_graph)
            if not records: raise HTTPException(status_code=404, detail="Registro no encontrado")
            
            await records.load_data()
            
            x2many_data, x2many_meta = extract_x2many_data(model_name, vals)
            safe_vals = _clean_m2o_payload(vals)
            
            if 'id' in safe_vals: del safe_vals['id']
            
            await records[0].write(safe_vals)
            
            if x2many_data:
                await process_nested_records(env, model_name, records[0], x2many_data, x2many_meta)
                await records[0].write({})
                
            storage = PostgresGraphStorage()
            await storage.save(session_graph)
            
            return {"status": "success", "data": await _serialize_record(env, records[0], model_name)}
    except Exception as e:
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Error del Servidor: {str(e)}")


# ==============================================================================
# 🎯 EL INTERCEPTOR MAESTRO DE ACCIONES (El Atajo al Worker)
# ==============================================================================
@router.post("/data/{model_name}/{record_id}/call/{method}")
async def call_action(model_name: str, record_id: int, method: str, params: dict = Body(default={}), current_user_id: int = Depends(get_current_user)):
    print(f"\n🎯 [API] Frontend solicita ejecutar: {model_name}.{method}() -> ID: {record_id}")
    try:
        actual_method = method
        if "wrapper" in method.lower():
            if model_name in ['sale.order', 'sale_order']:
                if 'action_name' in params:
                    actual_method = params['action_name']
                else:
                    print("⚠️ [FIX] Acción corrupta detectada. Deduciendo intención...")
                    actual_method = "action_confirm" 
            print(f"🔧 [REDIRECCIÓN] Traducido de {method} -> a -> {actual_method}")

        if actual_method.endswith('_async'):
            params['record_id'] = record_id
            await WorkerEngine.enqueue(model_name=model_name, method_name=actual_method, kwargs=params)
            
            return {
                "status": "success", 
                "type": "notification", 
                "title": "Procesando Tarea", 
                "message": "La operación se está ejecutando en segundo plano en los servidores."
            }

        async with transaction(): 
            session_graph = Model._graph.clone_for_session()
            env = Env(user_id=current_user_id, graph=session_graph)
            
            records = env[model_name].browse([record_id], context=session_graph)
            if not records: raise HTTPException(status_code=404, detail="No encontrado")
            
            await records.load_data()
            
            if not hasattr(records[0], actual_method): 
                if hasattr(records[0], actual_method + '_async'):
                    actual_method = actual_method + '_async'
                else:
                    raise HTTPException(status_code=405, detail=f"Método '{actual_method}' no definido")
            
            print(f"⚡ [EJECUCIÓN] Disparando método real: {actual_method}")
            result = await getattr(records[0], actual_method)(**params)
            
            storage = PostgresGraphStorage()
            await storage.save(session_graph)
            
            return {"status": "success", "result": result, "data": await _serialize_record(env, records[0], model_name)}
    except Exception as e: 
        traceback.print_exc()
        if "[CONCURRENCY_CONFLICT]" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/data/{model_name}/{record_id}")
async def read_record(model_name: str, record_id: int, current_user_id: int = Depends(get_current_user)):
    try:
        session_graph = Model._graph.clone_for_session()
        env = Env(user_id=current_user_id, graph=session_graph)
        
        records = env[model_name].browse([record_id], context=session_graph)
        if not records: raise HTTPException(status_code=404, detail="No encontrado")
        
        return await _serialize_record(env, records[0], model_name)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.delete("/data/{model_name}/{record_id}")
async def delete_record(model_name: str, record_id: int, current_user_id: int = Depends(get_current_user)):
    try:
        async with transaction(): 
            session_graph = Model._graph.clone_for_session()
            env = Env(user_id=current_user_id, graph=session_graph)
            
            records = env[model_name].browse([record_id], context=session_graph)
            if not records: raise HTTPException(status_code=404, detail="No encontrado")
            
            await records.load_data()
            await records[0].unlink()
            
            storage = PostgresGraphStorage()
            await storage.save(session_graph)
            
            return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))