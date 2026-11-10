import subprocess

from src.orchestrator.worktrees import WorktreeManager


def _git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def test_worktree_create_and_remove(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Sentinel Test")
    _git(repo, "config", "user.email", "sentinel@example.invalid")
    (repo / "README.md").write_text("baseline")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
    manager = WorktreeManager(str(repo))

    worktree = manager.create("tester", "sentinel/test-1")

    assert (tmp_path / "repo.worktrees" / "tester-sentinel-test-1").is_dir()
    manager.remove(worktree)
    assert not (tmp_path / "repo.worktrees" / "tester-sentinel-test-1").exists()


def test_worktree_recreate_cleans_stale_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Sentinel Test")
    _git(repo, "config", "user.email", "sentinel@example.invalid")
    (repo / "README.md").write_text("baseline")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
    manager = WorktreeManager(str(repo))

    first = manager.create("fixer", "sentinel/fix-7")
    second = manager.create("fixer", "sentinel/fix-7")

    assert first == second
    assert (tmp_path / "repo.worktrees" / "fixer-sentinel-fix-7").is_dir()
    assert manager.remove(second) is True
