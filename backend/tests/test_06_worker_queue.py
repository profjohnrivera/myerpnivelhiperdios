# backend/tests/test_06_worker_queue.py

import asyncio

import pytest

from app.core.env import Env, env_scope
from app.core.worker import WorkerEngine


async def _stop_worker_background():
    WorkerEngine.stop()
    await WorkerEngine.wait_stopped(timeout=1.0)
    await asyncio.sleep(0)


@pytest.fixture(autouse=True)
async def _quiesce_and_isolate_worker(booted_app):
    """
    Suite determinista del worker:
    - apaga runner de fondo
    - limpia cola y side effects de pruebas anteriores
    """
    await _stop_worker_background()

    conn = await booted_app.storage.get_connection()
    await conn.execute('DELETE FROM "ir_queue"')
    await conn.execute(
        """
        DELETE FROM "ir_config_parameter"
        WHERE key LIKE 'worker.%'
           OR key LIKE 'orphan.%'
           OR key LIKE 'prio.%'
        """
    )

    yield

    await _stop_worker_background()

    conn = await booted_app.storage.get_connection()
    await conn.execute('DELETE FROM "ir_queue"')
    await conn.execute(
        """
        DELETE FROM "ir_config_parameter"
        WHERE key LIKE 'worker.%'
           OR key LIKE 'orphan.%'
           OR key LIKE 'prio.%'
        """
    )


def _system_env(app):
    return Env(
        user_id="system",
        graph=app.graph,
        su=True,
        context={
            "disable_audit": True,
            "skip_optimistic_lock": True,
        },
        _skip_autoset=True,
    )


async def _create_test_record(app, name: str) -> int:
    env = _system_env(app)
    async with env_scope(env):
        rec = await env["test.record"].create({
            "name": name,
            "status": "draft",
        })
        id_map = await app.storage.save(app.graph, model_filter="test.record")
        real_id = id_map.get(str(rec.id), rec.id)
        return int(real_id)


async def _queue_row(app, job_id: int) -> dict:
    conn = await app.storage.get_connection()
    row = await conn.fetchrow(
        """
        SELECT id, model_name, method_name, priority, state, retries, max_retries,
               args_json, kwargs_json, retry_at, scheduled_at,
               date_started, date_finished, error_log
        FROM "ir_queue"
        WHERE id = $1
        """,
        int(job_id),
    )
    return dict(row) if row else None


async def _param_value(app, key: str):
    conn = await app.storage.get_connection()
    return await conn.fetchval(
        'SELECT value FROM "ir_config_parameter" WHERE key = $1 ORDER BY id DESC LIMIT 1',
        key,
    )


async def _record_row(app, record_id: int) -> dict:
    conn = await app.storage.get_connection()
    row = await conn.fetchrow(
        """
        SELECT id, name, description, status
        FROM "test_record"
        WHERE id = $1
        """,
        int(record_id),
    )
    return dict(row) if row else None


async def _set_retry_due_now(app, job_id: int):
    conn = await app.storage.get_connection()
    await conn.execute(
        """
        UPDATE "ir_queue"
        SET retry_at = NOW() - INTERVAL '1 second'
        WHERE id = $1
        """,
        int(job_id),
    )


@pytest.mark.asyncio
async def test_worker_enqueue_persists_pending_job(booted_app, unique_token):
    job_id = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": f"worker.ctx.{unique_token}"},
        priority=77,
        max_retries=4,
    )

    row = await _queue_row(booted_app, job_id)

    assert row is not None
    assert row["state"] == "pending"
    assert row["priority"] == 77
    assert row["model_name"] == "test.record"
    assert row["method_name"] == "worker_capture_context"
    assert row["max_retries"] == 4
    assert row["scheduled_at"] is not None
    assert "worker.ctx." in (row["kwargs_json"] or "")


@pytest.mark.asyncio
async def test_worker_executes_record_job_and_persists_graph_changes(booted_app, unique_token):
    record_id = await _create_test_record(booted_app, f"worker-record-{unique_token}")

    job_id = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_mark_done",
        kwargs={
            "record_id": record_id,
            "description": f"done-by-worker-{unique_token}",
        },
    )

    processed = await WorkerEngine.drain_available_jobs()

    assert processed == 1

    row = await _queue_row(booted_app, job_id)
    rec = await _record_row(booted_app, record_id)

    assert row["state"] == "done"
    assert row["date_finished"] is not None
    assert rec["status"] == "done"
    assert rec["description"] == f"done-by-worker-{unique_token}"


@pytest.mark.asyncio
async def test_worker_uses_technical_context_and_persists_side_effects(booted_app, unique_token):
    key = f"worker.ctx.{unique_token}"

    job_id = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": key},
    )

    processed = await WorkerEngine.drain_available_jobs()
    value = await _param_value(booted_app, key)
    row = await _queue_row(booted_app, job_id)

    assert processed == 1
    assert row["state"] == "done"
    assert value is not None
    assert "uid=system" in value
    assert "su=1" in value
    assert "audit=1" in value


@pytest.mark.asyncio
async def test_worker_retry_then_success_after_backoff(booted_app, unique_token):
    marker = f"retry-once-{unique_token}"

    job_id = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_fail_once",
        kwargs={"marker": marker},
        max_retries=2,
    )

    processed_1 = await WorkerEngine.drain_available_jobs()
    row_1 = await _queue_row(booted_app, job_id)

    assert processed_1 == 1
    assert row_1["state"] == "retry"
    assert row_1["retries"] == 1
    assert row_1["retry_at"] is not None
    assert "planned first failure" in (row_1["error_log"] or "")

    await _set_retry_due_now(booted_app, job_id)

    processed_2 = await WorkerEngine.drain_available_jobs()
    row_2 = await _queue_row(booted_app, job_id)
    count_value = await _param_value(booted_app, f"worker.fail_once.{marker}")
    result_value = await _param_value(booted_app, f"worker.result.{marker}")

    assert processed_2 == 1
    assert row_2["state"] == "done"
    assert row_2["date_finished"] is not None
    assert count_value == "2"
    assert result_value == "ok"


@pytest.mark.asyncio
async def test_worker_moves_job_to_dlq_after_exhausting_retries(booted_app, unique_token):
    marker = f"retry-always-{unique_token}"

    job_id = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_fail_always",
        kwargs={"marker": marker},
        max_retries=2,
    )

    # intento 1 -> retry
    await WorkerEngine.drain_available_jobs()
    row = await _queue_row(booted_app, job_id)
    assert row["state"] == "retry"
    assert row["retries"] == 1

    # intento 2 -> retry
    await _set_retry_due_now(booted_app, job_id)
    await WorkerEngine.drain_available_jobs()
    row = await _queue_row(booted_app, job_id)
    assert row["state"] == "retry"
    assert row["retries"] == 2

    # intento 3 -> failed (DLQ)
    await _set_retry_due_now(booted_app, job_id)
    await WorkerEngine.drain_available_jobs()
    row = await _queue_row(booted_app, job_id)
    count_value = await _param_value(booted_app, f"worker.fail_always.{marker}")

    assert row["state"] == "failed"
    assert row["retries"] == 3
    assert row["date_finished"] is not None
    assert "planned permanent failure" in (row["error_log"] or "")
    assert count_value == "3"


@pytest.mark.asyncio
async def test_worker_recovers_orphaned_started_jobs(booted_app, unique_token):
    job_retry = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": f"orphan.retry.{unique_token}"},
        max_retries=3,
    )
    job_fail = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": f"orphan.fail.{unique_token}"},
        max_retries=1,
    )

    conn = await booted_app.storage.get_connection()
    await conn.execute(
        """
        UPDATE "ir_queue"
        SET state = 'started', retries = 0, max_retries = 3
        WHERE id = $1
        """,
        int(job_retry),
    )
    await conn.execute(
        """
        UPDATE "ir_queue"
        SET state = 'started', retries = 1, max_retries = 1
        WHERE id = $1
        """,
        int(job_fail),
    )

    await WorkerEngine.recover_orphaned_jobs()

    row_retry = await _queue_row(booted_app, job_retry)
    row_fail = await _queue_row(booted_app, job_fail)

    assert row_retry["state"] == "retry"
    assert row_retry["retry_at"] is not None
    assert "[RECOVERY]" in (row_retry["error_log"] or "")

    assert row_fail["state"] == "failed"
    assert row_fail["date_finished"] is not None
    assert "[DLQ]" in (row_fail["error_log"] or "")


@pytest.mark.asyncio
async def test_worker_claim_orders_by_priority_and_never_claims_same_job_twice(booted_app, unique_token):
    job_low = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": f"prio.low.{unique_token}"},
        priority=10,
    )
    job_high = await WorkerEngine.enqueue(
        model_name="test.record",
        method_name="worker_capture_context",
        kwargs={"key": f"prio.high.{unique_token}"},
        priority=99,
    )

    pool = await booted_app.storage.get_pool()

    first = await WorkerEngine._claim_next_job(pool)
    second = await WorkerEngine._claim_next_job(pool)
    third = await WorkerEngine._claim_next_job(pool)

    assert first is not None
    assert second is not None
    assert third is None

    assert int(first["id"]) == int(job_high)
    assert int(second["id"]) == int(job_low)
    assert int(first["id"]) != int(second["id"])

    row_high = await _queue_row(booted_app, job_high)
    row_low = await _queue_row(booted_app, job_low)

    assert row_high["state"] == "started"
    assert row_low["state"] == "started"