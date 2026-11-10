"""BaseAgent: binds prompt + tools + model route + hooks to the harness.
Concept: Sub-Agents — isolated context per role."""

from src.harness.harness import AgentHarness, AgentOutput
from src.harness.hooks import HookManager
from src.tools.registry import make_tools, policy_for_role


class BaseAgent:
    role, task_type, system_prompt = "base", "default", ""

    def __init__(self, router, workdir, memory=None, hooks: HookManager | None = None):
        self.router, self.workdir, self.memory = router, workdir, memory
        policy = policy_for_role(self.role)
        tools = make_tools(
            workdir,
            allowed_tools=policy.tools,
            allowed_git_commands=policy.git_commands,
        )
        self.harness = AgentHarness(router, tools, task_type=self.task_type, hooks=hooks)

    async def run(self, task: str) -> AgentOutput:
        out = await self.harness.run(self.system_prompt, task)
        if self.memory:
            self.memory.add(
                self.role, "trace", f"task={task[:100]!r} success={out.success} steps={out.steps}"
            )
        return out
