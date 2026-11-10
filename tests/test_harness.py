import asyncio
from types import SimpleNamespace

from src.harness.harness import AgentHarness


class StubRouter:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def complete(self, messages, task_type="default"):
        del messages, task_type
        return SimpleNamespace(text=next(self.responses), provider="stub", model="stub")


def test_harness_returns_final_result():
    router = StubRouter(['{"thought":"done","action":"final","args":{},"result":"ok"}'])

    result = asyncio.run(AgentHarness(router, {}, max_steps=2).run("system", "task"))

    assert result.success is True
    assert result.result == "ok"
    assert result.steps == 1


def test_harness_executes_tool_then_finishes():
    router = StubRouter(
        [
            '{"thought":"read","action":"echo","args":{"value":"hello"}}',
            '{"thought":"done","action":"final","args":{},"result":"complete"}',
        ]
    )

    result = asyncio.run(
        AgentHarness(router, {"echo": lambda value: value}, max_steps=2).run("system", "task")
    )

    assert result.success is True
    assert result.trace[0]["output"].startswith("hello")


def test_harness_stops_at_configured_step_limit():
    router = StubRouter(["not json", "still not json"])

    result = asyncio.run(AgentHarness(router, {}, max_steps=2).run("system", "task"))

    assert result.success is False
    assert result.reason == "max_steps_reached"
    assert result.steps == 2
