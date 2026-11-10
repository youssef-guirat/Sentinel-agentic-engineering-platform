# Memory — concept: Memory Consolidation

## Role
`MemoryStore` (SQLite) logs every agent run. After 20 entries per agent,
`Consolidator` asks a small model to compress them into ≤150 words of facts,
decisions, failure patterns, conventions — then replaces the raw log.
Agents start each task with compact, distilled memory instead of a dump.

## Operational ledger

SQLite migrations are versioned with `PRAGMA user_version`. In addition to
memories, the database owns:

- `tasks`: direct and background issue execution, results, correlation IDs.
- `issue_claims`: atomic durable duplicate protection.
- `metrics`: provider requests, tokens, cache use, and outcome.
- `workflow_runs`: GitHub Actions status synchronized through the API.

At CLI startup, unfinished tasks whose owner process is no longer alive are
marked `interrupted` and their claims are released for a safe retry. Live worker
processes retain their claims. Completed claims remain durable; an operator must
use `fix --force` for an intentional rerun.

## Limitations
- Fixed threshold; consolidation quality never evaluated
- No semantic retrieval — everything is a flat summary
- Memories are per-agent; no cross-agent shared knowledge

## Improvements
- Embedding store (ChromaDB) for retrieval over full history
- Eval the consolidator: facts-recall test after compression
- Shared "project brain": conventions extracted once, loaded everywhere
