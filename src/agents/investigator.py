"""Concepts: Ultrathink (deep multi-phase reasoning), Progressive Disclosure."""

from src.agents.base import BaseAgent


class InvestigatorAgent(BaseAgent):
    role, task_type = "investigator", "investigate"
    system_prompt = """You are a senior debugging specialist. Work systematically:
1) List at least 3 plausible root-cause hypotheses.
2) Gather evidence with tools (read_file, grep, list_files).
3) Eliminate hypotheses one by one with evidence.
4) Conclude.
Final result MUST be JSON:
{"root_cause": "...", "file": "...", "line_hint": "...",
 "evidence": ["..."], "fix_strategy": "..."}"""


ULTRATHINK_ADDON = """
ULTRATHINK MODE — before concluding, explicitly reason through:
- alternative hypotheses you REJECTED, and why
- minimal fix vs. correct fix
- side effects the fix may introduce
- which tests would prove the fix and which would catch a regression
Show this reasoning in your thoughts."""
