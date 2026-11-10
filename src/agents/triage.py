"""Concepts: Prompting (role-based + structured output), Model Routing (small model)."""

from src.agents.base import BaseAgent


class TriageAgent(BaseAgent):
    role, task_type = "triage", "triage"
    system_prompt = """You triage GitHub issues for a Python project.
Classify: bug | feature | question | duplicate.
Priority: P0 (critical) | P1 | P2 | P3.
Complexity: trivial | moderate | complex.
Your final result MUST be JSON:
{"classification": "...", "priority": "...", "complexity": "...", "reasoning": "..."}"""
