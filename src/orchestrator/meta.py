"""Meta-orchestrator: an agent that manages the agent roster.
It analyzes failure clusters, DESIGNS new specialized agents (spec JSON),
and registers them. Concept: Agents Managing Agents."""

import json
from pathlib import Path

from src.agents.base import BaseAgent
from src.harness.parser import OutputParser, ParseError
from src.tools.registry import make_tools, policy_for_role

DYNAMIC_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "dynamic"

DESIGN_PROMPT = """You design AI agents for an autonomous bug-fixing system.

Performance analysis found a weakness:
{analysis}

Failed examples:
{examples}

Design ONE new specialized agent to fill this gap. Respond ONLY with JSON:
{{"name": "snake_case_name", "trigger_keywords": ["..."],
  "system_prompt": "detailed system prompt with rules and required final JSON",
  "task_type": "fix|investigate|review|test|default",
  "rationale": "why this agent will help"}}"""


class DynamicAgent(BaseAgent):
    """An agent whose identity comes from a spec file, not code."""

    @classmethod
    def from_spec(cls, spec: dict, router, workdir, memory=None):
        a = cls(router, workdir, memory)
        a.role = spec["name"]
        a.task_type = spec.get("task_type", "default")
        a.system_prompt = spec["system_prompt"]
        capability_role = spec.get("capability_role", "base")
        policy = policy_for_role(capability_role)
        a.harness.tools = make_tools(
            workdir,
            allowed_tools=policy.tools,
            allowed_git_commands=policy.git_commands,
        )
        a.harness.task_type = a.task_type
        return a


class MetaOrchestrator:
    def __init__(self, router, store, repo: str):
        self.router, self.store, self.repo = router, store, repo
        DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)

    async def run_cycle(self) -> dict:
        # 1. ANALYZE: failure clusters by keyword in task ledger
        rows = self.store.db.execute("SELECT issue, status FROM tasks").fetchall()
        clusters: dict[str, list] = {}
        for issue, status in rows:
            for w in issue.lower().replace("#", " ").split():
                if len(w) > 4:
                    clusters.setdefault(w, []).append(status)
        weak = {
            w: s
            for w, s in clusters.items()
            if len(s) >= 3 and s.count("pr_created") / len(s) < 0.5
        }

        report = {"analyzed_tasks": len(rows), "weak_clusters": list(weak)}
        if not weak:
            return report

        # 2. DESIGN: a new agent per weakness
        created = []
        for word, statuses in list(weak.items())[:2]:
            resp = await self.router.complete(
                [
                    {
                        "role": "user",
                        "content": DESIGN_PROMPT.replace(
                            "{analysis}",
                            f"tasks mentioning '{word}' succeed "
                            f"{statuses.count('pr_created')}/{len(statuses)} times",
                        ).replace(
                            "{examples}",
                            "\n".join(r[0] for r in rows if word in r[0].lower())[:1500],
                        ),
                    }
                ],
                task_type="ultrathink",
                max_tokens=1500,
            )
            try:
                spec = OutputParser().parse(resp.text)
            except ParseError:
                continue
            path = DYNAMIC_DIR / f"{spec.get('name', 'agent')}.json"
            path.write_text(json.dumps(spec, indent=2))
            created.append(spec.get("name"))
        report["created_agents"] = created
        return report

    def roster(self) -> list[str]:
        return [p.stem for p in DYNAMIC_DIR.glob("*.json")]
