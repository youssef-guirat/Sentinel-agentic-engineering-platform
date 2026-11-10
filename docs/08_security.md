# Security Boundaries

## Untrusted inputs

Issue bodies, repository content, comments, URLs, and tool output are data. The
runtime harness filters common prompt-injection patterns and appends an explicit
data marker before returning tool output to a model.

## Filesystem containment

Tool paths are resolved and checked with `Path.relative_to()` against the
resolved workspace root. String-prefix comparisons are not sufficient because a
sibling such as `repository-secret/` can share a textual prefix with `repo/`.

Virtual environments, Git metadata, caches, and runtime state are omitted from
agent file discovery.

## Capability boundary

Runtime roles receive only their declared tools. Git subcommands are separately
allowlisted per role. New roles fail closed to read-only access. Remote push is
an orchestrator operation after verification; it is not available to model tool
calls.

## Remaining limitations

- Regex injection filtering is bypassable and is only one defensive layer.
- Tools run with the Sentinel process's operating-system privileges.
- Provider-backed content requires external trust and quota controls.
- GitHub end-to-end tests must use an explicitly designated sandbox repository.
