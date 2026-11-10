from typer.testing import CliRunner

import cli.sentinel as sentinel_cli
from src.memory.store import MemoryStore


class FakeRouter:
    def stats(self):
        return {"providers": {}, "budget": {}}


class FakeGitHub:
    async def get_issue(self, issue):
        return {"number": issue, "title": "small bug", "body": "details", "labels": []}


class FakeOrchestrator:
    async def handle_issue(self, issue):
        return {"status": "done_local", "issue": issue["number"]}


def test_fix_command_records_task_in_local_ledger(tmp_path, monkeypatch):
    store = MemoryStore(str(tmp_path / "cli.db"))
    monkeypatch.setattr(
        sentinel_cli,
        "_build",
        lambda repo: (FakeRouter(), FakeOrchestrator(), FakeGitHub(), store),
    )

    result = CliRunner().invoke(
        sentinel_cli.app,
        ["fix", "--issue", "6", "--repo", "owner/repo"],
    )

    assert result.exit_code == 0, result.output
    tasks = store.tasks()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "done_local"
    assert tasks[0]["issue_key"] == "owner/repo#6"
