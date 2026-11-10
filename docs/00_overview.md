# Sentinel — Overview

## Flow
GitHub issue → Triage (small model) → Investigate (ultrathink if P0/P1)
→ Fixer ∥ Tester (parallel, separate git worktrees)
→ merge → run tests → Self-Heal loop (max 3) → Reviewer → PR.

## Concept → File map (study guide)
| Concept | File(s) |
|---|---|
| Prompting / Sub-Agents | src/agents/*.py |
| Tokens / Context Window | src/harness/context.py, src/llm/provider.py |
| API Keys / Model Routing | config/settings.py, src/llm/provider.py |
| Prompt Caching | src/llm/provider.py (PromptCache) |
| MCP Servers | src/mcp/*.py |
| Claude.MD / Projects | CLAUDE.md |
| / Commands, CLI | cli/sentinel.py |
| Git Worktrees / Parallel Agents | src/orchestrator/worktrees.py |
| Skills | skills/ |
| Hooks / Harness Engineering | src/harness/ |
| Background Agents / Headless | src/pipeline/background.py, workflow yml |
| Progressive Disclosure / Ultrathink | src/orchestrator/orchestrator.py |
| Eval-Driven Tests | evals/ |
| Orchestrator Workflow | src/orchestrator/orchestrator.py |
| Memory Consolidation | src/memory/ |
| Agent Loops / Self-Healing | src/harness/harness.py, src/healing/ |
| Tool Poisoning | src/security/poisoning.py |
| Agent CI/CD | .github/workflows/ |
| Agents Managing Agents | src/orchestrator/meta.py |