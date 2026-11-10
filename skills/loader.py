"""Skills: packaged capabilities loaded on demand.
Concept: Skills + Progressive Disclosure (loaded only when triage says so)."""

import json
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
DYNAMIC_DIR = SKILLS_DIR / "dynamic"


class Skill:
    def __init__(self, name, trigger, prompt, validation=""):
        self.name, self.trigger, self.prompt = name, trigger, prompt
        self.validation = validation

    def attach(self, agent):
        """Appends skill instructions to an agent's system prompt."""
        agent.system_prompt += f"\n\n[SKILL: {self.name}]\n{self.prompt}"


def load_skills() -> dict[str, Skill]:
    skills = {}
    for p in DYNAMIC_DIR.glob("*.json"):  # agent-designed skills
        spec = json.loads(p.read_text())
        keywords = spec.get("trigger_keywords", [p.stem])
        skills[p.stem] = Skill(p.stem, keywords, spec["system_prompt"])
    return skills


def match_skill(skills: dict[str, Skill], text: str) -> Skill | None:
    t = text.lower()
    for s in skills.values():
        if any(k.lower() in t for k in s.trigger):
            return s
    return None
