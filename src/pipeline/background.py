"""Background + headless execution. Submit work, walk away, check later.
Concepts: Background Agents, Headless Runs."""

import asyncio
import json
import logging
import uuid

from config.settings import ISSUE_TIMEOUT_SECONDS
from src.memory.store import MemoryStore
from src.observability import correlation_scope, get_logger, log_event

LOGGER = get_logger("background")


class BackgroundRunner:
    def __init__(self, orchestrator, store: MemoryStore | None = None, source: str = "local"):
        self.orch = orchestrator
        self.store = store or MemoryStore()
        self.source = source
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, issue: dict, *, force: bool = False) -> str | None:
        issue_number = issue.get("number", "unknown")
        issue_key = f"{self.source}#{issue_number}"
        if force:
            self.store.release_claim(issue_key)
        correlation_id = uuid.uuid4().hex
        task_id = self.store.claim_task(
            issue_key,
            f"#{issue_number} {issue.get('title', '')[:80]}",
            correlation_id,
        )
        if task_id is None:
            log_event(LOGGER, logging.INFO, "duplicate_issue_skipped", issue_key=issue_key)
            return None
        self._tasks[task_id] = asyncio.create_task(
            self._run(task_id, issue, correlation_id), name=f"sentinel-{task_id}"
        )
        return task_id

    async def _run(self, task_id: str, issue: dict, correlation_id: str):
        with correlation_scope(correlation_id):
            log_event(LOGGER, logging.INFO, "task_started", task_id=task_id)
            try:
                result = await asyncio.wait_for(
                    self.orch.handle_issue(issue), timeout=ISSUE_TIMEOUT_SECONDS
                )
                status = result.get("status", "done")
                self.store.finish_task(task_id, status, json.dumps(result, default=str))
            except TimeoutError:
                self.store.finish_task(task_id, "timed_out", "issue execution timed out")
            except asyncio.CancelledError:
                self.store.finish_task(task_id, "cancelled", "task cancelled")
                raise
            except Exception as exc:
                self.store.finish_task(task_id, "error", repr(exc))
                log_event(
                    LOGGER,
                    logging.ERROR,
                    "task_failed",
                    task_id=task_id,
                    error=type(exc).__name__,
                )
            finally:
                log_event(LOGGER, logging.INFO, "task_finished", task_id=task_id)

    async def wait(self, task_id: str) -> dict | None:
        task = self._tasks.get(task_id)
        if task:
            await asyncio.gather(task, return_exceptions=True)
        return self.store.task(task_id)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.done():
            return False
        self.store.finish_task(task_id, "cancelled", "task cancellation requested")
        task.cancel()
        return True

    async def wait_all(self):
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    def status(self) -> list[dict]:
        return self.store.tasks()
