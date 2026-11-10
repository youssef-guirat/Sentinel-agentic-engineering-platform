# Sentinel Development Progress

## Current State

- Last updated: 2026-10-25
- Branch: `main` in a newly initialized local repository
- Last commit: none; the downloaded project and harness are awaiting review
- Active feature: none
- Offline baseline: passing under the canonical `.venv`
- Supported environment: Python 3.11.9, enforced by `init.sh` and `init.ps1`

## Completed

- Added instructions, persistent state, scope, verification, and lifecycle subsystems.
- Added cross-platform bootstrap wrappers around one Python implementation.
- Added machine-readable architecture and runtime role-capability policies.
- Fixed the runtime harness step-limit defect and import-time data-directory side effect.
- Restricted triage, investigator, fixer, tester, reviewer, and unknown-role tools.
- Hardened filesystem containment and managed worktree deletion boundaries.
- Added trusted orchestrator push-before-PR behavior; model Git tools cannot push.
- Added 48 deterministic tests, all passing.
- Moved workflows under `.github/workflows/` and split offline CI from live evals.
- Normalized the worktree documentation filename and refreshed affected docs.
- Completed `feat-006-production-hardening`: versioned SQLite migrations,
  correlated JSON logs, model metrics, durable issue claims, dead-process
  recovery, bounded retries/timeouts/budgets, enforced reviewer rejection,
  GitHub Actions synchronization, and dashboard completion.

## Verification Evidence

- Harness state and JSON Schema: passed.
- Python syntax: passed.
- Architecture dependency rules: passed.
- Ruff: passed with no findings.
- Pytest: 48 passed.
- `feat-001` through `feat-004`: promoted by `scripts/verify_feature.py` with
  timestamped offline evidence.
- PowerShell bootstrap: created `.venv` with Python 3.11.9, synchronized all
  requirements, and passed `pip check` plus the complete offline gate.
- Installed application dependencies include pandas 3.0.6 and Streamlit 1.66.0.
- `feat-006-production-hardening`: promoted by `scripts/verify_feature.py` with
  complete offline evidence on 2026-10-25.
- Dashboard headless smoke test: HTTP 200 and `ok` from Streamlit health endpoint.
- GitHub retry and workflow synchronization: covered with deterministic mocked
  API integration tests; no external repository was mutated.
- Live agent eval: not run; `feat-005-live-agent-eval` is blocked.

## Blockers and Risks

- Provider-backed evals require explicit credentials or a running Ollama service.
- The local repository has no remote and no initial commit.
- A real GitHub issue-to-PR run and live Actions synchronization still require a
  user-designated sandbox repository.

## Next Steps

1. Review the initial diff and create the first commit if accepted.
2. Run `python scripts/verify.py --agent-evals --min-pass 0.8` in an authorized
   provider environment, then verify `feat-005-live-agent-eval`.
3. Exercise `sync-runs` and one issue-to-PR flow in an explicitly designated
   sandbox repository.
4. Configure a remote only if this folder should push to an upstream repository.

## Notes for Next Session

The initial migration predates a baseline commit, so the first four feature
records explicitly say `initial-uncommitted-bootstrap`. Once the initial commit
exists, future `--activate` operations record `HEAD` and enforce changed paths
against `allowed_paths` and `forbidden_paths`.
