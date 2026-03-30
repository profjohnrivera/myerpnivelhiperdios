# backend/app/core/orm/fields.py

from typing import Any, Dict, List, Callable, Type, Union
import datetime
import decimal
import uuid

from app.core.env import Context


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
            "**": self.extra_meta,
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
    def __init__(self, func: Callable, depends_on: List[str], store: bool = False, **kwargs):
        readonly = kwargs.pop("readonly", True)
        super().__init__(type_="computed", store=store, readonly=readonly, **kwargs)
        self.func = func
        self.depends_on = depends_on


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
            return Recordset(ModelClass, [ModelClass(_id=i, context=instance.graph, env=env) for i in ids], env)
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