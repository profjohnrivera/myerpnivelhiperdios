# backend/modules/mod_sales/data/demo.py

async def init_demo_data(env):
    """
    🎁 DATOS DEMO DE VENTAS
    Ahora idempotentes por XML-ID.
    """
    loader = env.data

    company = await loader.ensure_record(
        "demo_company_main",
        "res.company",
        {
            "name": "HiperDios Corp",
            "currency_id": "PEN",
        },
        lookup_domain=[("name", "=", "HiperDios Corp")],
    )

    c1 = await loader.ensure_record(
        "demo_partner_spacex",
        "res.partner",
        {
            "name": "SpaceX Corp",
            "email": "elon@spacex.com",
        },
        lookup_domain=[("email", "=", "elon@spacex.com")],
    )

    c2 = await loader.ensure_record(
        "demo_partner_stark",
        "res.partner",
        {
            "name": "Stark Industries",
            "email": "tony@stark.com",
        },
        lookup_domain=[("email", "=", "tony@stark.com")],
    )

    await loader.ensure_record(
        "demo_sale_order_1",
        "sale.order",
        {
            "name": "PED-2026-0001",
            "partner_id": c1.id,
            "company_id": company.id,
            "state": "draft",
        },
        lookup_domain=[("name", "=", "PED-2026-0001")],
    )

    await loader.ensure_record(
        "demo_sale_order_2",
        "sale.order",
        {
            "name": "PED-2026-0002",
            "partner_id": c2.id,
            "company_id": company.id,
            "state": "sale",
        },
        lookup_domain=[("name", "=", "PED-2026-0002")],
    )