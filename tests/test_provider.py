import asyncio
from types import SimpleNamespace

import pytest

from src.llm.provider import BudgetExceeded, LLMRouter, PromptCache, RateLimiter, estimate_tokens
from src.observability import correlation_scope


def test_token_estimate_counts_message_content():
    assert estimate_tokens([{"role": "user", "content": "x" * 20}]) == 5


def test_prompt_cache_is_model_specific():
    cache = PromptCache()
    messages = [{"role": "user", "content": "hello"}]
    cache.put_response(messages, "model-a", "answer")

    assert cache.get_response(messages, "model-a") == "answer"
    assert cache.get_response(messages, "model-b") is None


def test_rate_limiter_enforces_request_count():
    limiter = RateLimiter(rpm=1, tpm=100)

    assert limiter.available(10) is True
    limiter.record(10)
    assert limiter.available(10) is False


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    async def create(self, **kwargs):
        del kwargs
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))],
            usage=SimpleNamespace(
                prompt_tokens=4,
                completion_tokens=2,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


def fake_client(*outcomes):
    completions = FakeCompletions(outcomes)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_router_retries_then_falls_back_and_records_metrics():
    groq, groq_calls = fake_client(RuntimeError("temporary"), RuntimeError("temporary"))
    ollama, ollama_calls = fake_client("ok")
    delays = []
    metrics = []

    async def no_sleep(delay):
        delays.append(delay)

    router = LLMRouter(
        clients={"groq": groq, "ollama": ollama},
        sleep=no_sleep,
        metric_recorder=lambda **fields: metrics.append(fields),
    )
    with correlation_scope("request-123"):
        response = asyncio.run(router.complete([{"role": "user", "content": "hello"}]))

    assert response.provider == "ollama"
    assert groq_calls.calls == 2
    assert ollama_calls.calls == 1
    assert delays
    assert metrics[-1]["status"] == "success"
    assert metrics[-1]["correlation_id"] == "request-123"


def test_router_enforces_request_budget_before_call():
    client, calls = fake_client("unused")
    router = LLMRouter(clients={"groq": client}, max_requests=0)

    with pytest.raises(BudgetExceeded, match="request budget"):
        asyncio.run(router.complete([{"role": "user", "content": "hello"}]))

    assert calls.calls == 0


def test_router_enforces_token_budget_before_call():
    client, calls = fake_client("unused")
    router = LLMRouter(clients={"groq": client}, max_tokens=10)

    with pytest.raises(BudgetExceeded, match="token budget"):
        asyncio.run(
            router.complete(
                [{"role": "user", "content": "this prompt is already over the budget"}],
                max_tokens=10,
            )
        )

    assert calls.calls == 0
