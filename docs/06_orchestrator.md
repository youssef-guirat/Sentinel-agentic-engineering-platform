# Orchestrator — concepts: Orchestrator Workflow, Progressive Disclosure,
# Ultrathink

## Role
`handle_issue()` is the whole pipeline: triage → investigate →
(fix ∥ test) → merge → verify → self-heal → review → PR. Sub-agents never
talk to each other; all coordination flows through this class.

Every issue receives a correlation ID. Each agent stage is bounded by
`SENTINEL_AGENT_STAGE_TIMEOUT`, and the surrounding background runner bounds the
complete issue with `SENTINEL_ISSUE_TIMEOUT`. Structured JSON events identify
stage start, completion, failure, and timeout.

Reviewer approval is enforced. Invalid reviewer JSON, agent failure, or
`"approved": false` produces `review_rejected`; Sentinel comments on the issue
when GitHub is configured and does not push or create a pull request.

## Progressive disclosure
Triage sees *only* the title and labels (~50 tokens). The investigator gets
the body only after triage classifies it. Full file contents reach only the
agents that need them. Each stage earns more context.

## Ultrathink
For P0/P1 issues the investigator's route switches to a reasoning model
(DeepSeek-R1 free) and its prompt gains an explicit multi-phase reasoning
checklist (rejected hypotheses, minimal-vs-correct fix, side effects,
proving tests).

## Limitations
- The phase plan is static; a bad investigation isn't re-planned
- Single retry path; decision points are hardcoded
- PR body is a dump, not curated

## Improvements
- Dynamic planner: orchestrator LLM emits a DAG of phases per issue
- Re-investigate on repeated self-heal failure (currently only re-fixes)
- Human-in-the-loop gate for P0 PRs
