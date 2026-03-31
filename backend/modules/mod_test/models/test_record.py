# backend/modules/mod_test/models/test_record.py

from app.core.orm import (
    Model, Field, SelectionField, One2manyField,
    RelationField, Many2manyField, check_state,
)
from app.core.decorators import action
from app.core.env import Context


class TestRecord(Model):
    """
    🧪 REGISTRO DE LABORATORIO — Modelo maestro de demostración HiperDios.

    Además de cubrir tipos de campo, este modelo expone métodos controlados
    para la suite constitucional del Worker/Queue.
    """
    _name = "test.record"
    _rec_name = "name"

    # ── 1. Textos y Básicos ──────────────────────────────────────────────────
    name = Field(type_="string", label="Nombre del Experimento", required=True)
    description = Field(type_="text", label="Descripción detallada")
    is_active = Field(type_="bool", default=True, label="Está Activo")

    # ── 2. Selectores y Estados ──────────────────────────────────────────────
    status = SelectionField(
        options=[("draft", "Borrador"), ("done", "Completado")],
        default="draft",
        label="Estado",
    )
    priority = SelectionField(
        options=[("low", "Baja"), ("normal", "Normal"), ("high", "Alta")],
        default="normal",
        label="Prioridad",
    )

    # ── 3. Fechas ────────────────────────────────────────────────────────────
    start_date = Field(type_="date", label="Fecha de Inicio")
    end_datetime = Field(type_="datetime", label="Fecha y Hora de Fin")

    # ── 4. Números ───────────────────────────────────────────────────────────
    test_integer = Field(type_="integer", label="Número Entero")
    test_float = Field(type_="float", label="Número Decimal")
    test_money = Field(type_="monetary", label="Monto Monetario")

    # ── 5. Archivos ──────────────────────────────────────────────────────────
    document = Field(type_="binary", label="Documento Adjunto")
    image_1920 = Field(type_="image", label="Imagen Principal")

    # ── 6. Relaciones ────────────────────────────────────────────────────────
    user_id = RelationField("res.users", label="Responsable")
    line_ids = One2manyField("test.line", inverse_name="record_id", label="Líneas de Prueba")
    tag_ids = Many2manyField("test.tag", label="Etiquetas de Clasificación")

    # ── Acciones UI ──────────────────────────────────────────────────────────
    @action(label="Confirmar", icon="check", variant="primary")
    @check_state(["draft"])
    async def action_confirm(self):
        print(f"⚡ [LABORATORIO] Confirmando experimento: {self.name}")
        await self.write({"status": "done"})

    # =========================================================================
    # HELPERS CONSTITUCIONALES PARA WORKER / QUEUE
    # =========================================================================

    @staticmethod
    async def _set_param(key: str, value: str, group: str = "worker_tests"):
        env = Context.get_env()
        ICP = env["ir.config_parameter"]

        rs = await ICP.search([("key", "=", key)], limit=1)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        if rs and len(rs) > 0:
            await rs[0].write({"value": value, "group": group})
        else:
            await ICP.create({"key": key, "value": value, "group": group})

    @staticmethod
    async def _get_param(key: str, default: str = None) -> str:
        env = Context.get_env()
        ICP = env["ir.config_parameter"]

        rs = await ICP.search([("key", "=", key)], limit=1)
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        if rs and len(rs) > 0:
            return rs[0].value
        return default

    @classmethod
    async def worker_create_probe(cls, name: str, description: str = "") -> int:
        """
        Job exitoso de clase:
        crea un registro real para probar que el worker persiste job_env.graph.
        """
        rec = await cls.create({
            "name": name,
            "description": description,
            "status": "draft",
        })
        return rec.id

    @classmethod
    async def worker_capture_context(cls, key: str) -> str:
        """
        Guarda evidencia del contexto técnico del worker.
        """
        env = Context.get_env()
        uid = getattr(env, "uid", getattr(env, "user_id", None))
        su = bool(getattr(env, "su", False))
        disable_audit = bool(getattr(env, "context", {}).get("disable_audit"))

        payload = f"uid={uid}|su={int(su)}|audit={int(disable_audit)}"
        await cls._set_param(key, payload)
        return payload

    @classmethod
    async def worker_fail_once(cls, marker: str) -> int:
        """
        Falla la primera vez y pasa la segunda.
        """
        key = f"worker.fail_once.{marker}"
        result_key = f"worker.result.{marker}"

        current = await cls._get_param(key, "0")
        count = int(current or "0") + 1
        await cls._set_param(key, str(count))

        if count == 1:
            raise RuntimeError("planned first failure")

        await cls._set_param(result_key, "ok")
        return count

    @classmethod
    async def worker_fail_always(cls, marker: str) -> int:
        """
        Siempre falla y cuenta intentos.
        """
        key = f"worker.fail_always.{marker}"
        current = await cls._get_param(key, "0")
        count = int(current or "0") + 1
        await cls._set_param(key, str(count))
        raise RuntimeError("planned permanent failure")

    async def worker_mark_done(self, description: str = "done by worker") -> bool:
        """
        Job sobre registro existente para validar binding por record_id.
        """
        await self.write({
            "description": description,
            "status": "done",
        })
        return True