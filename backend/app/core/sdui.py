# backend/app/core/sdui.py

from typing import List, Dict, Any, Optional


class Component:
    _ui_type: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        node_type = self._ui_type or self.__class__.__name__

        res = {
            "type": node_type,
            "props": {},
            "children": [],
        }

        for k, v in self.__dict__.items():
            if v is None or k.startswith("_"):
                continue

            if k == "children":
                res["children"] = [
                    c.to_json() if isinstance(c, Component) else c
                    for c in (v if isinstance(v, list) else [])
                ]
            elif k in ["title", "id", "model", "data_source"]:
                res[k] = v
            else:
                prop_name = "name" if k == "key" else k
                res["props"][prop_name] = v

        return res


class ModelActions(Component):
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_json(self) -> Dict[str, Any]:
        from app.core.registry import Registry

        model_cls = Registry.get_model(self.model_name)
        buttons = []

        for attr_name in dir(model_cls):
            attr = getattr(model_cls, attr_name, None)
            if getattr(attr, "_is_action", False) and hasattr(attr, "_action_meta"):
                meta = attr._action_meta
                buttons.append(
                    Button(
                        label=meta.get("label"),
                        action=meta.get("name"),
                        icon=meta.get("icon"),
                        variant=meta.get("variant", "primary"),
                    ).to_json()
                )

        props = {"layout": "row", "gap": 2, "padding": 0, "border": False}
        for k, v in self.__dict__.items():
            if k not in ["model_name"] and not k.startswith("_"):
                props[k] = v

        return {
            "type": "Container",
            "props": props,
            "children": buttons,
        }


class ModelStatusBar(Component):
    def __init__(self, model_name: str, field: str = "state", options: list = None, **kwargs):
        self.model_name = model_name
        self.field = field
        self.options = options or []
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_json(self) -> Dict[str, Any]:
        from app.core.registry import Registry

        fields_meta = Registry.get_runtime_fields_for_model(self.model_name)
        state_meta = fields_meta.get(self.field, {})

        final_options = self.options if self.options else state_meta.get("options", [])

        props = {"field": self.field, "options": final_options}
        for k, v in self.__dict__.items():
            if k not in ["model_name", "field", "options"] and not k.startswith("_"):
                props[k] = v

        return {
            "type": "StatusBar",
            "props": props,
            "children": [],
        }


class Container(Component):
    def __init__(
        self,
        layout: str = "col",
        gap: int = 4,
        padding: int = 4,
        border: bool = False,
        justify: str = "start",
        align: str = "stretch",
        children: List[Component] = None,
        **kwargs,
    ):
        self.layout = layout
        self.gap = gap
        self.padding = padding
        self.border = border
        self.justify = justify
        self.align = align
        self.children = children or []
        for k, v in kwargs.items():
            setattr(self, k, v)


class HeaderBar(Container):
    _ui_type = "Container"

    def __init__(self, children: List[Component] = None, **kwargs):
        super().__init__(
            layout="row",
            justify="between",
            align="center",
            gap=4,
            padding=4,
            border=True,
            children=children,
            **kwargs,
        )


class Card(Component):
    def __init__(self, title: str = None, children: List[Component] = None, **kwargs):
        self.title = title
        self.children = children or []
        for k, v in kwargs.items():
            setattr(self, k, v)


class Group(Component):
    def __init__(self, columns: int = 2, children: List[Component] = None, **kwargs):
        self.columns = columns
        self.children = children or []
        for k, v in kwargs.items():
            setattr(self, k, v)


class Notebook(Component):
    def __init__(self, tabs: List[str], children: List[Component] = None, **kwargs):
        self.tabs = tabs
        self.children = children or []
        for k, v in kwargs.items():
            setattr(self, k, v)


class TextInput(Component):
    def __init__(self, name: str, label: str, type: str = "text", readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.type = type
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class DateInput(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class Many2OneLookup(Component):
    def __init__(self, name: str, label: str, comodel: str = None, placeholder: str = None, **kwargs):
        self.name = name
        self.label = label
        self.comodel = comodel
        self.placeholder = placeholder
        for k, v in kwargs.items():
            setattr(self, k, v)


class One2ManyLines(Component):
    def __init__(
        self,
        name: str,
        data_source: str = None,
        comodel: str = None,
        inverse_name: str = None,
        columns: list = None,
        **kwargs,
    ):
        self.name = name
        self.data_source = data_source or name
        self.comodel = comodel

        if inverse_name is not None:
            self.inverse_name = inverse_name
        if columns is not None:
            self.columns = columns

        for key, value in kwargs.items():
            setattr(self, key, value)


class Badge(Component):
    def __init__(self, name: str, label: str, color: str = "gray", **kwargs):
        self.name = name
        self.label = label
        self.color = color
        for k, v in kwargs.items():
            setattr(self, k, v)


class Typography(Component):
    def __init__(self, content: str, variant: str = "body", color: str = "slate-800", **kwargs):
        self.content = content
        self.variant = variant
        self.color = color
        for k, v in kwargs.items():
            setattr(self, k, v)


class Button(Component):
    def __init__(self, label: str, action: str, icon: str = None, variant: str = "primary", **kwargs):
        self.label = label
        self.action = action
        self.icon = icon
        self.variant = variant
        for k, v in kwargs.items():
            setattr(self, k, v)


class Chatter(Component):
    def __init__(self, res_model: str, **kwargs):
        self.res_model = res_model
        for k, v in kwargs.items():
            setattr(self, k, v)


class StatusBar(Component):
    def __init__(self, field: str = "state", options: list = None, **kwargs):
        self.field = field
        self.options = options or []
        for k, v in kwargs.items():
            setattr(self, k, v)


class TextArea(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class BooleanSwitch(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class NumberInput(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class MonetaryInput(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class DateTimeInput(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class SelectInput(Component):
    def __init__(self, name: str, label: str, options: list = None, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.options = options or []
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class Many2ManyTags(Component):
    def __init__(self, name: str, label: str, comodel: str = None, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.comodel = comodel
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class FileUploader(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)


class ImageUploader(Component):
    def __init__(self, name: str, label: str, readonly: bool = False, **kwargs):
        self.name = name
        self.label = label
        self.readonly = readonly
        for k, v in kwargs.items():
            setattr(self, k, v)