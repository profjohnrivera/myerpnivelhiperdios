# backend/tests/test_01_registry_and_sdui.py

import pytest

from app.core.registry import Registry
from app.core.scaffolder import ViewScaffolder


@pytest.mark.asyncio
async def test_registry_planes_are_separated(booted_app):
    runtime = Registry.get_runtime_fields_for_model("sale.order")
    technical = Registry.get_technical_fields_for_model("sale.order")
    schema = Registry.get_schema_fields_for_model("sale.order")

    assert "order_line" in runtime
    assert "order_line" in technical
    assert "order_line" not in schema

    assert "amount_total" in runtime
    assert "amount_total" in technical
    assert "amount_total" in schema

    with pytest.raises(RuntimeError, match="prohibido|ambigüedad"):
        Registry.get_fields_for_model("sale.order")


@pytest.mark.asyncio
async def test_explicit_sale_order_form_view_is_available(booted_app):
    SaleOrder = Registry.get_model("sale.order")
    view = await SaleOrder.get_view("form")

    assert view["model"] == "sale.order"
    assert view["view_type"] == "form"
    assert view["type"] == "Container"


@pytest.mark.asyncio
async def test_scaffolder_rejects_unknown_field(booted_app):
    bad_view = {
        "type": "Container",
        "props": {"layout": "col"},
        "children": [
            {
                "type": "TextInput",
                "props": {
                    "name": "field_ghost_definitivo",
                    "label": "Campo Fantasma",
                },
            }
        ],
    }

    ok, errors = ViewScaffolder.validate_view_ast("sale.order", "form", bad_view)

    assert ok is False
    assert errors
    assert any("no existe" in err.lower() for err in errors)