import asyncio

import pytest

from src.harness.harness import AgentOutput
from src.orchestrator.orchestrator import SentinelOrchestrator


def agent_class(result: str, *, success: bool = True, reason: str = ""):
    class Agent:
        def __init__(self, *args, **kwargs):
            del args, kwargs
            self.harness = type("Harness", (), {"task_type": "default"})()
            self.system_prompt = ""

        async def run(self, task):
            del task
            return AgentOutput(success, result=result, reason=reason)

    return Agent


class FakeWorktrees:
    def __init__(self, *, push=True, merge=True):
        self.push_result = push
        self.merge_result = merge
        self.pushed = False
        self.removed = []

    def create(self, agent, branch):
        return f"/tmp/{agent}-{branch.replace('/', '-')}"

    def merge(self, worktree, branch):
        del worktree, branch
        return self.merge_result

    def default_branch(self):
        return "main"

    def push(self, worktree, branch):
        del worktree, branch
        self.pushed = True
        return self.push_result

    def remove(self, path):
        self.removed.append(path)


class FakeGitHub:
    def __init__(self, *, pr_error=None):
        self.pr_error = pr_error
        self.pr_calls = 0
        self.comments = []

    async def create_pr(self, **kwargs):
        del kwargs
        self.pr_calls += 1
        if self.pr_error:
            raise self.pr_error
        return {"html_url": "https://example.invalid/pr/1"}

    async def comment(self, issue, body):
        self.comments.append((issue, body))


class FakeConsolidator:
    async def maybe_consolidate(self, agent):
        del agent


def build_orchestrator(monkeypatch, *, review_approved=True, push=True, github=None):
    import src.orchestrator.orchestrator as module

    monkeypatch.setattr(
        module,
        "TriageAgent",
        agent_class('{"classification":"bug","priority":"P2","complexity":"trivial"}'),
    )
    monkeypatch.setattr(
        module,
        "InvestigatorAgent",
        agent_class('{"root_cause":"bug","fix_strategy":"minimal"}'),
    )
    monkeypatch.setattr(module, "FixerAgent", agent_class('{"fixed":true}'))
    monkeypatch.setattr(module, "TesterAgent", agent_class('{"test_file":"tests/test_bug.py"}'))
    approved = "true" if review_approved else "false"
    monkeypatch.setattr(
        module,
        "ReviewerAgent",
        agent_class(f'{{"approved":{approved},"concerns":["review concern"]}}'),
    )
    monkeypatch.setattr(module, "run_tests_in", lambda worktree: (True, "passed"))

    orchestrator = SentinelOrchestrator.__new__(SentinelOrchestrator)
    orchestrator.router = object()
    orchestrator.repo = "."
    orchestrator.memory = object()
    orchestrator.consolidator = FakeConsolidator()
    orchestrator.worktrees = FakeWorktrees(push=push)
    orchestrator.github = github
    return orchestrator


def test_complete_orchestrator_flow_pushes_and_creates_pr(monkeypatch):
    github = FakeGitHub()
    orchestrator = build_orchestrator(monkeypatch, github=github)

    result = asyncio.run(
        orchestrator.handle_issue({"number": 8, "title": "bug", "body": "details", "labels": []})
    )

    assert result["status"] == "pr_created"
    assert orchestrator.worktrees.pushed is True
    assert github.pr_calls == 1
    assert orchestrator.worktrees.removed


def test_reviewer_rejection_blocks_push_and_pr(monkeypatch):
    github = FakeGitHub()
    orchestrator = build_orchestrator(monkeypatch, review_approved=False, github=github)

    result = asyncio.run(
        orchestrator.handle_issue({"number": 9, "title": "bug", "body": "details", "labels": []})
    )

    assert result["status"] == "review_rejected"
    assert orchestrator.worktrees.pushed is False
    assert github.pr_calls == 0
    assert github.comments


def test_push_failure_blocks_pull_request(monkeypatch):
    github = FakeGitHub()
    orchestrator = build_orchestrator(monkeypatch, push=False, github=github)

    result = asyncio.run(
        orchestrator.handle_issue({"number": 10, "title": "bug", "body": "", "labels": []})
    )

    assert result["status"] == "push_failed"
    assert github.pr_calls == 0


def test_pull_request_failure_is_not_reported_as_success(monkeypatch):
    github = FakeGitHub(pr_error=RuntimeError("GitHub unavailable"))
    orchestrator = build_orchestrator(monkeypatch, github=github)

    with pytest.raises(RuntimeError, match="GitHub unavailable"):
        asyncio.run(
            orchestrator.handle_issue(
                {"number": 11, "title": "bug", "body": "", "labels": []}
            )
        )


def test_self_healing_stops_after_configured_attempts(monkeypatch):
    import src.orchestrator.orchestrator as module

    orchestrator = build_orchestrator(monkeypatch)
    monkeypatch.setattr(module, "run_tests_in", lambda worktree: (False, "still failing"))

    attempts = []

    class AlwaysFailingHealer:

        def __init__(self, *args):
            del args

        async def heal(self, issue, investigation, output, attempt):
            del issue, investigation, output
            attempts.append(attempt)
            return False, "still failing"

    monkeypatch.setattr(module, "SelfHealer", AlwaysFailingHealer)

    result = asyncio.run(
        orchestrator.handle_issue({"number": 12, "title": "bug", "body": "", "labels": []})
    )

    assert result["status"] == "failed_after_self_heal"
    assert attempts == [1, 2, 3]
