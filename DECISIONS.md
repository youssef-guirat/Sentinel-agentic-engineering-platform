# Development Decisions

## D001 — Separate development and runtime harnesses

The version-controlled root artifacts govern coding agents that modify Sentinel.
`src/harness/` governs agents created by Sentinel. Neither imports the other.

## D002 — Use `.venv`, not `harness/`, for Python isolation

The old root environment is ambiguous beside `src/harness/`. The canonical
Python 3.11.9 environment is `.venv`; `harness/` remains untouched for
recoverability but is ignored by Git and all verification scans.

## D003 — Split deterministic and live verification

Offline checks are the required completion gate. Provider-backed agent evals
are an additional opt-in gate because they require network access, credentials,
quota, and nondeterministic model output.

## D004 — Store scope as data and enforce it with code

`.harness/scope.json` declares domains, dependencies, role capabilities, and
risk levels. `scripts/check_arch.py` and deterministic tests enforce it.

## D005 — State transitions require evidence

Only `scripts/verify_feature.py` may promote a feature to `passing`; it records
the executed profile and timestamp. This prevents unsupported completion claims.

## D006 — Standardize on Python 3.11.9

Local bootstrap, version metadata, Ruff, and GitHub Actions all use Python
3.11.9. This matches the available workstation runtime and keeps local and CI
verification aligned.

## D007 — Pull remote workflow state into local operations storage

A GitHub-hosted runner cannot directly update a workstation-local SQLite file.
Sentinel treats GitHub Actions as external authoritative state and explicitly
pulls run metadata through the API into `workflow_runs`.

## D008 — Enforce durable issue claims and reviewer approval

Issue claims persist across polling cycles and process restarts to prevent
duplicate fixes. Operator retries require `--force`. A reviewer failure, invalid
review response, or explicit rejection stops the pipeline before push and PR.

## D009 — Use bounded free-tier budgets

Provider routes remain free-tier or local. Sentinel therefore enforces request
and token ceilings as the cost-control boundary, alongside bounded exponential
backoff, per-stage timeouts, and a whole-issue timeout.
