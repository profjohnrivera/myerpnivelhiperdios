# backend/app/api/v1/ui.py

from fastapi import APIRouter, HTTPException, Depends

from app.core.scaffolder import ViewScaffolder
from app.core.security import get_current_user
from app.core.registry import Registry

from .runtime import request_env

router = APIRouter()


def _extract_group_ids(raw_groups) -> set[int]:
    """
    Normaliza distintos formatos posibles de group_ids:
    - [1, 2]
    - [[1, "Admin"], [2, "Ventas"]]
    - [{"id": 1}, {"id": 2}]
    """
    result: set[int] = set()

    for item in raw_groups or []:
        try:
            if isinstance(item, (int, float)):
                result.add(int(item))
            elif isinstance(item, (list, tuple)) and item:
                if str(item[0]).isdigit():
                    result.add(int(item[0]))
            elif isinstance(item, dict) and item.get("id") is not None:
                if str(item["id"]).isdigit():
                    result.add(int(item["id"]))
        except Exception:
            continue

    return result


@router.get("/ui/menu")
async def get_menus(current_user_id: int = Depends(get_current_user)):
    """
    Fuente única de verdad:
    - ir.ui.menu persistido en BD

    Cierre de seguridad:
    - criterio admin unificado con ir.rule._is_admin_user()
    - fail-closed si falla el cálculo de permisos
    - sin SQL directo en el endpoint
    """
    try:
        async with request_env(current_user_id) as (env, session_graph):
            IrRuleModel = Registry.get_model("ir.rule")
            if not IrRuleModel:
                raise HTTPException(status_code=500, detail="Modelo ir.rule no disponible")

            # =========================================================
            # Cálculo de permisos de menú — FAIL CLOSED
            # =========================================================
            is_admin = False
            user_group_ids: set[int] = set()

            try:
                is_admin = await IrRuleModel._is_admin_user(current_user_id)
                if not is_admin:
                    user_group_ids = set(await IrRuleModel._user_group_ids(current_user_id))
            except Exception:
                # Fallo de permisos => no elevar privilegios
                is_admin = False
                user_group_ids = set()

            # =========================================================
            # Lectura canónica de menús desde el dominio
            # =========================================================
            menus_rs = await env["ir.ui.menu"].search([], context=session_graph)
            if not menus_rs:
                return []

            rows = await menus_rs.read(
                fields=[
                    "id",
                    "name",
                    "parent_id",
                    "action",
                    "icon",
                    "sequence",
                    "is_category",
                    "group_ids",
                ]
            )

            result = []

            for row in rows:
                parent = row.get("parent_id")
                if isinstance(parent, list):
                    row["parent_id"] = parent[0] if parent else None

                row["is_category"] = bool(row.get("is_category")) or not row.get("parent_id")

                if not is_admin:
                    menu_group_ids = _extract_group_ids(row.get("group_ids") or [])
                    if menu_group_ids and not (menu_group_ids & user_group_ids):
                        continue

                row.pop("group_ids", None)
                result.append(row)

            return sorted(result, key=lambda x: (x.get("sequence") or 100, x.get("id") or 0))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo menús: {str(e)}")


@router.get("/ui/view/{model_name}")
async def get_view_schema(
    model_name: str,
    view_type: str = "form",
    current_user_id: int = Depends(get_current_user),
):
    """
    Runtime de vistas:
    - explícita si existe en código
    - implícita/scaffold si no existe explícita
    """
    try:
        return await ViewScaffolder.get_default_view(model_name, view_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))