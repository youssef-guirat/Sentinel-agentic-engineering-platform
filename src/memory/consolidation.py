"""Compress raw memories into compact summaries so agent context stays small.
Concept: Memory Consolidation."""

from config.settings import CONSOLIDATE_AFTER
from src.memory.store import MemoryStore

PROMPT = """Consolidate these agent memories into a compact summary.
Keep: facts, decisions, failure patterns, conventions.
Drop: duplicates and trivia. Max 150 words, plain text.

MEMORIES:
{mems}"""


class Consolidator:
    def __init__(self, store: MemoryStore, router):
        self.store, self.router = store, router

    async def maybe_consolidate(self, agent: str):
        """Called after agent runs. 20+ raw entries -> 1 compact summary."""
        if self.store.count(agent) < CONSOLIDATE_AFTER:
            return
        mems = "\n".join(r[0] for r in self.store.recent(agent, 100))
        resp = await self.router.complete(
            [{"role": "user", "content": PROMPT.replace("{mems}", mems)}],
            task_type="summarize",
            max_tokens=400,
        )
        self.store.replace_all(agent, resp.text)
