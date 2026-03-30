# backend/app/core/scaffolder.py

import hashlib
import json
import traceback
from typing import List, Dict, Any, Tuple

from app.core.registry import Registry


class ViewScaffolder:
    """
    🏗️ GENERADOR DE UI AUTOMÁTICO (Runtime oficial de vistas)

    Decisión arquitectónica definitiva:
    - El runtime REAL de vistas vive aquí.
    - ir.ui.view NO es la fuente canónica de ejecución.
    - ir.ui.view puede usarse como catálogo persistente / snapshot técnico,
      pero NO como override runtime automático.

    CIERRE SDUI ↔ MODELO:
    - Toda vista explícita o implícita se valida contra el metamodelo.
    - La validación usa runtime_fields del Registry.
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

    FIELD_COMPONENT_COMPAT = {
        "TextInput": {"string", "text", "password"},
        "TextArea": {"text"},
        "NumberInput": {"integer", "int", "float", "decimal"},
        "MonetaryInput": {"monetary", "float", "decimal"},
        "BooleanSwitch": {"bool"},
        "SelectInput": {"selection"},
        "Many2OneLookup": {"relation", "many2one"},
        "One2ManyLines": {"one2many"},
        "Many2ManyTags": {"many2many"},
        "DateInput": {"date", "datetime"},
        "DateTimeInput": {"datetime"},
        "FileUploader": {"binary"},
        "ImageUploader": {"image"},
        "StatusBar": {"selection"},
        "ModelStatusBar": {"selection"},
        "Badge": {"selection", "string"},
    }

    CONTAINER_TYPES = {
        "Container",
        "HeaderBar",
        "Card",
        "Group",
        "Notebook",
        "Typography",
        "Button",
        "Chatter",
        "ModelActions",
    }

    _explicit_views: List[Any] = []

    @staticmethod
    def _build_view_key(model_name: str, view_type: str) -> str:
        return f"{model_name}.{view_type}"

    @staticmethod
    def _normalize_runtime_view(view_ast: Dict[str, Any], model_name: str, view_type: str) -> Dict[str, Any]:
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

    @classmethod
    def _get_model_field_map(cls, model_name: str) -> Dict[str, Dict[str, Any]]:
        return Registry.get_runtime_fields_for_model(model_name) or {}

    @classmethod
    def _validate_component_field(
        cls,
        *,
        model_name: str,
        component_type: str,
        field_name: str,
        props: Dict[str, Any],
        path: str,
        errors: List[str],
    ) -> None:
        fields_meta = cls._get_model_field_map(model_name)
        if field_name not in fields_meta:
            errors.append(f"{path}: el campo '{field_name}' no existe en modelo '{model_name}'.")
            return

        meta = fields_meta[field_name]
        field_type = meta.get("type", "string")
        allowed_types = cls.FIELD_COMPONENT_COMPAT.get(component_type)

        if allowed_types and field_type not in allowed_types:
            errors.append(
                f"{path}: el componente '{component_type}' no es compatible con "
                f"'{model_name}.{field_name}' ({field_type})."
            )

        if component_type in {"Many2OneLookup", "Many2ManyTags"}:
            expected_target = meta.get("target") or meta.get("relation") or meta.get("comodel")
            given_target = props.get("comodel")
            if expected_target and given_target and str(expected_target) != str(given_target):
                errors.append(
                    f"{path}: comodel inválido para '{model_name}.{field_name}'. "
                    f"Esperado '{expected_target}', recibido '{given_target}'."
                )

        if component_type == "One2ManyLines":
            expected_target = meta.get("target") or meta.get("relation") or meta.get("comodel")
            given_target = props.get("comodel")
            if expected_target and given_target and str(expected_target) != str(given_target):
                errors.append(
                    f"{path}: comodel inválido para '{model_name}.{field_name}'. "
                    f"Esperado '{expected_target}', recibido '{given_target}'."
                )

            expected_inverse = meta.get("inverse_name")
            given_inverse = props.get("inverse_name")
            if expected_inverse and given_inverse and str(expected_inverse) != str(given_inverse):
                errors.append(
                    f"{path}: inverse_name inválido para '{model_name}.{field_name}'. "
                    f"Esperado '{expected_inverse}', recibido '{given_inverse}'."
                )

            child_model = expected_target or given_target
            if child_model:
                child_fields = cls._get_model_field_map(child_model)
                for i, col in enumerate(props.get("columns", []) or []):
                    col_field = col.get("field")
                    col_type = col.get("type")
                    col_path = f"{path}.columns[{i}]"

                    if not col_field:
                        errors.append(f"{col_path}: columna sin 'field'.")
                        continue

                    if col_field not in child_fields:
                        errors.append(
                            f"{col_path}: el campo '{col_field}' no existe en modelo hijo '{child_model}'."
                        )
                        continue

                    cmeta = child_fields[col_field]
                    ctype = cmeta.get("type", "string")
                    allowed_child_types = cls.FIELD_COMPONENT_COMPAT.get(col_type)
                    if allowed_child_types and ctype not in allowed_child_types:
                        errors.append(
                            f"{col_path}: tipo de componente '{col_type}' incompatible con "
                            f"'{child_model}.{col_field}' ({ctype})."
                        )

                    if col_type == "Many2OneLookup":
                        expected_child_target = cmeta.get("target") or cmeta.get("relation") or cmeta.get("comodel")
                        given_child_target = col.get("comodel")
                        if expected_child_target and given_child_target and str(expected_child_target) != str(given_child_target):
                            errors.append(
                                f"{col_path}: comodel inválido para '{child_model}.{col_field}'. "
                                f"Esperado '{expected_child_target}', recibido '{given_child_target}'."
                            )

    @classmethod
    def _validate_node(
        cls,
        *,
        model_name: str,
        node: Dict[str, Any],
        path: str,
        errors: List[str],
    ) -> None:
        if not isinstance(node, dict):
            errors.append(f"{path}: nodo inválido, se esperaba dict.")
            return

        node_type = node.get("type")
        props = node.get("props", {}) or {}
        children = node.get("children", []) or []

        if not node_type:
            errors.append(f"{path}: nodo sin 'type'.")
            return

        if node_type in {
            "TextInput",
            "TextArea",
            "NumberInput",
            "MonetaryInput",
            "BooleanSwitch",
            "SelectInput",
            "Many2OneLookup",
            "One2ManyLines",
            "Many2ManyTags",
            "DateInput",
            "DateTimeInput",
            "FileUploader",
            "ImageUploader",
            "StatusBar",
            "ModelStatusBar",
            "Badge",
        }:
            field_name = props.get("name") or props.get("field")
            if not field_name:
                errors.append(f"{path}: componente '{node_type}' sin campo asociado ('name'/'field').")
            else:
                cls._validate_component_field(
                    model_name=model_name,
                    component_type=node_type,
                    field_name=field_name,
                    props=props,
                    path=path,
                    errors=errors,
                )

        elif node_type == "DataGrid":
            fields_map = cls._get_model_field_map(model_name)
            for i, col in enumerate(props.get("columns", []) or []):
                field_name = col.get("field")
                if not field_name:
                    errors.append(f"{path}.columns[{i}]: columna sin 'field'.")
                    continue
                if field_name not in fields_map:
                    errors.append(
                        f"{path}.columns[{i}]: el campo '{field_name}' no existe en modelo '{model_name}'."
                    )

        elif node_type == "Chatter":
            res_model = props.get("res_model")
            if res_model and str(res_model) != str(model_name):
                errors.append(
                    f"{path}: Chatter res_model='{res_model}' no coincide con view.model='{model_name}'."
                )

        elif node_type in cls.CONTAINER_TYPES:
            pass
        else:
            pass

        for idx, child in enumerate(children):
            cls._validate_node(
                model_name=model_name,
                node=child,
                path=f"{path}.children[{idx}]",
                errors=errors,
            )

    @classmethod
    def validate_view_ast(cls, model_name: str, view_type: str, view_ast: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not Registry.get_model(model_name):
            errors.append(f"El modelo '{model_name}' no está registrado.")
            return False, errors

        normalized = cls._normalize_runtime_view(view_ast, model_name, view_type)
        cls._validate_node(
            model_name=model_name,
            node=normalized,
            path=f"{model_name}.{view_type}",
            errors=errors,
        )

        return len(errors) == 0, errors

    @classmethod
    def _assert_valid_view_ast(cls, model_name: str, view_type: str, view_ast: Dict[str, Any], source: str) -> None:
        ok, errors = cls.validate_view_ast(model_name, view_type, view_ast)
        if not ok:
            joined = "\n - ".join(errors)
            raise RuntimeError(
                f"Vista {source} inválida para {model_name}::{view_type}\n - {joined}"
            )

    @classmethod
    def register_view(cls, view_instance):
        model_name = getattr(view_instance, "model", None)
        view_type = getattr(view_instance, "view_type", "form")
        view_id = getattr(view_instance, "id", None)

        if not model_name:
            raise RuntimeError("Vista explícita inválida: falta atributo 'model'.")

        compiled = view_instance.compile()
        cls._assert_valid_view_ast(model_name, view_type, compiled, source="explicit_code")

        for existing in cls._explicit_views:
            if (
                getattr(existing, "model", None) == model_name
                and getattr(existing, "view_type", "form") == view_type
                and getattr(existing, "id", None) == view_id
            ):
                return

        cls._explicit_views.append(view_instance)
        print(f"✅ [SDUI] Vista explícita registrada para: {model_name}::{view_type}")

    @classmethod
    async def get_runtime_view(cls, model_name: str, view_type: str = "form") -> Dict[str, Any]:
        try:
            for view_instance in cls._explicit_views:
                if (
                    getattr(view_instance, "model", "") == model_name
                    and getattr(view_instance, "view_type", "form") == view_type
                ):
                    print(f"🎨 [SDUI] Sirviendo Vista Explícita para: {model_name}")
                    compiled = view_instance.compile()
                    cls._assert_valid_view_ast(model_name, view_type, compiled, source="explicit_code")
                    return cls._normalize_runtime_view(compiled, model_name, view_type)

            print(f"🏗️ [SDUI] Generando Vista Implícita/Hardcodeada para: {model_name}")
            built = await cls._build_view(model_name, view_type)
            cls._assert_valid_view_ast(model_name, view_type, built, source="generated_code")
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
        return await cls.get_runtime_view(model_name, view_type)

    @classmethod
    async def _build_view(cls, model_name: str, view_type: str) -> Dict[str, Any]:
        try:
            behaviors = Registry.get_behaviors(model_name)
        except AttributeError:
            behaviors = []

        fields_meta = cls._get_model_field_map(model_name)

        if not fields_meta:
            return {
                "type": "Typography",
                "props": {
                    "content": f"Error: No hay metadatos para {model_name}",
                    "color": "red-600",
                },
            }

        is_sale = model_name in ["sale.order", "sale_order"]

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

        if view_type == "list":
            if is_sale:
                columns = [
                    {"field": "name", "label": "Número", "type": "TextInput"},
                    {"field": "create_date", "label": "Fecha de creación", "type": "DateInput"},
                    {"field": "partner_id", "label": "Cliente", "type": "Many2OneLookup"},
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
                                "Pedidos de Venta"
                                if is_sale
                                else f"Listado de {model_name.replace('.', ' ').title()}"
                            ),
                        },
                    }
                ],
                "actions": model_actions,
            }

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
                    ["done", "Completado"],
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
                    "props": {"columns": 2},
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
                                        "comodel": "res.partner",
                                    },
                                },
                                {
                                    "type": "Many2OneLookup",
                                    "props": {
                                        "name": "company_id",
                                        "label": "Empresa",
                                        "comodel": "res.company",
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
                                    "props": {"name": "create_date", "label": "Fecha de creación", "readonly": True},
                                },
                                {
                                    "type": "TextInput",
                                    "props": {"name": "currency_id", "label": "Moneda", "readonly": True},
                                },
                                {
                                    "type": "MonetaryInput",
                                    "props": {"name": "amount_total", "label": "Total Pedido", "readonly": True},
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
                                    "props": {
                                        "name": "order_line",
                                        "data_source": "order_line",
                                        "comodel": "sale.order.line",
                                        "inverse_name": "order_id",
                                        "columns": [
                                            {
                                                "field": "product_id",
                                                "label": "Producto",
                                                "type": "Many2OneLookup",
                                                "comodel": "product.product",
                                            },
                                            {
                                                "field": "product_uom_qty",
                                                "label": "Cantidad",
                                                "type": "NumberInput",
                                            },
                                            {
                                                "field": "price_unit",
                                                "label": "Precio unitario",
                                                "type": "NumberInput",
                                            },
                                            {
                                                "field": "name",
                                                "label": "Descripción",
                                                "type": "TextInput",
                                            },
                                            {
                                                "field": "price_subtotal",
                                                "label": "Importe",
                                                "type": "NumberInput",
                                            },
                                        ],
                                    },
                                }
                            ],
                        },
                        {
                            "type": "Container",
                            "props": {"layout": "col", "gap": 4, "padding": 4},
                            "children": [
                                {
                                    "type": "Typography",
                                    "props": {
                                        "content": "Seguimiento",
                                        "variant": "h2",
                                        "color": "slate-800",
                                    },
                                },
                                {
                                    "type": "SelectInput",
                                    "props": {
                                        "name": "invoice_status",
                                        "label": "Estado de Facturación",
                                        "readonly": True,
                                        "options": [
                                            ["upselling", "Oportunidad de Upselling"],
                                            ["invoiced", "Totalmente Facturado"],
                                            ["to invoice", "A Facturar"],
                                            ["no", "Nada que Facturar"],
                                        ],
                                    },
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
                        child_fields = cls._get_model_field_map(comodel)
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