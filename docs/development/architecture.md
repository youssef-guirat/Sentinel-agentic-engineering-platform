# Development Harness Architecture

Sentinel has two intentionally separate harnesses.

The development harness is a version-controlled control plane for coding
agents. `CLAUDE.md` routes startup behavior, `feature_list.json` defines work,
`PROGRESS.md` persists continuity, `.harness/scope.json` defines boundaries,
and `scripts/verify.py` produces completion evidence.

The runtime harness under `src/harness/` is product code. It assembles prompts,
parses model actions, dispatches scoped tools, sanitizes tool output, manages
context, and terminates bounded loops. `src/orchestrator/` coordinates the
specialized agents around that runtime.

## Dependency Direction

Low-level domains (`security`, `tools`, `config`) do not import orchestration.
The runtime harness may use configuration and security. Agents may use the
runtime harness and tool registry. Orchestration may coordinate those domains.
The development harness is never a runtime dependency.

`scripts/check_arch.py` reads `.harness/scope.json`, parses Python imports with
the standard library AST, and rejects undeclared cross-domain dependencies.

## State Ownership

- Runtime traces and tasks: `data/sentinel.db` (untracked).
- Development feature state: `feature_list.json` (tracked).
- Current development checkpoint: `PROGRESS.md` (tracked).
- Durable rationale: `DECISIONS.md` (tracked).
- Temporary context handoff: `session-handoff.md` (tracked and replaceable).

## Naming

- `.harness/`: development policy data.
- `src/harness/`: runtime Python package.
- `.venv/`: canonical local Python environment.
- `harness/`: legacy environment, ignored and not used by scripts.

## Operational Control Plane

`src/observability/` supplies standard-library JSON logging and context-local
correlation IDs. The CLI creates one durable task per issue, the orchestrator
propagates the correlation context through agent stages, and the provider writes
token metrics through an injected persistence callback. This preserves the
dependency direction: the LLM domain does not import SQLite memory code.

GitHub Actions runs are external state. `src/integrations/github_sync.py` pulls
their metadata into the local database instead of pretending a hosted runner can
write to a workstation-local file.
