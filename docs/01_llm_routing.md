# LLM Provider — concepts: API Keys, Tokens, Model Routing, Prompt Caching

## Role
Single entry point for all LLM calls. Holds one OpenAI-compatible client
per provider (Groq, Gemini, OpenRouter, Ollama) — one SDK, four free backends.

## How it works here
- **Routing**: each task type maps to an ordered chain. First available
  provider wins; on 429/error it is penalized (60s cooldown) and the next
  is tried. Ollama is the unlimited last resort.
- **Rate limits**: client-side sliding-window RPM/TPM counters mean we
  *avoid* 429s instead of just reacting to them.
- **Tokens**: estimated at chars/4 for budgeting; real counts read from
  API `usage` for accounting.
- **Run budgets**: request and token ceilings are checked before each provider
  call. Exhaustion fails closed with `BudgetExceeded` instead of silently
  consuming more quota.
- **Reliability**: each route receives bounded exponential-backoff retries,
  after which routing falls through to the next configured provider.
- **Telemetry**: successes, cache hits, and failures are recorded with provider,
  model, task type, token counts, timestamp, and correlation ID.
- **Prompt caching**: (a) prefix cache — repeated stable prefixes are
  detected and, with Ollama `keep_alive`, the server's KV cache is reused;
  (b) response cache — identical prompts replay for free (great for evals).

## Limitations
- char/4 token estimates are ~10% off; limits change without notice
- prefix cache is detection + accounting, not a true cross-process cache
- no cross-process daily-quota coordination or request prioritization
- single process only (limits are per-process)

## Improvements
- Use tiktoken / provider tokenizers for exact counts
- Persist rate-limit state to SQLite so multiple processes share budgets
- Add daily counters and alert before exhaustion
- Weighted routing: prefer provider with lowest current latency
