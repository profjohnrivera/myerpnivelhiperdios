# backend/app/api/v1/ui.py

from fastapi import APIRouter, HTTPException, Depends

from app.core.scaffolder import ViewScaffolder
from app.core.security import get_current_user
from app.core.storage.postgres_storage import PostgresGraphStorage

from .runtime import request_env

router = APIRouter()


@router.get("/ui/menu")
async def get_menus(current_user_id: int = Depends(get_current_user)):
    """
    ÚNICA FUENTE DE VERDAD:
    - ir.ui.menu persistido en BD

    PROHIBIDO:
    - mezclar con Registry.get_all_menus()
    - reconstruir navegación desde memoria del proceso
    """
    try:
        async with request_env(current_user_id) as (env, session_graph):
            user_group_ids: set[int] = set()
            is_admin = False

            try:
                _storage = PostgresGraphStorage()
                _conn = await _storage.get_connection()

                admin_row = await _conn.fetchrow(
                    '''SELECT 1
                       FROM "res_users_group_ids_rel" rug
                       JOIN "res_groups" g ON g.id = rug.rel_id
                       WHERE rug.base_id = $1 AND g.is_system_admin = TRUE
                       LIMIT 1''',
                    int(current_user_id),
                )
                is_admin = bool(admin_row)

                rows = await _conn.fetch(
                    'SELECT rel_id FROM "res_users_group_ids_rel" WHERE base_id = $1',
                    int(current_user_id),
                )
                user_group_ids = {int(r["rel_id"]) for r in rows}
            except Exception:
                # Fallback conservador: si falla el cálculo de permisos,
                # no exponemos lógica híbrida ni inventamos menús.
                is_admin = True

            db_menus = await env["ir.ui.menu"].search([], context=session_graph)
            if not db_menus:
                return []

            result = []
            for m in await db_menus.read(
                ["id", "name", "parent_id", "action", "icon", "sequence", "is_category", "group_ids"]
            ):
                parent = m.get("parent_id")
                if isinstance(parent, list):
                    m["parent_id"] = parent[0] if parent else None

                m["is_category"] = bool(m.get("is_category")) or not m.get("parent_id")

                if not is_admin:
                    menu_groups = m.get("group_ids") or []
                    mg_ids: set[int] = set()

                    for g in menu_groups:
                        if isinstance(g, (int, float)):
                            mg_ids.add(int(g))
                        elif isinstance(g, (list, tuple)) and g:
                            mg_ids.add(int(g[0]))
                        elif isinstance(g, dict) and g.get("id"):
                            mg_ids.add(int(g["id"]))

                    # Si el menú tiene grupos y el usuario no pertenece a ninguno, ocultarlo.
                    if mg_ids and not mg_ids.intersection(user_group_ids):
                        continue

                m.pop("group_ids", None)
                result.append(m)

            return sorted(result, key=lambda x: (x.get("sequence") or 100, x.get("id") or 0))
    except Exception:
        return []


@router.get("/ui/view/{model_name}")
async def get_view_schema(
    model_name: str,
    view_type: str = "form",
    current_user_id: int = Depends(get_current_user),
):
    try:
        return await ViewScaffolder.get_default_view(model_name, view_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))