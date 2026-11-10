import asyncio
import json
import logging
import sqlite3

from src.memory.store import SCHEMA_VERSION, MemoryStore
from src.observability import correlation_scope
from src.observability.logging import JsonFormatter
from src.pipeline.background import BackgroundRunner


class FastOrchestrator:
    async def handle_issue(self, issue):
        return {"status": "done_local", "issue": issue["number"]}


class SlowOrchestrator:
    async def handle_issue(self, issue):
        del issue
        await asyncio.Event().wait()


def test_database_migrates_existing_v1_schema(tmp_path):
    path = tmp_path / "legacy.db"
    database = sqlite3.connect(path)
    database.executescript("""
        CREATE TABLE memories(id INTEGER PRIMARY KEY, agent TEXT, kind TEXT, content TEXT, ts REAL);
        CREATE TABLE tasks(id TEXT PRIMARY KEY, issue TEXT, status TEXT, result TEXT, ts REAL);
        PRAGMA user_version=1;
    """)
    database.close()

    store = MemoryStore(str(path))

    assert store.schema_version == SCHEMA_VERSION
    tables = {
        row[0]
        for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"issue_claims", "metrics", "workflow_runs"} <= tables


def test_duplicate_claim_is_rejected_and_recovery_releases_it(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))
    first = store.claim_task("owner/repo#9", "#9 bug", "correlation-a")

    assert first
    assert store.claim_task("owner/repo#9", "#9 bug", "correlation-b") is None
    store.db.execute("UPDATE tasks SET owner_pid=-1 WHERE id=?", (first,))
    assert store.recover_interrupted() == 1
    assert store.task(first)["status"] == "interrupted"
    assert store.claim_task("owner/repo#9", "#9 retry", "correlation-c")


def test_forced_background_retry_releases_durable_claim(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))

    async def run():
        runner = BackgroundRunner(FastOrchestrator(), store, source="owner/repo")
        first = runner.submit({"number": 7, "title": "bug"})
        await runner.wait(first)
        assert runner.submit({"number": 7, "title": "bug"}) is None
        second = runner.submit({"number": 7, "title": "bug"}, force=True)
        await runner.wait(second)
        return first, second

    first, second = asyncio.run(run())

    assert first != second


def test_recovery_does_not_steal_task_from_live_process(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))
    task_id = store.claim_task("owner/repo#live", "live", "correlation-live")

    assert store.recover_interrupted() == 0
    assert store.task(task_id)["status"] == "running"


def test_background_runner_records_direct_execution(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))

    async def run():
        runner = BackgroundRunner(FastOrchestrator(), store, source="owner/repo")
        task_id = runner.submit({"number": 2, "title": "small bug"})
        return task_id, await runner.wait(task_id)

    task_id, task = asyncio.run(run())

    assert task_id
    assert task["status"] == "done_local"
    assert json.loads(task["result"])["issue"] == 2


def test_background_runner_supports_cancellation(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))

    async def run():
        runner = BackgroundRunner(SlowOrchestrator(), store)
        task_id = runner.submit({"number": 3, "title": "slow bug"})
        await asyncio.sleep(0)
        assert runner.cancel(task_id) is True
        return await runner.wait(task_id)

    task = asyncio.run(run())

    assert task["status"] == "cancelled"


def test_background_runner_enforces_issue_timeout(tmp_path, monkeypatch):
    import src.pipeline.background as background

    monkeypatch.setattr(background, "ISSUE_TIMEOUT_SECONDS", 0.001)
    store = MemoryStore(str(tmp_path / "runtime.db"))

    async def run():
        runner = BackgroundRunner(SlowOrchestrator(), store)
        task_id = runner.submit({"number": 5, "title": "slow bug"})
        return await runner.wait(task_id)

    task = asyncio.run(run())

    assert task["status"] == "timed_out"


def test_model_metrics_are_persisted_for_dashboard(tmp_path):
    store = MemoryStore(str(tmp_path / "runtime.db"))

    store.record_metric(
        correlation_id="correlation-1",
        provider="groq",
        model="model",
        task_type="fix",
        requests=1,
        input_tokens=10,
        output_tokens=4,
        cached_prefix=2,
        cache_hits=0,
        status="success",
    )

    metric = store.db.execute("SELECT * FROM metrics").fetchone()
    assert metric["correlation_id"] == "correlation-1"
    assert metric["input_tokens"] == 10


def test_structured_log_contains_correlation_id():
    formatter = JsonFormatter()
    record = logging.LogRecord("sentinel.test", logging.INFO, __file__, 1, "event", (), None)
    record.event_name = "unit_test"
    record.event_fields = {"answer": 42}

    with correlation_scope("correlation-42"):
        payload = json.loads(formatter.format(record))

    assert payload["correlation_id"] == "correlation-42"
    assert payload["event"] == "unit_test"
    assert payload["answer"] == 42
