# backend/tests/test_05_onchange_and_tree.py

import json

import pytest

from app.api.v1.onchange import onchange_record
from tests.helpers import create_category, read_single, write_model


@pytest.mark.asyncio
async def test_onchange_ignores_unknown_fields_and_nested_unknown_fields(booted_app, unique_token):
    payload = {
        "data": {
            "name": f"onchange_{unique_token}",
            "field_ghost": "boom",
            "line_ids": [
                {
                    "name": "Reactivo P5",
                    "qty": 2.0,
                    "nested_ghost": "nope",
                }
            ],
        }
    }

    result = await onchange_record(
        model_name="test.record",
        payload=payload,
        current_user_id="system",
    )

    rendered = json.dumps(result, ensure_ascii=False)

    assert f"onchange_{unique_token}" in rendered
    assert "field_ghost" not in rendered
    assert "nested_ghost" not in rendered


@pytest.mark.asyncio
async def test_tree_parent_path_cascades_and_cycle_is_blocked(booted_app, unique_token):
    root_id = await create_category(f"root_{unique_token}")
    child_id = await create_category(f"child_{unique_token}", parent_id=root_id)
    grandchild_id = await create_category(f"grand_{unique_token}", parent_id=child_id)

    root_before = await read_single("system", "product.category", root_id, fields=["id", "name", "parent_path"])
    child_before = await read_single("system", "product.category", child_id, fields=["id", "name", "parent_path"])
    grand_before = await read_single("system", "product.category", grandchild_id, fields=["id", "name", "parent_path"])

    assert child_before["parent_path"].startswith(root_before["parent_path"])
    assert grand_before["parent_path"].startswith(child_before["parent_path"])

    await write_model("system", "product.category", child_id, {"parent_id": None})

    child_after = await read_single("system", "product.category", child_id, fields=["id", "name", "parent_path"])
    grand_after = await read_single("system", "product.category", grandchild_id, fields=["id", "name", "parent_path"])

    assert child_after["parent_path"] == f"{child_id}/"
    assert grand_after["parent_path"].startswith(child_after["parent_path"])

    with pytest.raises(ValueError, match="Paradoja"):
        await write_model("system", "product.category", root_id, {"parent_id": grandchild_id})

    root_after_failed_cycle = await read_single("system", "product.category", root_id, fields=["id", "name", "parent_path"])
    assert root_after_failed_cycle["parent_path"] == root_before["parent_path"]