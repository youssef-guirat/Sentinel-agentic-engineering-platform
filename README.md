# Sentinel — Autonomous Multi-Agent Code Guardian

Sentinel triages labeled GitHub issues, investigates defects, creates fixes and
regression tests in parallel Git worktrees, runs a bounded self-healing loop,
reviews the result, and opens a pull request. Its configured routes use free-tier
cloud models with local Ollama fallback.

## Development setup

Sentinel requires Python 3.11.9 and a Git working tree.

```bash
./init.sh
```

On Windows PowerShell:

```powershell
.\init.ps1
```

Bootstrap creates `.venv`, installs `requirements.txt`, checks dependency
health, and runs the deterministic offline gate. The old root `harness/`
environment is legacy and intentionally ignored.

Read `CLAUDE.md`, `PROGRESS.md`, and `feature_list.json` before development.

## Verification

```bash
# Required deterministic completion gate
python scripts/verify.py --offline

# Verify and record one active feature
python scripts/verify_feature.py feat-001-development-harness

# Explicit opt-in: calls a provider or local Ollama
python scripts/verify.py --agent-evals --min-pass 0.8
```

Live agent evals are not part of ordinary startup because they use network
access, credentials, quota, and nondeterministic model output.

## Runtime configuration

Set at least one free cloud provider key, or run Ollama locally:

```bash
export GROQ_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
export GITHUB_TOKEN=...
```

Optional local fallback:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:14b
```

## Commands

```bash
python -m cli.sentinel fix --issue 42 --repo owner/repository
python -m cli.sentinel watch --repo owner/repository
python -m cli.sentinel status
python -m cli.sentinel sync-runs --repo owner/repository
python -m cli.sentinel eval 0.8
python -m cli.sentinel meta
python -m cli.sentinel mcp
```

Component documentation lives in `docs/`. Development-harness documentation
lives in `docs/development/`.

## Operations dashboard

Initialize the database and start the local dashboard:

```powershell
python -m cli.sentinel status
python -m streamlit run dashboard/app.py
```

Direct `fix` and background `watch` executions write task results and correlated
model metrics to `data/sentinel.db`. Pull GitHub Actions run status into that
same database with `sync-runs`, or enter `owner/repository` in the dashboard
sidebar and select **Sync workflow runs**. Set `GITHUB_TOKEN` for private repos.

Reliability limits can be configured with `SENTINEL_ISSUE_TIMEOUT`,
`SENTINEL_AGENT_STAGE_TIMEOUT`, `SENTINEL_HTTP_MAX_RETRIES`,
`SENTINEL_LLM_MAX_REQUESTS`, and `SENTINEL_LLM_MAX_TOKENS`.


## Project status

- ✅ Offline verification and 48 automated tests
- ✅ Development and runtime harness architecture
- ✅ Security, observability, recovery, and dashboard infrastructure
- ⏳ Local Ollama model evaluation
- ⏳ End-to-end GitHub issue-to-PR demonstration