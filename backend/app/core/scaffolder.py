# backend/app/core/scaffolder.py

import hashlib
import json
import traceback
from typing import List, Dict, Any

from app.core.registry import Registry


class ViewScaffolder:
    """
    🏗️ GENERADOR DE UI AUTOMÁTICO (Runtime oficial de vistas)

    Decisión arquitectónica definitiva:
    - El runtime REAL de vistas vive aquí.
    - ir.ui.view NO es la fuente canónica de ejecución.
    - ir.ui.view puede usarse como catálogo persistente / snapshot técnico,
      pero NO como override runtime automático.
    """

    TYPE_MAPPING = {
        "string": "TextInput",
        "text": "TextArea",
        "decimal": "NumberInput",
        "float": "NumberInput",
        "integer": "NumberInput",
        "int": "NumberInput",
        "monetary": "MonetaryInput",
        "bool": "BooleanSwitch",
        "selection": "SelectInput",
        "relation": "Many2OneLookup",
        "many2one": "Many2OneLookup",
        "one2many": "One2ManyLines",
        "many2many": "Many2ManyTags",
        "date": "DateInput",
        "datetime": "DateTimeInput",
        "password": "TextInput",
        "binary": "FileUploader",
        "image": "ImageUploader",
    }

    # Nunca dibujar como campos normales del formulario
    HIDDEN_FIELDS = {
        "id",
        "create_date",
        "write_date",
        "create_uid",
        "write_uid",
        "write_version",
        "parent_path",
        "x_ext",
        "active",
        "state",
    }

    # Almacén oficial de vistas explícitas runtime
    _explicit_views: List[Any] = []

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _build_view_key(model_name: str, view_type: str) -> str:
        return f"{model_name}.{view_type}"

    @staticmethod
    def _normalize_runtime_view(view_ast: Dict[str, Any], model_name: str, view_type: str) -> Dict[str, Any]:
        """
        Garantiza metadatos mínimos y consistentes en toda vista runtime.
        """
        normalized = dict(view_ast or {})
        normalized.setdefault("id", f"{model_name}.{view_type}")
        normalized.setdefault("model", model_name)
        normalized.setdefault("view_type", view_type)
        return normalized

    @staticmethod
    def _compute_checksum(view_ast: Dict[str, Any]) -> str:
        raw = json.dumps(view_ast or {}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def export_snapshot_record(
        cls,
        model_name: str,
        view_type: str,
        view_ast: Dict[str, Any],
        source: str,
        checksum: str | None = None,
        notes: str | None = None,
    ) -> Dict[str, Any]:
        """
        Construye el payload persistible para ir.ui.view.
        NO escribe en BD. Solo prepara el snapshot técnico.
        """
        normalized = cls._normalize_runtime_view(view_ast, model_name, view_type)
        view_key = cls._build_view_key(model_name, view_type)

        if checksum is None:
            checksum = cls._compute_checksum(normalized)

        return {
            "name": view_key,
            "view_key": view_key,
            "model_name": model_name,
            "type": view_type,
            "arch": json.dumps(normalized, ensure_ascii=False),
            "source": source,
            "runtime_role": "snapshot",
            "checksum": checksum,
            "priority": 16,
            "notes": notes or "",
            "active": True,
        }

    # =========================================================================
    # REGISTRO DE VISTAS EXPLÍCITAS
    # =========================================================================

    @classmethod
    def register_view(cls, view_instance):
        """
        Registra una vista explícita en código como fuente runtime oficial.
        Idempotente por model + view_type + id.
        """
        model_name = getattr(view_instance, "model", None)
        view_type = getattr(view_instance, "view_type", "form")
        view_id = getattr(view_instance, "id", None)

        for existing in cls._explicit_views:
            if (
                getattr(existing, "model", None) == model_name
                and getattr(existing, "view_type", "form") == view_type
                and getattr(existing, "id", None) == view_id
            ):
                return

        cls._explicit_views.append(view_instance)
        print(f"✅ [SDUI] Vista explícita registrada para: {model_name}::{view_type}")

    # =========================================================================
    # RUNTIME OFICIAL DE VISTAS
    # =========================================================================

    @classmethod
    async def get_runtime_view(cls, model_name: str, view_type: str = "form") -> Dict[str, Any]:
        """
        Runtime oficial de vistas.

        Orden:
        1. vista explícita en código
        2. vista implícita generada

        Regla dura:
        - NO consulta ir.ui.view como override automático
        - NO escribe snapshots automáticamente en la ruta de lectura
        """
        try:
            # 1. Vista explícita en código
            for view_instance in cls._explicit_views:
                if (
                    getattr(view_instance, "model", "") == model_name
                    and getattr(view_instance, "view_type", "form") == view_type
                ):
                    print(f"🎨 [SDUI] Sirviendo Vista Explícita para: {model_name}")
                    compiled = view_instance.compile()
                    return cls._normalize_runtime_view(compiled, model_name, view_type)

            # 2. Vista implícita generada
            print(f"🏗️ [SDUI] Generando Vista Implícita/Hardcodeada para: {model_name}")
            built = await cls._build_view(model_name, view_type)
            return cls._normalize_runtime_view(built, model_name, view_type)

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"\n🔥 CRASH EN SCAFFOLDER ({model_name}):\n{error_trace}")

            return {
                "id": f"{model_name}.{view_type}.error",
                "model": model_name,
                "view_type": view_type,
                "type": "Container",
                "props": {"layout": "col", "gap": 4, "padding": 6, "border": True},
                "children": [
                    {
                        "type": "Typography",
                        "props": {
                            "content": "🔥 500 Internal Server Error (Scaffolder)",
                            "variant": "h2",
                            "color": "red-600",
                        },
                    },
                    {
                        "type": "Typography",
                        "props": {
                            "content": str(e),
                            "weight": "bold",
                            "color": "red-800",
                        },
                    },
                    {
                        "type": "TextArea",
                        "props": {"name": "trace", "readonly": True},
                        "data": {"trace": error_trace},
                    },
                ],
            }

    @classmethod
    async def get_default_view(cls, model_name: str, view_type: str = "form") -> Dict[str, Any]:
        """
        Alias conservado por compatibilidad.
        """
        return await cls.get_runtime_view(model_name, view_type)

    # =========================================================================
    # GENERADOR IMPLÍCITO
    # =========================================================================

    @classmethod
    async def _build_view(cls, model_name: str, view_type: str) -> Dict[str, Any]:
        try:
            behaviors = Registry.get_behaviors(model_name)
        except AttributeError:
            behaviors = []

        fields_meta = Registry.get_fields_for_model(model_name)

        if not fields_meta:
            return {
                "type": "Typography",
                "props": {
                    "content": f"Error: No hay metadatos para {model_name}",
                    "color": "red-600",
                },
            }

        is_sale = model_name in ["sale.order", "sale_order"]

        # =====================================================================
        # ACCIONES GLOBALES DEL MODELO
        # =====================================================================
        model_actions = []
        model_cls = Registry.get_model(model_name)
        if model_cls:
            for attr_name in dir(model_cls):
                attr = getattr(model_cls, attr_name)
                if hasattr(attr, "_action_meta"):
                    meta = dict(attr._action_meta)
                    meta["name"] = attr_name
                    meta["method"] = attr_name
                    meta["action"] = attr_name
                    model_actions.append(meta)

        # =====================================================================
        # VISTA DE LISTA
        # =====================================================================
        if view_type == "list":
            if is_sale:
                columns = [
                    {"field": "name", "label": "Número", "type": "TextInput"},
                    {"field": "create_date", "label": "Fecha de creación", "type": "DateInput"},
                    {"field": "partner_id", "label": "Cliente", "type": "Many2OneLookup"},
                    {"field": "user_id", "label": "Vendedor", "type": "Avatar"},
                    {"field": "activity_ids", "label": "Actividades", "type": "Activity"},
                    {"field": "company_id", "label": "Empresa", "type": "Many2OneLookup"},
                    {"field": "amount_total", "label": "Total", "type": "MonetaryInput"},
                    {"field": "state", "label": "Estado", "type": "Badge"},
                ]
            else:
                columns = []
                for f_name, f_meta in fields_meta.items():
                    if f_name in cls.HIDDEN_FIELDS:
                        continue

                    meta_dict = f_meta if isinstance(f_meta, dict) else {}
                    raw_type = meta_dict.get("type", "string")

                    columns.append(
                        {
                            "field": f_name,
                            "label": meta_dict.get("label", f_name.title()),
                            "type": cls.TYPE_MAPPING.get(raw_type, "TextInput"),
                        }
                    )

            return {
                "type": "Container",
                "props": {"layout": "col", "gap": 4, "padding": 4},
                "children": [
                    {
                        "type": "DataGrid",
                        "props": {
                            "key": f"grid_{model_name.replace('.', '_')}",
                            "data_source": f"data_{model_name.replace('.', '_')}",
                            "columns": columns[:8],
                            "title": (
                                "Cotizaciones"
                                if is_sale
                                else f"Listado de {model_name.replace('.', ' ').title()}"
                            ),
                        },
                    }
                ],
                "actions": model_actions,
            }

        # =====================================================================
        # VISTA DE FORMULARIO
        # =====================================================================
        header_components = []
        body_children = []
        table_components = []
        footer_components = []

        has_state = "state" in fields_meta
        if (has_state or is_sale or "aprobable" in behaviors) and view_type == "form":
            if is_sale:
                statusbar_options = [
                    ["draft", "Cotización"],
                    ["sent", "Cotización Enviada"],
                    ["sale", "Orden de Venta"],
                    ["done", "Bloqueado"],
                    ["cancel", "Cancelado"],
                ]
            else:
                statusbar_options = [
                    ["draft", "Borrador"],
                    ["waiting", "En Espera"],
                    ["approved", "Aprobado"],
                    ["rejected", "Rechazado"],
                ]

            header_components.append(
                {
                    "type": "StatusBar",
                    "props": {
                        "field": "state",
                        "options": statusbar_options,
                    },
                }
            )

        if is_sale:
            body_children = [
                {
                    "type": "Group",
                    "props": {},
                    "children": [
                        {
                            "type": "Container",
                            "props": {"layout": "col", "gap": 1},
                            "children": [
                                {
                                    "type": "Many2OneLookup",
                                    "props": {
                                        "name": "partner_id",
                                        "label": "Cliente",
                                        "placeholder": "Comience a escribir para encontrar a un cliente...",
                                    },
                                },
                                {
                                    "type": "Many2OneLookup",
                                    "props": {
                                        "name": "sale_order_template_id",
                                        "label": "Plantilla de cotización",
                                    },
                                },
                            ],
                        },
                        {
                            "type": "Container",
                            "props": {"layout": "col", "gap": 1},
                            "children": [
                                {
                                    "type": "DateInput",
                                    "props": {"name": "validity_date", "label": "Vencimiento"},
                                },
                                {
                                    "type": "Many2OneLookup",
                                    "props": {"name": "payment_term_id", "label": "Términos de pago"},
                                },
                            ],
                        },
                    ],
                },
                {
                    "type": "Notebook",
                    "props": {"tabs": ["Líneas de la orden", "Otra información"]},
                    "children": [
                        {
                            "type": "Container",
                            "props": {"layout": "col", "gap": 0},
                            "children": [
                                {
                                    "type": "One2ManyLines",
                                    "props": {"name": "order_line", "data_source": "order_line"},
                                }
                            ],
                        },
                        {
                            "type": "Container",
                            "props": {"layout": "grid", "gap": 8, "padding": 4},
                            "children": [
                                {
                                    "type": "Container",
                                    "props": {"layout": "col", "gap": 2},
                                    "children": [
                                        {
                                            "type": "Typography",
                                            "props": {
                                                "content": "Ventas",
                                                "variant": "h2",
                                                "color": "slate-800",
                                            },
                                        },
                                        {
                                            "type": "Many2OneLookup",
                                            "props": {"name": "user_id", "label": "Vendedor"},
                                        },
                                        {
                                            "type": "Many2OneLookup",
                                            "props": {"name": "company_id", "label": "Empresa"},
                                        },
                                        {
                                            "type": "Many2ManyTags",
                                            "props": {"name": "tag_ids", "label": "Etiquetas"},
                                        },
                                    ],
                                },
                                {
                                    "type": "Container",
                                    "props": {"layout": "col", "gap": 2},
                                    "children": [
                                        {
                                            "type": "Typography",
                                            "props": {
                                                "content": "Facturación y Seguimiento",
                                                "variant": "h2",
                                                "color": "slate-800",
                                            },
                                        },
                                        {
                                            "type": "TextInput",
                                            "props": {
                                                "name": "client_order_ref",
                                                "label": "Referencia del cliente",
                                            },
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ]
        else:
            generic_fields = []

            for f_name, f_meta in fields_meta.items():
                if f_name in cls.HIDDEN_FIELDS:
                    continue

                meta_dict = f_meta if isinstance(f_meta, dict) else {}
                raw_type = meta_dict.get("type", "string")
                comp_type = cls.TYPE_MAPPING.get(raw_type, "TextInput")
                comodel = meta_dict.get("comodel") or meta_dict.get("target")

                atom_props = {
                    "name": f_name,
                    "label": meta_dict.get("label", f_name.title()),
                    "options": meta_dict.get("options", []),
                }

                if comp_type in ["One2ManyLines", "DataGrid"]:
                    atom_props["data_source"] = f_name
                    atom_props["comodel"] = comodel

                    inverse = meta_dict.get("inverse_name", "")
                    atom_props["inverse_name"] = inverse

                    if comodel:
                        child_fields = Registry.get_fields_for_model(comodel)
                        if child_fields:
                            child_columns = []
                            for cf_name, cf_meta in child_fields.items():
                                if cf_name in cls.HIDDEN_FIELDS or cf_name == inverse:
                                    continue

                                c_meta = cf_meta if isinstance(cf_meta, dict) else {}
                                child_type = cls.TYPE_MAPPING.get(c_meta.get("type", "string"), "TextInput")
                                child_column = {
                                    "field": cf_name,
                                    "label": c_meta.get("label", cf_name.title()),
                                    "type": child_type,
                                }

                                child_target = c_meta.get("comodel") or c_meta.get("target")
                                if child_type == "Many2OneLookup" and child_target:
                                    child_column["comodel"] = child_target

                                child_columns.append(child_column)

                            atom_props["columns"] = child_columns

                    table_components.append({"type": comp_type, "props": atom_props})

                elif comp_type == "Many2OneLookup":
                    atom_props["comodel"] = comodel
                    generic_fields.append({"type": comp_type, "props": atom_props})

                elif comp_type == "Many2ManyTags":
                    atom_props["comodel"] = comodel
                    generic_fields.append({"type": comp_type, "props": atom_props})

                else:
                    generic_fields.append({"type": comp_type, "props": atom_props})

            body_children = [
                {"type": "Group", "props": {}, "children": generic_fields},
                *table_components,
            ]

        if "trazable" in behaviors and view_type == "form":
            footer_components.append(
                {
                    "type": "Chatter",
                    "props": {"res_model": model_name},
                }
            )

        final_children = []
        final_children.extend(header_components)
        final_children.append(
            {
                "type": "Card",
                "props": {},
                "children": body_children,
            }
        )
        final_children.extend(footer_components)

        return {
            "type": "Container",
            "props": {"layout": "col", "gap": 0, "padding": 0, "border": False},
            "children": final_children,
            "actions": model_actions,
        }