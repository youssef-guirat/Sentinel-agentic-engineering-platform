# Verification, Evals, and CI/CD

## Deterministic CI

`.github/workflows/ci.yml` runs on pushes to `main` and pull requests. It installs
Python 3.11.9 dependencies and executes `python scripts/verify.py --offline`.
That gate validates development state, Python syntax, dependency direction,
Ruff, and pytest without calling a model provider.

## Provider-backed evals

`evals/` gives a fixer agent a temporary Git repository containing a known bug.
The generated repair is checked behaviorally, then optionally scored by an LLM
judge as a secondary signal. The deterministic behavior result controls the
case outcome.

`.github/workflows/live-evals.yml` is manual. It runs the offline gate first,
then executes the configured pass-rate gate with repository secrets. This keeps
ordinary pull requests independent of provider uptime and quota.

## Auto-fix workflow

`.github/workflows/sentinel-fix.yml` responds to `auto-fix` issues, runs offline
verification, configures a bot Git identity, and starts the headless pipeline.
The orchestrator pushes the verified fix branch through trusted code before the
GitHub client creates a pull request; model-facing Git tools cannot push.

## Local dashboard synchronization

GitHub Actions cannot directly modify SQLite on a developer workstation.
Sentinel therefore pulls authoritative workflow-run metadata through the GitHub
API and upserts it into the local `workflow_runs` table:

```bash
python -m cli.sentinel sync-runs --repo owner/repository
```

The dashboard exposes the same operation in its sidebar. Task and model metrics
are recorded directly for local `fix` and `watch` executions; remote workflow
status is synchronized explicitly and remains read-only.

## Evidence

Offline success is necessary for every feature. Live eval evidence must include
date, provider route, configured threshold, pass rate, and notable failures.
