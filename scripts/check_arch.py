"""Enforce Sentinel's machine-readable architectural boundaries."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE_PATH = ROOT / ".harness" / "scope.json"
RULES_PATH = ROOT / ".harness" / "arch-rules.json"
SOURCE_ROOTS = (ROOT / "src", ROOT / "cli", ROOT / "evals", ROOT / "skills", ROOT / "dashboard")


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _normal(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _domain_for_path(path: str, domains: list[dict]) -> str | None:
    return next(
        (
            domain["name"]
            for domain in domains
            if any(path.startswith(prefix) for prefix in domain["prefixes"])
        ),
        None,
    )


def _domain_for_module(module: str, domains: list[dict]) -> str | None:
    candidate = module.replace(".", "/") + "/"
    return _domain_for_path(candidate, domains)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def check() -> list[str]:
    scope = _load(SCOPE_PATH)
    rules = _load(RULES_PATH)
    domains = scope["domains"]
    errors: list[str] = []

    if not rules.get("rules"):
        errors.append("ARCH000: .harness/arch-rules.json has no rules")

    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.py"):
            relative = _normal(path)
            owner = _domain_for_path(relative, domains)
            if owner is None:
                errors.append(f"ARCH001: {relative} belongs to no declared domain")
                continue
            owner_policy = next(domain for domain in domains if domain["name"] == owner)
            allowed = set(owner_policy["may_import"]) | {owner}
            for line, module in _imports(path):
                target = _domain_for_module(module, domains)
                if target is not None and target not in allowed:
                    errors.append(
                        f"ARCH001: {relative}:{line} domain '{owner}' imports "
                        f"undeclared domain '{target}' via {module}"
                    )
                if module == "scripts" or module.startswith("scripts."):
                    errors.append(f"ARCH002: {relative}:{line} imports development module {module}")

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("Architecture check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
