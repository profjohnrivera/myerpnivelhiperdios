# backend/app/core/data_loader.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.env import Env
from app.core.storage.postgres_storage import PostgresGraphStorage


class ModuleDataLoader:
    """
    Loader idempotente por XML-ID.

    Reglas:
    - cada dato técnico/base debe tener XML-ID estable
    - si el XML-ID existe -> reutiliza y actualiza
    - si no existe -> puede adoptar por lookup_domain
    - si crea un registro nuevo, primero lo materializa a ID físico
      y recién después vincula el XML-ID
    - toda vinculación XML-ID se persiste inmediatamente
    """

    def __init__(self, env: Env, module_name: str):
        self.env = env
        self.module_name = module_name
        self.storage = PostgresGraphStorage()

    def _qualify(self, xml_name_or_full: str) -> str:
        if "." in xml_name_or_full:
            return xml_name_or_full
        return f"{self.module_name}.{xml_name_or_full}"

    async def _flush_graph(self, model_filter: Optional[str] = None) -> Dict[str, int]:
        return await self.storage.save(self.env.graph, model_filter=model_filter)

    async def _resolve_physical_id(self, record_or_id: Any) -> int:
        """
        Convierte una identidad temporal new_xxx en ID físico real.
        """
        raw_id = record_or_id.id if hasattr(record_or_id, "id") else record_or_id

        if str(raw_id).isdigit():
            return int(raw_id)

        id_map = await self._flush_graph()
        resolved = id_map.get(str(raw_id), raw_id)

        if not str(resolved).isdigit():
            raise ValueError(
                f"❌ No se pudo materializar el ID físico del registro: {raw_id!r}"
            )

        return int(resolved)

    async def _refresh_record(self, model_name: str, res_id: int):
        ModelClass = self.env[model_name]
        rs = await ModelClass.search([("id", "=", int(res_id))], limit=1)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()
        return rs[0] if rs and len(rs) > 0 else None

    async def ref(self, xml_name_or_full: str):
        IrModelData = self.env["ir.model.data"]
        return await IrModelData.get_object(self._qualify(xml_name_or_full))

    async def ref_id(self, xml_name_or_full: str) -> Optional[int]:
        IrModelData = self.env["ir.model.data"]
        return await IrModelData.get_id(self._qualify(xml_name_or_full))

    @staticmethod
    def _normalize_compare(value: Any) -> Any:
        if hasattr(value, "id"):
            return value.id
        if isinstance(value, list):
            return [ModuleDataLoader._normalize_compare(v) for v in value]
        return value

    async def _write_if_needed(self, record: Any, values: Dict[str, Any]) -> bool:
        changed: Dict[str, Any] = {}

        for key, new_value in (values or {}).items():
            try:
                current_value = getattr(record, key, None)
            except Exception:
                current_value = None

            if self._normalize_compare(current_value) != self._normalize_compare(new_value):
                changed[key] = new_value

        if changed:
            await record.write(changed)
            return True

        return False

    async def ensure_record(
        self,
        xml_name: str,
        model_name: str,
        values: Dict[str, Any],
        *,
        lookup_domain: Optional[List] = None,
        noupdate: bool = False,
    ):
        """
        Upsert idempotente por XML-ID.

        Orden:
        1. si existe XML-ID -> reutiliza
        2. si no, intenta adoptar por lookup_domain
        3. si no existe nada -> crea
        4. si creó con ID temporal -> materializa
        5. vincula XML-ID
        6. devuelve registro refrescado
        """
        IrModelData = self.env["ir.model.data"]
        ModelClass = self.env[model_name]
        full_xmlid = self._qualify(xml_name)

        mapping = await IrModelData.get_mapping(full_xmlid)
        target = await IrModelData.get_object(full_xmlid)

        if target:
            mapping_noupdate = bool(mapping and getattr(mapping, "noupdate", False))
            if not mapping_noupdate:
                changed = await self._write_if_needed(target, values)
                if changed:
                    await self._flush_graph(model_filter=model_name)

            await IrModelData.bind_xmlid(
                full_xmlid,
                model_name=model_name,
                res_id=target.id,
                noupdate=noupdate or mapping_noupdate,
            )
            refreshed = await IrModelData.get_object(full_xmlid)
            return refreshed or target

        adopted = None
        if lookup_domain:
            rs = await ModelClass.search(lookup_domain, limit=1)
            if rs and hasattr(rs, "load_data"):
                await rs.load_data()
            if rs and len(rs) > 0:
                adopted = rs[0]

        if adopted:
            if not (mapping and getattr(mapping, "noupdate", False)):
                changed = await self._write_if_needed(adopted, values)
                if changed:
                    await self._flush_graph(model_filter=model_name)

            await IrModelData.bind_xmlid(
                full_xmlid,
                model_name=model_name,
                res_id=adopted.id,
                noupdate=noupdate,
            )
            refreshed = await IrModelData.get_object(full_xmlid)
            return refreshed or adopted

        created = await ModelClass.create(values)
        real_id = await self._resolve_physical_id(created)

        await IrModelData.bind_xmlid(
            full_xmlid,
            model_name=model_name,
            res_id=real_id,
            noupdate=noupdate,
        )

        refreshed = await self._refresh_record(model_name, real_id)
        return refreshed or created

    async def ensure_menu(
        self,
        xml_name: str,
        values: Dict[str, Any],
        *,
        lookup_domain: Optional[List] = None,
        noupdate: bool = False,
    ):
        return await self.ensure_record(
            xml_name=xml_name,
            model_name="ir.ui.menu",
            values=values,
            lookup_domain=lookup_domain,
            noupdate=noupdate,
        )

    async def ensure_action_window(
        self,
        xml_name: str,
        values: Dict[str, Any],
        *,
        lookup_domain: Optional[List] = None,
        noupdate: bool = False,
    ):
        return await self.ensure_record(
            xml_name=xml_name,
            model_name="ir.actions.act_window",
            values=values,
            lookup_domain=lookup_domain,
            noupdate=noupdate,
        )

    async def ensure_action_server(
        self,
        xml_name: str,
        values: Dict[str, Any],
        *,
        lookup_domain: Optional[List] = None,
        noupdate: bool = False,
    ):
        return await self.ensure_record(
            xml_name=xml_name,
            model_name="ir.actions.server",
            values=values,
            lookup_domain=lookup_domain,
            noupdate=noupdate,
        )