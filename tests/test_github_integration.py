import asyncio

import httpx
import pytest

from src.integrations.github import GitHubClient
from src.integrations.github_sync import sync_workflow_runs
from src.memory.store import MemoryStore


def test_github_retries_transient_failure():
    attempts = 0
    delays = []

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, request=request, json={"message": "temporary"})
        return httpx.Response(
            200,
            request=request,
            json={"number": 4, "title": "bug", "body": "details", "labels": []},
        )

    async def no_sleep(delay):
        delays.append(delay)

    client = GitHubClient("owner/repo", transport=httpx.MockTransport(handler), sleep=no_sleep)
    issue = asyncio.run(client.get_issue(4))

    assert issue["number"] == 4
    assert attempts == 2
    assert delays


def test_github_does_not_retry_permanent_client_failure():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, request=request, json={"message": "missing"})

    client = GitHubClient("owner/repo", transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.get_issue(99))

    assert attempts == 1


def test_workflow_runs_sync_into_dashboard_database(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            request=request,
            json={
                "workflow_runs": [
                    {
                        "id": 101,
                        "name": "Sentinel CI",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://example.invalid/run/101",
                        "head_branch": "main",
                        "event": "push",
                        "created_at": "2026-10-25T10:00:00Z",
                        "updated_at": "2026-10-25T10:01:00Z",
                    }
                ]
            },
        )

    store = MemoryStore(str(tmp_path / "dashboard.db"))
    client = GitHubClient("owner/repo", transport=httpx.MockTransport(handler))

    count = asyncio.run(sync_workflow_runs("owner/repo", store, client=client))
    row = store.db.execute("SELECT * FROM workflow_runs WHERE run_id=101").fetchone()

    assert count == 1
    assert row["conclusion"] == "success"
