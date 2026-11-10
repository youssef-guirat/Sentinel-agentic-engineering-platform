# Runtime Operations

## Reliability controls

| Environment variable | Default | Purpose |
|---|---:|---|
| `SENTINEL_AGENT_STAGE_TIMEOUT` | 900 seconds | Maximum duration of one agent stage |
| `SENTINEL_ISSUE_TIMEOUT` | 3600 seconds | Maximum duration of one complete issue |
| `SENTINEL_HTTP_TIMEOUT` | 30 seconds | One provider or GitHub HTTP request |
| `SENTINEL_HTTP_MAX_RETRIES` | 3 | GitHub retry ceiling |
| `SENTINEL_RETRY_BASE_SECONDS` | 0.5 seconds | Exponential-backoff base |
| `SENTINEL_LLM_RETRIES_PER_ROUTE` | 2 | Attempts before provider fallback |
| `SENTINEL_LLM_MAX_REQUESTS` | 200 | Per-process LLM request budget |
| `SENTINEL_LLM_MAX_TOKENS` | 250000 | Per-process combined token budget |
| `SENTINEL_LOG_LEVEL` | `INFO` | Structured runtime log level |
| `SENTINEL_DB_PATH` | `data/sentinel.db` | Runtime SQLite database location |

Sentinel's provider policy remains free-tier or local, so the enforceable cost
proxy is a hard request/token budget rather than a currency estimate. If paid
routes are introduced later, they require an explicit monetary budget and a
reviewed provider-policy change.

## Task lifecycle

`running` tasks terminate as `pr_created`, `done_local`, a named pipeline
failure, `review_rejected`, `timed_out`, `cancelled`, `error`, or `interrupted`.
Issue claims are durable so `watch` does not resubmit the same open issue every
minute. `fix --force` is the explicit operator override.

## Dashboard data

Run `python -m streamlit run dashboard/app.py`. Local model calls populate
`metrics`; local issue execution populates `tasks`. Use the dashboard sidebar or
`python -m cli.sentinel sync-runs --repo owner/repository` to pull GitHub Actions
metadata. Private repositories require `GITHUB_TOKEN`.
