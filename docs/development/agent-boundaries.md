# Runtime Agent Boundaries

Capabilities are fail-closed and defined in `src/tools/registry.py`. The
machine-readable mirror is `.harness/scope.json`.

| Role | Files | Execution | Git |
|---|---|---|---|
| Triage | None | None | None |
| Investigator | Read/search | None | None |
| Fixer | Read/write | Tests and lint | Status, diff, add, commit, log |
| Tester | Read/write | Tests and lint | Status, diff, add, commit, log |
| Reviewer | Read/search | Tests and lint | Status, diff, log |

The reviewer cannot edit or commit. Triage never needs repository capabilities.
The investigator gathers evidence but cannot mutate it. Fixer and tester work
only inside orchestrator-created worktrees.

Adding a tool or Git operation is a security change. Update the policy mirror,
implementation, tests, and this document together. Tools default to mutating and
non-concurrent unless deliberately classified otherwise.

External coding agents are governed separately by the active feature's
`allowed_paths` and `forbidden_paths`. Runtime permissions never grant an
external coding agent broader development authority.
