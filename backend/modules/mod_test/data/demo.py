# backend/modules/mod_test/data/demo.py

async def init_demo_data(env):
    """
    🎁 DATOS DEMO DE LABORATORIO
    Idempotentes por XML-ID.
    """
    loader = env.data

    record = await loader.ensure_record(
        "demo_test_record_alpha",
        "test.record",
        {
            "name": "Experimento Relacional Alfa",
            "description": "Validando el One2manyField y el Scaffolder",
            "status": "draft",
        },
        lookup_domain=[("name", "=", "Experimento Relacional Alfa")],
    )

    await loader.ensure_record(
        "demo_test_line_a",
        "test.line",
        {
            "record_id": record.id,
            "name": "Reactivo A",
            "qty": 15.5,
        },
        lookup_domain=[("name", "=", "Reactivo A"), ("record_id", "=", record.id)],
    )

    await loader.ensure_record(
        "demo_test_line_b",
        "test.line",
        {
            "record_id": record.id,
            "name": "Reactivo B",
            "qty": 7.0,
            "notes": "Altamente volátil",
        },
        lookup_domain=[("name", "=", "Reactivo B"), ("record_id", "=", record.id)],
    )