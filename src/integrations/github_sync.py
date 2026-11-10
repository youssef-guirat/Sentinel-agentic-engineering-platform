"""Synchronize GitHub Actions run metadata into Sentinel's local database."""

from src.integrations.github import GitHubClient
from src.memory.store import MemoryStore


async def sync_workflow_runs(
    repo: str,
    store: MemoryStore,
    *,
    client: GitHubClient | None = None,
    limit: int = 50,
) -> int:
    github = client or GitHubClient(repo)
    runs = await github.workflow_runs(limit=limit)
    return store.upsert_workflow_runs(repo, runs)
