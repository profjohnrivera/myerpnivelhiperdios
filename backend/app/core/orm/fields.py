# backend/app/core/orm/fields.py

from typing import Any, Dict, List, Callable, Type, Union, Optional
import datetime
import decimal
import uuid

from app.core.env import Context


def _is_digit_id(value: Any) -> bool:
    return str(value).isdigit()


def _coerce_id(value: Any) -> Any:
    if _is_digit_id(value):
        return int(value)
    return value


class Field:
    def __init__(
        self,
        default: Any = None,
        label: str = None,
        type_: str = "string",
        required: bool = False,
        readonly: bool = False,
        index: bool = False,
        store: bool = True,
        translate: bool = False,
        help: str = None,
        copy: bool = True,
        groups: Optional[List[str]] = None,
        company_dependent: bool = False,
        inverse: Optional[str] = None,
        search: Optional[str] = None,
        compute_sudo: bool = False,
        precompute: bool = False,
        **kwargs,
    ):
        self.name: str = ""
        self.default = default
        self.label = label
        self.type = type_
        self.required = required
        self.readonly = readonly
        self.index = index
        self.store = store
        self.translate = translate
        self.help = help
        self.copy = copy
        self.groups = groups or []
        self.company_dependent = company_dependent
        self.inverse = inverse
        self.search = search
        self.compute_sudo = compute_sudo
        self.precompute = precompute
        self.extra_meta = kwargs

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name == "id":
            return instance._id_val

        node_name = instance._get_node_name(self.name)
        val = instance.graph.get(node_name)

        if val is not None and self.translate:
            if isinstance(val, dict):
                env = instance._env or Context.get_env()
                lang = getattr(env, "lang", "en_US") if env else "en_US"
                return val.get(lang, list(val.values())[0] if val else "")
            return val

        if val is None:
            return self.default() if callable(self.default) else self.default
        return val

    def __set__(self, instance, value):
        if self.name == "id":
            if not hasattr(instance, "_id_val") or instance._id_val is None:
                instance._id_val = int(value) if str(value).isdigit() else str(value)
            return

        if self.required and (value is None or value == "" or value is False):
            if not (self.type == "bool" and value is False):
                raise ValueError(f"❌ Campo '{self.label or self.name}' es obligatorio.")

        node_name = instance._get_node_name(self.name)

        if self.translate and value is not None:
            env = instance._env or Context.get_env()
            lang = getattr(env, "lang", "en_US") if env else "en_US"
            current_dict = instance.graph.get(node_name) or {}
            if isinstance(current_dict, dict):
                current_dict[lang] = value
                value = current_dict
            else:
                value = {lang: value}

        if isinstance(value, datetime.datetime):
            value = value.isoformat()

        instance.graph.set_fact(node_name, value)

    def get_meta(self) -> Dict:
        return {
            "type": "jsonb" if self.translate else self.type,
            "logical_type": self.type,
            "label": self.label or self.name.replace("_", " ").title(),
            "required": self.required,
            "readonly": self.readonly,
            "index": self.index,
            "store": self.store,
            "translate": self.translate,
            "help": self.help,
            "copy": self.copy,
            "groups": self.groups,
            "company_dependent": self.company_dependent,
            "inverse": self.inverse,
            "search": self.search,
            "compute_sudo": self.compute_sudo,
            "precompute": self.precompute,
            **self.extra_meta,
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
    def __init__(self, currency_field="currency_id", digits=(16, 2), **kwargs):
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
    def __init__(
        self,
        func: Callable,
        depends_on: List[str],
        store: bool = False,
        compute_sudo: bool = False,
        precompute: bool = False,
        **kwargs,
    ):
        readonly = kwargs.pop("readonly", True)
        super().__init__(
            type_="computed",
            store=store,
            readonly=readonly,
            compute_sudo=compute_sudo,
            precompute=precompute,
            **kwargs,
        )
        self.func = func
        self.depends_on = depends_on

    def get_meta(self) -> Dict:
        meta = super().get_meta()
        meta["depends_on"] = self.depends_on
        return meta


class HtmlField(Field):
    def __init__(self, **kwargs):
        super().__init__(type_="html", **kwargs)

    def __set__(self, instance, value):
        if value is not None:
            value = str(value)
        super().__set__(instance, value)


class JsonField(Field):
    def __init__(self, default=None, **kwargs):
        default = default if default is not None else dict
        super().__init__(default=default, type_="json", **kwargs)

    def get_meta(self) -> Dict:
        meta = super().get_meta()
        meta["type"] = "jsonb"
        meta["logical_type"] = "json"
        return meta

    def __set__(self, instance, value):
        if isinstance(value, tuple):
            value = list(value)
        super().__set__(instance, value)


class ReferenceField(Field):
    """
    Almacena referencias polimórficas en formato "model_name,res_id".
    """
    def __init__(self, allowed_models: Optional[List[str]] = None, **kwargs):
        super().__init__(type_="reference", allowed_models=allowed_models or [], **kwargs)
        self.allowed_models = allowed_models or []

    def _normalize_reference(self, value: Any) -> Optional[str]:
        if value in (None, False, ""):
            return None

        if hasattr(value, "_get_model_name") and hasattr(value, "id"):
            model_name = value._get_model_name()
            rec_id = value.id
            if self.allowed_models and model_name not in self.allowed_models:
                raise ValueError(
                    f"❌ Modelo '{model_name}' no permitido en ReferenceField '{self.name}'."
                )
            return f"{model_name},{rec_id}"

        if isinstance(value, (list, tuple)) and len(value) == 2:
            model_name, rec_id = value[0], value[1]
            if self.allowed_models and model_name not in self.allowed_models:
                raise ValueError(
                    f"❌ Modelo '{model_name}' no permitido en ReferenceField '{self.name}'."
                )
            if not _is_digit_id(rec_id):
                raise ValueError(f"❌ ID inválido en ReferenceField '{self.name}': {rec_id}")
            return f"{model_name},{int(rec_id)}"

        if isinstance(value, dict):
            model_name = value.get("model")
            rec_id = value.get("id")
            if not model_name or rec_id is None:
                raise ValueError(
                    f"❌ Dict inválido para ReferenceField '{self.name}'. Usa {{'model': ..., 'id': ...}}."
                )
            if self.allowed_models and model_name not in self.allowed_models:
                raise ValueError(
                    f"❌ Modelo '{model_name}' no permitido en ReferenceField '{self.name}'."
                )
            if not _is_digit_id(rec_id):
                raise ValueError(f"❌ ID inválido en ReferenceField '{self.name}': {rec_id}")
            return f"{model_name},{int(rec_id)}"

        if isinstance(value, str) and "," in value:
            model_name, rec_id = value.split(",", 1)
            if self.allowed_models and model_name not in self.allowed_models:
                raise ValueError(
                    f"❌ Modelo '{model_name}' no permitido en ReferenceField '{self.name}'."
                )
            if not _is_digit_id(rec_id):
                raise ValueError(f"❌ ID inválido en ReferenceField '{self.name}': {rec_id}")
            return f"{model_name},{int(rec_id)}"

        raise ValueError(f"❌ Valor inválido para ReferenceField '{self.name}': {value!r}")

    def __get__(self, instance, owner):
        if instance is None:
            return self

        raw = super().__get__(instance, owner)
        if not raw:
            return None

        from app.core.registry import Registry

        try:
            model_name, rec_id = str(raw).split(",", 1)
        except ValueError:
            return None

        try:
            ModelClass = Registry.get_model(model_name)
        except Exception:
            return None

        return ModelClass(_id=_coerce_id(rec_id), context=instance.graph, env=instance._env)

    def __set__(self, instance, value):
        super().__set__(instance, self._normalize_reference(value))

    def get_meta(self) -> Dict:
        meta = super().get_meta()
        meta["allowed_models"] = self.allowed_models
        return meta


class RelatedField(Field):
    """
    Campo declarativo related.

    Esta ola:
    - soporta rutas simples tipo partner_id.name
    - soporta many2one -> scalar / many2one
    - registra metadatos rich para scaffolder/runtime
    - todavía NO agrega search/inverse automáticos estilo Odoo
    """
    def __init__(
        self,
        path: str,
        *,
        field_type: str = "string",
        target_model: Optional[str] = None,
        store: bool = False,
        readonly: bool = True,
        **kwargs,
    ):
        super().__init__(
            type_=field_type,
            store=store,
            readonly=readonly,
            related=path,
            target=target_model,
            **kwargs,
        )
        self.related = path
        self.target_model = target_model

    def _resolve_terminal(self, instance):
        current = instance
        parts = self.related.split(".")

        for part in parts[:-1]:
            if current is None:
                return None, None
            try:
                current = getattr(current, part)
            except Exception:
                return None, None

        return current, parts[-1]

    def __get__(self, instance, owner):
        if instance is None:
            return self

        parent, leaf = self._resolve_terminal(instance)
        if parent is None or not leaf:
            return self.default() if callable(self.default) else self.default

        try:
            return getattr(parent, leaf)
        except Exception:
            return self.default() if callable(self.default) else self.default

    def __set__(self, instance, value):
        if self.readonly:
            raise ValueError(f"❌ RelatedField '{self.name}' es readonly.")

        parent, leaf = self._resolve_terminal(instance)
        if parent is None or not leaf:
            raise ValueError(f"❌ No se pudo resolver la ruta related '{self.related}'.")

        setattr(parent, leaf, value)

    def get_meta(self) -> Dict:
        meta = super().get_meta()
        meta["related"] = self.related
        if self.target_model:
            meta["target"] = self.target_model
        return meta


class RelationField(Field):
    def __init__(self, model_cls: Union[Type, str], ondelete: str = "set null", **kwargs):
        super().__init__(type_="relation", target=str(model_cls), ondelete=ondelete, **kwargs)
        self.related_model = model_cls

    def __get__(self, instance, owner):
        if instance is None:
            return self

        related_id = super().__get__(instance, owner)
        if not related_id:
            return None

        from app.core.registry import Registry

        target = self.related_model if self.related_model != "self" else instance._get_model_name()
        ModelClass = Registry.get_model(target)
        return ModelClass(_id=related_id, context=instance.graph, env=instance._env)

    def __set__(self, instance, value):
        if hasattr(value, "id"):
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
        if instance is None:
            return self

        ids = super().__get__(instance, owner) or []
        virtual_records = instance.graph.get(("virtual", instance._get_model_name(), instance.id, self.name))

        from app.core.registry import Registry
        from .recordset import Recordset

        try:
            ModelClass = Registry.get_model(self.related_model)
            env = instance._env or Context.get_env()
            if virtual_records is not None:
                return Recordset(ModelClass, virtual_records, env)
            return Recordset(
                ModelClass,
                [ModelClass(_id=i, context=instance.graph, env=env) for i in ids],
                env,
            )
        except Exception:
            return Recordset(None, [])

    def __set__(self, instance, value):
        clean_ids = []
        virtual_records = []

        from app.core.registry import Registry
        from .recordset import Recordset

        try:
            ChildModel = Registry.get_model(self.related_model)
        except Exception:
            ChildModel = None

        if isinstance(value, (list, Recordset)):
            for item in value:
                if isinstance(item, dict) and ChildModel:
                    v_id = item.get("id") or f"new_{uuid.uuid4().hex[:8]}"
                    v_rec = ChildModel(_id=v_id, context=instance.graph, env=instance._env)
                    for k, v in item.items():
                        if hasattr(v_rec, k):
                            setattr(v_rec, k, v)
                    virtual_records.append(v_rec)
                    clean_ids.append(v_id)
                elif hasattr(item, "id"):
                    clean_ids.append(item.id)
                    virtual_records.append(item)
                else:
                    val = int(item) if str(item).isdigit() else str(item)
                    clean_ids.append(val)
                    if ChildModel:
                        virtual_records.append(ChildModel(_id=val, context=instance.graph, env=instance._env))

        super().__set__(instance, clean_ids)
        instance.graph.set_fact(("virtual", instance._get_model_name(), instance.id, self.name), virtual_records)

    def get_meta(self) -> Dict:
        meta = super().get_meta()
        meta["inverse_name"] = self.inverse_name
        return meta


class Many2manyField(Field):
    def __init__(self, related_model: str, **kwargs):
        super().__init__(type_="many2many", target=related_model, store=True, **kwargs)
        self.related_model = related_model

    def __get__(self, instance, owner):
        if instance is None:
            return self

        ids = super().__get__(instance, owner) or []

        from app.core.registry import Registry
        from .recordset import Recordset

        try:
            ModelClass = Registry.get_model(self.related_model)
            env = instance._env or Context.get_env()
            return Recordset(
                ModelClass,
                [ModelClass(_id=i, context=instance.graph, env=env) for i in ids],
                env,
            )
        except Exception:
            return Recordset(None, [])

    def __set__(self, instance, value):
        clean_ids = []

        from .recordset import Recordset

        if isinstance(value, (list, Recordset)):
            for item in value:
                if hasattr(item, "id"):
                    _id = item.id
                    if str(_id).isdigit():
                        clean_ids.append(int(_id))
                elif isinstance(item, dict):
                    _id = item.get("id")
                    if _id is not None and str(_id).isdigit():
                        clean_ids.append(int(_id))
                elif str(item).isdigit():
                    clean_ids.append(int(item))

        super().__set__(instance, clean_ids)


class PasswordField(Field):
    def __init__(self, **kwargs):
        super().__init__(type_="password", **kwargs)


# Alias más cercanos al vocabulario Odoo / estándar
Many2oneField = RelationField