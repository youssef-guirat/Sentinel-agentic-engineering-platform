"""Git worktree isolation for Sentinel's mutating runtime agents."""

from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeManager:
    def __init__(self, repo: str):
        self.repo = Path(repo).resolve()
        result = self._git("rev-parse", "--is-inside-work-tree")
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise RuntimeError(f"not a Git repository: {self.repo}")
        self.root = self.repo.parent / f"{self.repo.name}.worktrees"
        self.root.mkdir(exist_ok=True)
        self._git("worktree", "prune")

    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def default_branch(self) -> str:
        remote = self._git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        if remote.returncode == 0 and "/" in remote.stdout.strip():
            return remote.stdout.strip().split("/", 1)[1]
        current = self._git("branch", "--show-current")
        return current.stdout.strip() or "main"

    def create(self, agent: str, branch: str, base: str | None = None) -> str:
        base = base or self.default_branch()
        path = (self.root / f"{agent}-{branch.replace('/', '-')}").resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValueError(f"worktree path escapes managed root: {path}") from exc
        if path.exists():
            removed = self._git("worktree", "remove", "--force", str(path))
            if removed.returncode != 0:
                raise RuntimeError(f"stale worktree cleanup failed: {removed.stderr}")
        result = self._git("worktree", "add", "-b", branch, str(path), base)
        if result.returncode != 0:  # branch may already exist
            result = self._git("worktree", "add", str(path), branch)
            if result.returncode != 0:
                raise RuntimeError(f"worktree add failed: {result.stderr}")
        return str(path)

    def merge(self, worktree: str, branch: str) -> bool:
        result = self._git("merge", branch, "--no-edit", cwd=worktree)
        return result.returncode == 0

    def push(self, worktree: str, branch: str) -> bool:
        result = self._git("push", "--set-upstream", "origin", branch, cwd=worktree)
        return result.returncode == 0

    def remove(self, path: str) -> bool:
        target = Path(path).resolve()
        try:
            target.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValueError(f"refusing to remove unmanaged worktree: {target}") from exc
        result = self._git("worktree", "remove", "--force", str(target))
        self._git("worktree", "prune")
        if result.returncode != 0 and target.exists():
            raise RuntimeError(f"worktree cleanup failed: {result.stderr}")
        return result.returncode == 0
