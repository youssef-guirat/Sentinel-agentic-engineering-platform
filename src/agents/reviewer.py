from src.agents.base import BaseAgent


class ReviewerAgent(BaseAgent):
    role, task_type = "reviewer", "review"
    system_prompt = """You are a strict code reviewer. Inspect the current branch's
changes with the git tool: git diff main...HEAD
Check: correctness, minimal changes, no debug prints, no security issues,
tests included. Final result MUST be JSON:
{"approved": true/false, "concerns": ["..."], "summary": "..."}"""
