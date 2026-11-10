# Meta-Orchestrator — concept: Agents Managing Agents

## Role
An agent above the agents. It reads the task ledger, clusters failures by
keyword, finds weak spots (e.g., "auth" tasks succeed 30%), then *designs*
a new specialist agent — name, trigger keywords, system prompt, model route —
as a JSON spec saved to `skills/dynamic/`. `DynamicAgent.from_spec()`
instantiates specs at runtime. The system evolves its own roster.

## Limitations
- Keyword clustering is crude (no embeddings)
- Designed agents are registered but not auto-wired into routing
- No shadow-testing of new agents before promotion; no retirement policy

## Improvements
- Shadow-test each new agent on the very cases that motivated it; promote
  only if it beats the incumbent
- Add retirement: agents with zero triggers in N days get archived
- Let the meta-orchestrator also *edit* existing prompts (with eval gate)