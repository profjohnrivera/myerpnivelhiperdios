# backend/modules/core_system/models/ir_model_data.py

import re
from typing import Optional, Any

from app.core.orm import Model, Field
from app.core.env import Context
from app.core.registry import Registry
from app.core.storage.postgres_storage import PostgresGraphStorage


class IrModelData(Model):
    """
    🔗 MAPA DE IDENTIFICADORES EXTERNOS (ir.model.data)

    Responsabilidades:
    - resolver XML-ID -> ID físico
    - resolver XML-ID -> objeto vivo
    - vincular / re-vincular XML-ID de forma idempotente
    - servir como base del data loader constitucional
    """
    _name = "ir.model.data"
    _rec_name = "name"

    _sql_constraints = [
        (
            "ir_model_data_unique_xmlid",
            'UNIQUE("module", "name")',
            "El XML-ID ya existe.",
        ),
    ]

    module = Field(type_="string", label="Módulo", required=True, index=True)
    name = Field(type_="string", label="ID Externo", required=True, index=True)
    model_name = Field(type_="string", label="Modelo Técnico", required=True, index=True)
    res_id = Field(type_="integer", label="ID Físico", required=True, index=True)
    noupdate = Field(type_="bool", default=False, label="No Actualizar")
    active = Field(type_="bool", default=True, label="Activo")

    @classmethod
    def _split_xmlid(cls, xml_id: str) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(xml_id, str) or "." not in xml_id:
            return None, None
        module, name = xml_id.split(".", 1)
        return module, name

    @classmethod
    def _get_cache(cls) -> dict:
        graph = Context.get_graph()
        if not graph:
            if not hasattr(cls, "_static_cache"):
                cls._static_cache = {}
            return cls._static_cache

        if not hasattr(graph, "_xmlid_cache"):
            graph._xmlid_cache = {}
        return graph._xmlid_cache

    @classmethod
    def _clear_cache_entry(cls, xml_id: str) -> None:
        cache = cls._get_cache()
        if xml_id in cache:
            del cache[xml_id]

    @classmethod
    async def get_mapping(cls, xml_id: str):
        module, name = cls._split_xmlid(xml_id)
        if not module or not name:
            return None

        rs = await cls.search(
            [("module", "=", module), ("name", "=", name), ("active", "=", True)],
            limit=1,
        )
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()
        return rs[0] if rs and len(rs) > 0 else None

    @classmethod
    async def get_id(cls, xml_id: str) -> Optional[int]:
        cache = cls._get_cache()
        if xml_id in cache:
            return cache[xml_id]

        mapping = await cls.get_mapping(xml_id)
        if not mapping:
            return None

        res_id = mapping.res_id
        cache[xml_id] = res_id
        return res_id

    @classmethod
    async def get_object(cls, xml_id: str) -> Optional[Any]:
        mapping = await cls.get_mapping(xml_id)
        if not mapping:
            return None

        model_name = mapping.model_name
        res_id = mapping.res_id

        ModelClass = Registry.get_model(model_name)
        if not ModelClass:
            return None

        rs = await ModelClass.search([("id", "=", res_id)], context=Context.get_graph(), limit=1)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        return rs[0] if rs and len(rs) > 0 else None

    @classmethod
    def set_cache(cls, xml_id: str, res_id: int) -> None:
        cache = cls._get_cache()
        cache[xml_id] = res_id

    @classmethod
    async def _resolve_physical_res_id(cls, res_id: Any) -> int:
        """
        Hace robusto bind_xmlid frente a IDs temporales new_xxx.
        """
        if str(res_id).isdigit():
            return int(res_id)

        graph = Context.get_graph()
        if not graph:
            raise ValueError(
                f"❌ No se puede resolver ID temporal sin graph activo: {res_id!r}"
            )

        storage = PostgresGraphStorage()
        id_map = await storage.save(graph)
        resolved = id_map.get(str(res_id), res_id)

        if not str(resolved).isdigit():
            raise ValueError(
                f"❌ No se pudo materializar el ID físico para XML-ID: {res_id!r}"
            )

        return int(resolved)

    @classmethod
    async def bind_xmlid(
        cls,
        xml_id: str,
        *,
        model_name: str,
        res_id: int,
        noupdate: bool = False,
    ):
        module, name = cls._split_xmlid(xml_id)
        if not module or not name:
            raise ValueError(f"XML-ID inválido: {xml_id}")

        real_res_id = await cls._resolve_physical_res_id(res_id)
        existing = await cls.get_mapping(xml_id)

        payload = {
            "module": module,
            "name": name,
            "model_name": model_name,
            "res_id": real_res_id,
            "noupdate": bool(noupdate),
            "active": True,
        }

        if existing:
            await existing.write(payload)
            record = existing
        else:
            record = await cls.create(payload)

        # Persistir inmediatamente el mapping para que sea visible
        storage = PostgresGraphStorage()
        await storage.save(Context.get_graph(), model_filter="ir.model.data")

        cls.set_cache(xml_id, real_res_id)
        return record

    @classmethod
    def is_xml_id(cls, value: str) -> bool:
        return isinstance(value, str) and bool(re.match(r"^[a-z0-9_]+\.[a-z0-9_]+$", value))

    async def unlink(self):
        xml_id = f"{self.module}.{self.name}"
        self._clear_cache_entry(xml_id)
        return await super().unlink()