# Verification Strategy

## Offline Gate

Run `python scripts/verify.py --offline`. It validates JSON state, checks Python
syntax without importing modules, enforces architecture rules, runs Ruff, and
runs deterministic pytest tests. It must not need a network connection, API
key, Ollama, GitHub repository, or writable production database.

## Feature Gate

Run `python scripts/verify_feature.py <feature-id>`. The script reads the
feature's named profiles, runs each profile, and writes `passing` plus timestamped
evidence only after every profile succeeds. Do not edit a feature directly to
claim passing status.

## Agent Evaluations

Run `python scripts/verify.py --agent-evals` only with explicit authorization.
This calls `evals/run_evals.py`, uses configured provider routes, consumes quota,
and is nondeterministic. Record provider, date, pass rate, and noteworthy model
failures. Agent evals supplement rather than replace deterministic tests.

## GitHub End-to-End

The issue-to-PR workflow has remote side effects. Exercise it manually or in a
designated sandbox repository. Never infer permission to run it against an
arbitrary repository from permission to run offline tests.

## Repair Guidance

- State failure: correct malformed or inconsistent harness JSON.
- Syntax failure: repair the named file before imports or tests.
- Architecture failure: remove the dependency back-edge or document a reviewed
  policy change.
- Ruff failure: fix the reported source; do not globally suppress the rule.
- Pytest failure: repair behavior; do not weaken the assertion without rationale.
- Agent eval failure: preserve artifacts, identify whether the defect is prompt,
  tool, environment, or model variance, and add a deterministic regression test.
