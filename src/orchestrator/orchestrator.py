"""Central orchestrator: triage -> investigate -> (fix || test) -> merge ->
verify -> self-heal -> review -> PR.
Concepts: Orchestrator Workflow, Progressive Disclosure, Ultrathink,
Parallel Agents, Sub-Agents, Hooks, Self-Healing."""

import asyncio
import json
import logging
import subprocess

from config.settings import AGENT_STAGE_TIMEOUT_SECONDS, SELF_HEAL_RETRIES
from src.agents.fixer import FixerAgent
from src.agents.investigator import ULTRATHINK_ADDON, InvestigatorAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.tester import TesterAgent
from src.agents.triage import TriageAgent
from src.harness.hooks import HookManager
from src.healing.self_healing import SelfHealer, run_tests_in
from src.memory.consolidation import Consolidator
from src.memory.store import MemoryStore
from src.observability import get_correlation_id, get_logger, log_event
from src.orchestrator.worktrees import WorktreeManager

LOGGER = get_logger("orchestrator")


class SentinelOrchestrator:
    def __init__(self, router, repo_path: str, memory: MemoryStore | None = None, github=None):
        self.router = router
        self.repo = repo_path
        self.memory = memory or MemoryStore()
        self.consolidator = Consolidator(self.memory, router)
        self.worktrees = WorktreeManager(repo_path)
        self.github = github

    def _hooks(self, workdir: str) -> HookManager:
        """Quality gates: after every file edit, auto-run the linter and
        feed issues back into the agent. The agent can't forget quality."""
        h = HookManager()

        def lint_after_edit(ctx):
            if ctx["tool"] == "edit_file" and "path" in ctx.get("args", {}):
                r = subprocess.run(
                    ["python", "-m", "ruff", "check", ctx["args"]["path"]],
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if r.returncode != 0 and r.stdout.strip():
                    return f"Ruff found issues after your edit — fix them:\n{r.stdout[-800:]}"

        h.on("post_tool_use", lint_after_edit)
        return h

    async def _stage(self, name: str, awaitable):
        log_event(LOGGER, logging.INFO, "stage_started", stage=name)
        try:
            result = await asyncio.wait_for(awaitable, timeout=AGENT_STAGE_TIMEOUT_SECONDS)
        except TimeoutError:
            log_event(LOGGER, logging.ERROR, "stage_timed_out", stage=name)
            raise
        log_event(LOGGER, logging.INFO, "stage_completed", stage=name)
        return result

    async def handle_issue(self, issue: dict) -> dict:
        log: dict = {
            "issue": issue.get("number"),
            "correlation_id": get_correlation_id(),
        }
        n = issue.get("number", "x")

        # ---- 1. TRIAGE (progressive disclosure: title + labels only) ----
        tri = await self._stage(
            "triage",
            TriageAgent(self.router, self.repo, self.memory, self._hooks(self.repo)).run(
                f"Issue #{n}: {issue.get('title')}\nLabels: {issue.get('labels', [])}"
            ),
        )
        if not tri.success:
            log.update(status="triage_failed", reason=tri.reason)
            return log
        try:
            triage = json.loads(tri.result)
        except json.JSONDecodeError:
            triage = {"classification": "bug", "priority": "P2"}
        log["triage"] = triage
        if triage.get("classification") != "bug":
            log["status"] = "skipped_non_bug"
            return log

        # ---- 2. INVESTIGATE (ultrathink for P0/P1) ----
        inv_agent = InvestigatorAgent(self.router, self.repo, self.memory, self._hooks(self.repo))
        if triage.get("priority") in ("P0", "P1"):
            inv_agent.harness.task_type = "ultrathink"
            inv_agent.system_prompt += ULTRATHINK_ADDON
        inv = await self._stage(
            "investigate",
            inv_agent.run(f"Issue: {issue.get('title')}\n\n{issue.get('body', '')[:4000]}"),
        )
        if not inv.success:
            log.update(status="investigation_failed", reason=inv.reason)
            return log
        log["investigation"] = inv.result[:1500]

        # ---- 3. PARALLEL: fixer & tester in SEPARATE worktrees ----
        fix_wt = self.worktrees.create("fixer", f"sentinel/fix-{n}")
        test_wt = self.worktrees.create("tester", f"sentinel/test-{n}")
        try:
            fix_out, test_out = await self._stage(
                "fix_and_test",
                asyncio.gather(
                    FixerAgent(self.router, fix_wt, self.memory, self._hooks(fix_wt)).run(
                        f"Issue #{n}: {issue.get('title')}\n\nInvestigation:\n{inv.result}\n"
                        "Implement the fix in this worktree, then commit."
                    ),
                    TesterAgent(self.router, test_wt, self.memory, self._hooks(test_wt)).run(
                        f"Issue #{n}: {issue.get('title')}\n\nInvestigation:\n{inv.result}\n"
                        "Write a regression test under tests/ that reproduces this bug, "
                        "then commit."
                    ),
                ),
            )
            if not fix_out.success or not test_out.success:
                log.update(
                    status="agent_failed",
                    fixer_reason=fix_out.reason,
                    tester_reason=test_out.reason,
                )
                return log

            # ---- 4. MERGE tests into fix worktree, verify ----
            if not self.worktrees.merge(fix_wt, f"sentinel/test-{n}"):
                log["status"] = "merge_conflict"
                return log
            ok, output = run_tests_in(fix_wt)

            # ---- 5. SELF-HEALING (bounded loop) ----
            attempt = 0
            while not ok and attempt < SELF_HEAL_RETRIES:
                attempt += 1
                ok, output = await self._stage(
                    f"self_heal_{attempt}",
                    SelfHealer(self.router, fix_wt).heal(
                        issue, inv.result, output, attempt
                    ),
                )

            if not ok:
                log.update(status="failed_after_self_heal", tests=output[-1500:])
                if self.github:
                    await self.github.comment(
                        n,
                        f"🤖 Sentinel could not auto-fix this after "
                        f"{SELF_HEAL_RETRIES} self-heal attempts. Escalating to humans.",
                    )
                return log

            # ---- 6. REVIEW ----
            base_branch = self.worktrees.default_branch()
            rev = await self._stage(
                "review",
                ReviewerAgent(self.router, fix_wt, self.memory).run(
                    f"Review the current branch for issue #{n}. "
                    f"Use the git tool: git diff {base_branch}...HEAD"
                ),
            )
            log["review"] = rev.result[:800]
            try:
                review = json.loads(rev.result) if rev.success else {}
            except json.JSONDecodeError:
                review = {}
            if not review.get("approved", False):
                log.update(
                    status="review_rejected",
                    concerns=review.get("concerns", [rev.reason or "invalid reviewer result"]),
                )
                if self.github:
                    await self.github.comment(
                        n,
                        "Sentinel produced a candidate fix, but automated review rejected it. "
                        "The branch was not pushed.",
                    )
                return log

            # ---- 7. PR (or local branch if no GitHub) ----
            if self.github:
                branch = f"sentinel/fix-{n}"
                if not self.worktrees.push(fix_wt, branch):
                    log["status"] = "push_failed"
                    return log
                pr = await self.github.create_pr(
                    title=f"[Sentinel] Fix issue #{n}: {issue.get('title')}",
                    head=branch,
                    base=base_branch,
                    body=(
                        f"Autonomous fix by Sentinel.\n\nInvestigation:\n"
                        f"{inv.result[:1500]}\n\nReview:\n{rev.result[:800]}"
                    ),
                )
                log.update(status="pr_created", pr=pr.get("html_url"))
            else:
                log.update(status="done_local", branch=f"sentinel/fix-{n}")

            await self.consolidator.maybe_consolidate("fixer")
            await self.consolidator.maybe_consolidate("tester")
            return log
        finally:
            self.worktrees.remove(test_wt)  # keep fix worktree for inspection
