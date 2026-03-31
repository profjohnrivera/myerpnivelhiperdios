# backend/tests/test_04_sales_aggregates.py

import pytest

from tests.helpers import (
    create_partner,
    create_sale_order,
    create_sale_order_line,
    order_line_ids,
    order_snapshot,
    unlink_model,
    write_model,
)


@pytest.mark.asyncio
async def test_sale_order_total_stays_consistent_after_line_create_write_unlink(
    booted_app,
    master_data,
    unique_token,
):
    company_id = master_data["company_id"]
    product_id = master_data["product_id"]

    partner_id = await create_partner(f"agg_{unique_token}", company_id=company_id, user_id="system")

    order_id = await create_sale_order(
        user_id="system",
        prefix=f"agg_order_{unique_token}",
        company_id=company_id,
        partner_id=partner_id,
        product_id=product_id,
        line_specs=[
            {"qty": 1.0, "price": 1.0, "name": "L1"},
            {"qty": 1.0, "price": 1.0, "name": "L2"},
        ],
    )

    snap = await order_snapshot("system", order_id)
    assert snap["amount_total"] == pytest.approx(2.0)
    assert snap["lines_total"] == pytest.approx(2.0)

    existing_line_ids = await order_line_ids("system", order_id)
    assert len(existing_line_ids) == 2
    first_line_id = existing_line_ids[0]

    third_line_id = await create_sale_order_line(
        user_id="system",
        order_id=order_id,
        product_id=product_id,
        qty=1.0,
        price=1.0,
        name="L3",
    )

    snap = await order_snapshot("system", order_id)
    assert snap["amount_total"] == pytest.approx(3.0)
    assert snap["lines_total"] == pytest.approx(3.0)

    await write_model(
        user_id="system",
        model_name="sale.order.line",
        record_id=first_line_id,
        vals={"product_uom_qty": 4.0},
    )

    snap = await order_snapshot("system", order_id)
    assert snap["amount_total"] == pytest.approx(6.0)
    assert snap["lines_total"] == pytest.approx(6.0)

    await unlink_model(
        user_id="system",
        model_name="sale.order.line",
        record_id=third_line_id,
    )

    snap = await order_snapshot("system", order_id)
    assert snap["amount_total"] == pytest.approx(5.0)
    assert snap["lines_total"] == pytest.approx(5.0)