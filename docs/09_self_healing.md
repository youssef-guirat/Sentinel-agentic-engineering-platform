# Self-Healing — concepts: Agent Loops, Self-Healing, Background, Headless

## Role
Two loops: (1) the **harness loop** — observe → think → act → feedback,
bounded by MAX_AGENT_STEPS; (2) the **heal loop** — tests fail → diagnose
from test output → re-fix with a *different strategy* → re-verify, bounded
by SELF_HEAL_RETRIES=3, then escalate to humans via a GitHub comment.

## Key design choices
- Each heal attempt gets a **fresh agent context** (no contamination from
  the failed attempt)
- The heal prompt includes prior failure output and explicitly demands a
  different approach — prevents identical retries

## Background & headless
`BackgroundRunner` tracks tasks in SQLite; the GitHub Action runs the same
pipeline with zero human interaction.

Direct `fix` executions now use the same runner and ledger. Issue claims prevent
the polling loop, manual commands, and restarts from processing the same issue
twice. Tasks support cancellation and a whole-issue timeout; interrupted tasks
are recovered at the next CLI startup.

## Limitations
- No loop detection (agent could ping-pong between two bad edits)
- Diagnosis is implicit in the fixer prompt, not a separate step
- Escalation is a comment; no structured handoff artifact

## Improvements
- Embedding-based loop detector on action traces
- Separate diagnostician agent producing a root-cause-of-failure report
- Human handoff bundle: diff + failing tests + all heal attempts
