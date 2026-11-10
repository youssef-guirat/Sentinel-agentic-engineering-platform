# Runtime Harness

## Role

`src/harness/harness.py` surrounds a model call with message assembly, bounded
steps, tool dispatch, JSON parsing and repair, security framing, hooks, and
context eviction. It is Sentinel product code, not the root development harness.

## Protocol

Small-model fallback uses one text JSON action per turn. The parser handles
common fences, trailing commas, and single quotes. Invalid output is returned to
the model with a compact repair instruction.

## Termination

`AgentHarness` stores and enforces its configured `max_steps`. Completion returns
an `AgentOutput`; exhaustion returns `success=False` with
`reason=max_steps_reached`. Deterministic tests cover both paths.

## Hooks and context

Hooks run at defined runtime events. Tool output is sanitized before entering
model context. Context eviction removes old tool output first and preserves the
system prompt.

## Limitations

- Repair cannot recover arbitrarily truncated JSON.
- Eviction is positional rather than relevance-scored.
- The current loop performs one tool action per model turn.
- Live provider behavior still requires the separate agent eval suite.
