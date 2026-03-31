# backend/tests/test_03_security_acl_rls.py

import pytest

from app.api.v1.runtime import request_env
from tests.helpers import create_partner, create_sale_order, read_single, search_ids


@pytest.mark.asyncio
async def test_alpha_and_beta_only_see_their_own_sale_orders(booted_app, master_data, unique_token):
    company_id = master_data["company_id"]
    alpha = master_data["alpha"]
    beta = master_data["beta"]

    partner_alpha = await create_partner(f"alpha_{unique_token}", company_id=company_id, user_id="system")
    partner_beta = await create_partner(f"beta_{unique_token}", company_id=company_id, user_id="system")

    alpha_order_id = await create_sale_order(
        user_id=alpha["id"],
        prefix=f"acl_alpha_{unique_token}",
        company_id=company_id,
        partner_id=partner_alpha,
    )
    beta_order_id = await create_sale_order(
        user_id=beta["id"],
        prefix=f"acl_beta_{unique_token}",
        company_id=company_id,
        partner_id=partner_beta,
    )

    alpha_visible = await search_ids(alpha["id"], "sale.order", [("id", "in", [alpha_order_id, beta_order_id])])
    beta_visible = await search_ids(beta["id"], "sale.order", [("id", "in", [alpha_order_id, beta_order_id])])

    assert alpha_visible == [alpha_order_id]
    assert beta_visible == [beta_order_id]


@pytest.mark.asyncio
async def test_admin_group_bypass_sees_both_orders(booted_app, master_data, unique_token):
    company_id = master_data["company_id"]
    admin = master_data["admin"]
    alpha = master_data["alpha"]
    beta = master_data["beta"]

    partner_alpha = await create_partner(f"admincheck_alpha_{unique_token}", company_id=company_id, user_id="system")
    partner_beta = await create_partner(f"admincheck_beta_{unique_token}", company_id=company_id, user_id="system")

    alpha_order_id = await create_sale_order(
        user_id=alpha["id"],
        prefix=f"admin_a_{unique_token}",
        company_id=company_id,
        partner_id=partner_alpha,
    )
    beta_order_id = await create_sale_order(
        user_id=beta["id"],
        prefix=f"admin_b_{unique_token}",
        company_id=company_id,
        partner_id=partner_beta,
    )

    visible_to_admin = await search_ids(
        admin["id"],
        "sale.order",
        [("id", "in", [alpha_order_id, beta_order_id])],
    )

    assert set(visible_to_admin) == {alpha_order_id, beta_order_id}


@pytest.mark.asyncio
async def test_direct_read_of_foreign_order_is_blocked_by_rls(booted_app, master_data, unique_token):
    company_id = master_data["company_id"]
    alpha = master_data["alpha"]
    beta = master_data["beta"]

    partner_beta = await create_partner(f"foreign_beta_{unique_token}", company_id=company_id, user_id="system")
    beta_order_id = await create_sale_order(
        user_id=beta["id"],
        prefix=f"foreign_{unique_token}",
        company_id=company_id,
        partner_id=partner_beta,
    )

    async with request_env(alpha["id"]) as (env, session_graph):
        rs = env["sale.order"].browse([beta_order_id], context=session_graph)
        await rs.load_data()

        with pytest.raises(PermissionError):
            await rs.read(["id", "name"])


@pytest.mark.asyncio
async def test_admin_user_can_direct_read_foreign_order(booted_app, master_data, unique_token):
    company_id = master_data["company_id"]
    admin = master_data["admin"]
    beta = master_data["beta"]

    partner_beta = await create_partner(f"adminread_beta_{unique_token}", company_id=company_id, user_id="system")
    beta_order_id = await create_sale_order(
        user_id=beta["id"],
        prefix=f"adminread_{unique_token}",
        company_id=company_id,
        partner_id=partner_beta,
    )

    row = await read_single(admin["id"], "sale.order", beta_order_id, fields=["id", "name"])
    assert row["id"] == beta_order_id