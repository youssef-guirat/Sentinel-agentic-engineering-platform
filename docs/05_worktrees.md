# Worktrees — concepts: Git Worktrees, Parallel Agents

## Role

`WorktreeManager` gives every mutating agent its own directory and branch while
sharing one Git object database. The orchestrator creates separate fixer and
tester worktrees, runs those agents concurrently, merges the test branch into
the fix worktree, and verifies the result.

## Why it matters

Agents do not switch branches or stash each other's changes. A merge can still
conflict, but concurrent work cannot silently overwrite a peer's working tree.

## Development requirements

- The repository must have Git metadata and at least one commit.
- The default branch is detected rather than assumed.
- Stale worktree metadata is pruned before creating a worktree.
- Runtime worktrees live beside the repository and are not development state.
- The tester worktree is removed in a `finally` block; the fix worktree remains
  available for inspection when operating locally.

## Limitations

- Test-to-fix merges can conflict and currently stop the pipeline.
- Abrupt process termination can leave worktree directories behind.
- Remote push and PR behavior requires an authenticated GitHub workflow.

## Improvements

- Add an explicit conflict-resolution stage with human approval for ambiguity.
- Add a startup sweep for abandoned Sentinel branches after a retention period.
- Store structured cleanup evidence in the runtime task ledger.
