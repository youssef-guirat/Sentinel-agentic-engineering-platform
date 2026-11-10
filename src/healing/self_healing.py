"""Bounded self-healing: diagnose -> re-fix -> verify, with fresh context
each attempt and a 'try a DIFFERENT approach' constraint.
Concept: Self-Healing + Agent Loops (bounded termination)."""

import subprocess

from config.settings import SELF_HEAL_RETRIES
from src.agents.fixer import FixerAgent


def run_tests_in(workdir: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["python", "-m", "pytest", "-x", "-q"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return r.returncode == 0, (r.stdout + r.stderr)[-5_000:]


class SelfHealer:
    def __init__(self, router, workdir: str):
        self.router, self.workdir = router, workdir

    async def heal(
        self, issue: dict, investigation: str, failing_output: str, attempt: int
    ) -> tuple[bool, str]:
        agent = FixerAgent(self.router, self.workdir)  # FRESH context per attempt
        await agent.run(
            f"""The fix for issue #{issue.get("number")} is INCOMPLETE.
Self-heal attempt {attempt} of {SELF_HEAL_RETRIES}.

Investigation:
{investigation}

FAILING TEST OUTPUT:
{failing_output[-4000:]}

RULE: previous approaches did NOT work. Diagnose the actual failure from the
test output, choose a DIFFERENT strategy, fix the code, run the tests with
the run_tests tool until they pass, then commit."""
        )
        return run_tests_in(self.workdir)
