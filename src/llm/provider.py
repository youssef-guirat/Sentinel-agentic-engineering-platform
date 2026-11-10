"""LLM access layer: model routing, free-tier rate-limit fallback,
prompt caching, and usage accounting.
Concepts: API Keys, Tokens, Model Routing, Prompt Caching."""

import asyncio
import hashlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from openai import AsyncOpenAI

from config.settings import (
    HTTP_TIMEOUT_SECONDS,
    LLM_MAX_REQUESTS_PER_RUN,
    LLM_MAX_TOKENS_PER_RUN,
    LLM_RETRIES_PER_ROUTE,
    MODEL_ROUTES,
    OLLAMA_KEEPALIVE,
    PROVIDERS,
    RETRY_BASE_SECONDS,
)
from src.observability import get_correlation_id, get_logger, log_event

LOGGER = get_logger("llm")


class AllProvidersBusy(Exception):
    pass


class BudgetExceeded(Exception):
    pass


def estimate_tokens(messages) -> int:
    """~4 chars/token heuristic. Fine for budgeting; not billing-grade."""
    return sum(len(m.get("content", "")) for m in messages) // 4


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_prefix_tokens: int = 0
    response_cache_hits: int = 0


class RateLimiter:
    """Sliding-window RPM/TPM enforcement + cooldown after a 429."""

    def __init__(self, rpm: int, tpm: int):
        self.rpm, self.tpm = rpm, tpm
        self._reqs, self._toks = deque(), deque()
        self.cooldown_until = 0.0

    def _prune(self):
        now = time.time()
        while self._reqs and now - self._reqs[0] > 60:
            self._reqs.popleft()
        while self._toks and now - self._toks[0][0] > 60:
            self._toks.popleft()

    def available(self, est_tokens: int) -> bool:
        if time.time() < self.cooldown_until:
            return False
        self._prune()
        return len(self._reqs) < self.rpm and sum(t for _, t in self._toks) + est_tokens <= self.tpm

    def record(self, tokens: int):
        now = time.time()
        self._reqs.append(now)
        self._toks.append((now, tokens))

    def penalize(self, seconds=60):
        self.cooldown_until = time.time() + seconds


class PromptCache:
    """Two layers:
    1. PREFIX cache — detects a repeated stable prefix (system prompt/docs).
       On Ollama this pairs with keep_alive so the server reuses its KV cache.
       On Groq caching is automatic server-side; usage reports cached tokens.
    2. RESPONSE cache — exact-match prompt -> answer (free replay for
       identical requests: evals, repeated triage)."""

    def __init__(self):
        self.prefixes, self.responses = {}, {}

    @staticmethod
    def _prefix_key(messages):
        return hashlib.sha256(json.dumps(messages[:-1], sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _full_key(messages, model):
        return hashlib.sha256(
            f"{model}|{json.dumps(messages, sort_keys=True)}".encode()
        ).hexdigest()

    def seen_prefix(self, messages) -> bool:
        return self._prefix_key(messages) in self.prefixes

    def remember_prefix(self, messages):
        self.prefixes[self._prefix_key(messages)] = estimate_tokens(messages[:-1])

    def get_response(self, messages, model):
        return self.responses.get(self._full_key(messages, model))

    def put_response(self, messages, model, text):
        self.responses[self._full_key(messages, model)] = text


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool = False


class LLMRouter:
    """Routes a task type through an ordered provider chain.
    On rate-limit (429) or error, penalizes the provider and falls through
    to the next one. Local Ollama is the unlimited last resort."""

    def __init__(
        self,
        *,
        metric_recorder=None,
        clients: dict | None = None,
        sleep=asyncio.sleep,
        max_requests: int = LLM_MAX_REQUESTS_PER_RUN,
        max_tokens: int = LLM_MAX_TOKENS_PER_RUN,
    ):
        self.clients, self.limiters = {}, {}
        self.usage = defaultdict(Usage)
        self.cache = PromptCache()
        self.metric_recorder = metric_recorder
        self.sleep = sleep
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.total_requests = 0
        self.total_tokens = 0
        supplied = clients or {}
        for name, cfg in PROVIDERS.items():
            key = os.getenv(cfg["key_env"]) if cfg["key_env"] else "local"
            if name in supplied:
                self.clients[name] = supplied[name]
            elif clients is None and key:
                self.clients[name] = AsyncOpenAI(base_url=cfg["base_url"], api_key=key)
            if name in self.clients:
                self.limiters[name] = RateLimiter(cfg["rpm"], cfg["tpm"])
        if not self.clients:
            raise RuntimeError(
                "No provider available. Set GROQ_API_KEY / GEMINI_API_KEY / "
                "OPENROUTER_API_KEY, or start Ollama locally."
            )

    def _record(self, **fields) -> None:
        if not self.metric_recorder:
            return
        try:
            self.metric_recorder(correlation_id=get_correlation_id(), ts=time.time(), **fields)
        except Exception:
            log_event(LOGGER, logging.ERROR, "metric_record_failed", exc_info=True)

    def _reserve_budget(self, estimated_tokens: int) -> None:
        if self.total_requests >= self.max_requests:
            raise BudgetExceeded(f"LLM request budget exhausted ({self.max_requests})")
        if self.total_tokens + estimated_tokens > self.max_tokens:
            raise BudgetExceeded(
                f"LLM token budget would exceed {self.max_tokens}: "
                f"used={self.total_tokens}, requested={estimated_tokens}"
            )
        self.total_requests += 1

    async def complete(
        self,
        messages: list,
        task_type: str = "default",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        chain = MODEL_ROUTES.get(task_type, MODEL_ROUTES["default"])
        est = estimate_tokens(messages)

        # exact-match response cache (checked once, against preferred model)
        first_avail = next((r for r in chain if r.split(":", 1)[0] in self.clients), None)
        if first_avail:
            m = first_avail.split(":", 1)[1]
            hit = self.cache.get_response(messages, m)
            if hit is not None:
                provider = first_avail.split(":")[0]
                self.usage[provider].response_cache_hits += 1
                self._record(
                    provider=provider,
                    model=m,
                    task_type=task_type,
                    cache_hits=1,
                    status="cache_hit",
                )
                return LLMResponse(hit, provider, m, 0, 0, cached=True)

        for route in chain:
            provider, model = route.split(":", 1)
            client = self.clients.get(provider)
            if not client or not self.limiters[provider].available(est):
                continue
            prefix_reuse = self.cache.seen_prefix(messages)
            raw = None
            for attempt in range(1, LLM_RETRIES_PER_ROUTE + 1):
                self._reserve_budget(est + max_tokens)
                try:
                    kwargs = dict(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if provider == "ollama":
                        kwargs["extra_body"] = {"keep_alive": OLLAMA_KEEPALIVE}
                    raw = await asyncio.wait_for(
                        client.chat.completions.create(**kwargs), timeout=HTTP_TIMEOUT_SECONDS
                    )
                    break
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    self._record(
                        provider=provider,
                        model=model,
                        task_type=task_type,
                        requests=1,
                        status="error",
                    )
                    log_event(
                        LOGGER,
                        logging.WARNING,
                        "provider_attempt_failed",
                        provider=provider,
                        model=model,
                        attempt=attempt,
                        error=type(exc).__name__,
                    )
                    if "429" in str(exc) or "rate" in str(exc).lower():
                        self.limiters[provider].penalize()
                    if attempt < LLM_RETRIES_PER_ROUTE:
                        await self.sleep(RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
            if raw is None:
                continue
            text = raw.choices[0].message.content or ""

            in_tok = raw.usage.prompt_tokens if raw.usage else est
            out_tok = raw.usage.completion_tokens if raw.usage else max(1, len(text) // 4)
            u = self.usage[provider]
            u.requests += 1
            u.input_tokens += in_tok
            u.output_tokens += out_tok
            self.total_tokens += in_tok + out_tok
            if prefix_reuse:
                u.cached_prefix_tokens += est
            server_cached = (
                getattr(getattr(raw.usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
            )
            u.cached_prefix_tokens += server_cached

            self.cache.remember_prefix(messages)
            self.cache.put_response(messages, model, text)
            self.limiters[provider].record(in_tok + out_tok)
            self._record(
                provider=provider,
                model=model,
                task_type=task_type,
                requests=1,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_prefix=(est if prefix_reuse else 0) + server_cached,
                status="success",
            )
            return LLMResponse(text, provider, model, in_tok, out_tok)

        raise AllProvidersBusy(f"Every provider in chain {chain} is rate-limited.")

    def stats(self) -> dict:
        return {
            "providers": {p: u.__dict__ for p, u in self.usage.items()},
            "budget": {
                "requests_used": self.total_requests,
                "requests_limit": self.max_requests,
                "tokens_used": self.total_tokens,
                "tokens_limit": self.max_tokens,
            },
        }
