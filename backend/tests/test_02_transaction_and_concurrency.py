# backend/tests/test_02_transaction_and_concurrency.py

import pytest

from app.api.v1.runtime import request_env
from app.core.transaction import transaction
from tests.helpers import create_test_record, persist_graph, search_ids


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_exception_happens(booted_app, unique_token):
    record_name = f"rollback_probe_{unique_token}"

    with pytest.raises(RuntimeError, match="boom"):
        async with transaction():
            async with request_env("system") as (env, session_graph):
                record = await env["test.record"].create(
                    {
                        "name": record_name,
                        "description": "must rollback",
                        "status": "draft",
                    },
                    context=session_graph,
                )
                await persist_graph(session_graph)
                assert record is not None
                raise RuntimeError("boom")

    ids = await search_ids("system", "test.record", [("name", "=", record_name)])
    assert ids == []


@pytest.mark.asyncio
async def test_write_version_conflict_is_detected(booted_app, unique_token):
    record_id = await create_test_record(prefix=f"cc_{unique_token}", user_id="system")

    async with request_env("system") as (env1, graph1):
        rs1 = env1["test.record"].browse([record_id], context=graph1)
        await rs1.load_data()
        rec1 = rs1[0]
        version1 = rec1.write_version

        async with request_env("system") as (env2, graph2):
            rs2 = env2["test.record"].browse([record_id], context=graph2)
            await rs2.load_data()
            rec2 = rs2[0]

            assert rec2.write_version == version1

            async with transaction():
                await rec1.write({"description": "winner"})
                await persist_graph(graph1)

            async with transaction():
                with pytest.raises(ValueError, match="CONCURRENCY_CONFLICT"):
                    await rec2.write({"description": "loser"})
                    await persist_graph(graph2)