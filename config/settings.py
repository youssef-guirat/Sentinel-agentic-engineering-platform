"""Central configuration: providers, model routing, limits, tunables.
All providers are FREE. Cloud limits are enforced client-side by the router.
Update rpm/tpm/daily when providers change their free tiers."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = os.getenv("SENTINEL_DB_PATH", str(DATA_DIR / "sentinel.db"))


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "rpm": 30,
        "tpm": 12_000,
        "daily": 14_400,
    },
    "gemini": {  # OpenAI-compatible endpoint
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "rpm": 15,
        "tpm": 250_000,
        "daily": 1_500,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "rpm": 20,
        "tpm": 20_000,
        "daily": 1_000,
    },
    "ollama": {  # local, unlimited — final fallback
        "base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/v1",
        "key_env": None,
        "rpm": 10**6,
        "tpm": 10**9,
        "daily": 10**9,
    },
}

# task type -> ordered fallback chain "provider:model"
MODEL_ROUTES = {
    "triage": ["groq:llama-3.1-8b-instant", "gemini:gemini-2.0-flash", "ollama:llama3.1:8b"],
    "investigate": [
        "groq:llama-3.3-70b-versatile",
        "gemini:gemini-2.0-flash",
        "ollama:qwen2.5-coder:14b",
    ],
    "fix": [
        "groq:llama-3.3-70b-versatile",
        "openrouter:qwen/qwen-2.5-coder-32b-instruct:free",
        "ollama:qwen2.5-coder:14b",
    ],
    "test": ["groq:llama-3.1-8b-instant", "ollama:llama3.1:8b"],
    "review": ["groq:llama-3.3-70b-versatile", "gemini:gemini-2.0-flash", "ollama:llama3.1:8b"],
    "ultrathink": [
        "openrouter:deepseek/deepseek-r1:free",
        "groq:llama-3.3-70b-versatile",
        "ollama:qwen2.5:14b",
    ],
    "summarize": ["groq:llama-3.1-8b-instant", "ollama:llama3.1:8b"],
    "judge": ["gemini:gemini-2.0-flash", "groq:llama-3.3-70b-versatile", "ollama:llama3.1:8b"],
    "default": ["groq:llama-3.1-8b-instant", "ollama:llama3.1:8b"],
}

MAX_AGENT_STEPS = 40
SELF_HEAL_RETRIES = 3
CONSOLIDATE_AFTER = 20  # memories per agent before consolidation
CONTEXT_TOKENS = 8_000
OLLAMA_KEEPALIVE = "10m"  # keep model loaded => KV-cache reuse
POLL_SECONDS = 60

# Reliability controls. All are overridable without modifying source.
AGENT_STAGE_TIMEOUT_SECONDS = _float_env("SENTINEL_AGENT_STAGE_TIMEOUT", 900.0)
ISSUE_TIMEOUT_SECONDS = _float_env("SENTINEL_ISSUE_TIMEOUT", 3600.0)
HTTP_TIMEOUT_SECONDS = _float_env("SENTINEL_HTTP_TIMEOUT", 30.0)
HTTP_MAX_RETRIES = _int_env("SENTINEL_HTTP_MAX_RETRIES", 3)
RETRY_BASE_SECONDS = _float_env("SENTINEL_RETRY_BASE_SECONDS", 0.5)
LLM_MAX_REQUESTS_PER_RUN = _int_env("SENTINEL_LLM_MAX_REQUESTS", 200)
LLM_MAX_TOKENS_PER_RUN = _int_env("SENTINEL_LLM_MAX_TOKENS", 250_000)
LLM_RETRIES_PER_ROUTE = _int_env("SENTINEL_LLM_RETRIES_PER_ROUTE", 2)
LOG_LEVEL = os.getenv("SENTINEL_LOG_LEVEL", "INFO").upper()
