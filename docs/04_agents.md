# Specialized Runtime Agents

Sentinel has triage, investigator, fixer, tester, and reviewer roles. Each has a
narrow prompt, task route, isolated runtime context, and a fail-closed capability
policy.

## Capabilities

- Triage: no repository tools.
- Investigator: read, list, and search.
- Fixer: read/write, tests, lint, and limited commit operations.
- Tester: read/write, tests, lint, and limited commit operations.
- Reviewer: read, tests, lint, and read-only Git operations.

`src/tools/registry.py` is authoritative at runtime. `.harness/scope.json` is the
machine-readable development mirror, and deterministic tests require them to
remain synchronized.

Unknown or newly generated roles default to read-only capabilities. Promoting a
dynamic role to mutation access requires a reviewed `capability_role` in its
specification; model-selected task type alone does not grant write authority.

## Prompt rules

Agents use role-specific methodology, a required final JSON schema, and negative
constraints. Prompt or protocol changes affect runtime behavior and therefore
require deterministic tests plus the provider-backed eval profile.
