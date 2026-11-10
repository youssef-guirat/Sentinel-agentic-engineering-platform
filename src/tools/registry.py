"""Fail-closed in-process tools shared by runtime agents and MCP servers."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

ALL_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "grep",
        "edit_file",
        "write_file",
        "run_tests",
        "run_linter",
        "git",
    }
)
READ_TOOLS = frozenset({"read_file", "list_files", "grep"})
WRITE_TOOLS = frozenset({"edit_file", "write_file"})
CHECK_TOOLS = frozenset({"run_tests", "run_linter"})
IGNORED_PARTS = {".git", ".venv", "harness", "__pycache__", ".pytest_cache", ".ruff_cache"}


@dataclass(frozen=True)
class ToolPolicy:
    tools: frozenset[str]
    git_commands: frozenset[str] = frozenset()


ROLE_POLICIES = {
    "triage": ToolPolicy(frozenset()),
    "investigator": ToolPolicy(READ_TOOLS),
    "fixer": ToolPolicy(
        READ_TOOLS | WRITE_TOOLS | CHECK_TOOLS | {"git"},
        frozenset({"status", "diff", "add", "commit", "log"}),
    ),
    "tester": ToolPolicy(
        READ_TOOLS | WRITE_TOOLS | CHECK_TOOLS | {"git"},
        frozenset({"status", "diff", "add", "commit", "log"}),
    ),
    "reviewer": ToolPolicy(
        READ_TOOLS | CHECK_TOOLS | {"git"},
        frozenset({"status", "diff", "log"}),
    ),
    "base": ToolPolicy(READ_TOOLS),
}


def policy_for_role(role: str) -> ToolPolicy:
    """Return a role policy; unknown roles receive read-only capabilities."""
    return ROLE_POLICIES.get(role, ROLE_POLICIES["base"])


def _safe(workdir: str, path: str) -> Path:
    """Resolve *path* and prove it remains under the workspace root."""
    root = Path(workdir).resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {path}") from exc
    return candidate


def _visible(path: Path) -> bool:
    return not any(part in IGNORED_PARTS for part in path.parts)


def make_tools(
    workdir: str,
    *,
    allowed_tools: frozenset[str] | set[str] | None = None,
    allowed_git_commands: frozenset[str] | set[str] | None = None,
) -> dict:
    """Build a fail-closed registry limited to explicitly allowed capabilities."""
    selected = frozenset(allowed_tools) if allowed_tools is not None else ALL_TOOLS
    unknown = selected - ALL_TOOLS
    if unknown:
        raise ValueError(f"unknown tools in policy: {sorted(unknown)}")
    git_allowed = frozenset(allowed_git_commands or ())

    def read_file(path: str) -> str:
        return _safe(workdir, path).read_text(errors="replace")[:20_000]

    def list_files(path: str = ".") -> str:
        root = _safe(workdir, path)
        workspace = Path(workdir).resolve()
        files = [
            str(candidate.relative_to(workspace))
            for candidate in sorted(root.rglob("*"))
            if candidate.is_file() and _visible(candidate.relative_to(workspace))
        ]
        return "\n".join(files)[:8_000]

    def grep(pattern: str, path: str = ".") -> str:
        hits = []
        workspace = Path(workdir).resolve()
        for file in _safe(workdir, path).rglob("*"):
            relative = file.relative_to(workspace)
            if (
                file.is_file()
                and _visible(relative)
                and file.suffix in {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml"}
            ):
                for line_number, line in enumerate(
                    file.read_text(errors="replace").splitlines(), 1
                ):
                    if pattern in line:
                        hits.append(f"{relative}:{line_number}: {line.strip()}")
                    if len(hits) >= 100:
                        break
            if len(hits) >= 100:
                break
        return "\n".join(hits) or "no matches"

    def edit_file(path: str, old: str, new: str) -> str:
        target = _safe(workdir, path)
        source = target.read_text()
        if old not in source:
            return "old snippet not found — re-read the file and use exact text"
        target.write_text(source.replace(old, new, 1))
        return f"edited {path}"

    def write_file(path: str, content: str) -> str:
        target = _safe(workdir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} chars to {path}"

    def run_tests(pattern: str = "") -> str:
        command = ["python", "-m", "pytest", "-x", "-q", *shlex.split(pattern)]
        result = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return f"exit={result.returncode}\n{result.stdout}{result.stderr}"[-6_000:]

    def run_linter(files: str = ".") -> str:
        result = subprocess.run(
            ["python", "-m", "ruff", "check", files],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return f"exit={result.returncode}\n{result.stdout}{result.stderr}"[-3_000:]

    def git(cmd: str) -> str:
        parts = shlex.split(cmd)
        if not parts or parts[0] not in git_allowed:
            return f"not allowed; use one of {tuple(sorted(git_allowed))}"
        result = subprocess.run(
            ["git", *parts],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return f"exit={result.returncode}\n{result.stdout}{result.stderr}"[-3_000:]

    implementations = {
        function.__name__: function
        for function in (
            read_file,
            list_files,
            grep,
            edit_file,
            write_file,
            run_tests,
            run_linter,
            git,
        )
    }
    return {name: implementations[name] for name in selected}
