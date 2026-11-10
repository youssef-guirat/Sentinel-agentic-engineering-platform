"""Deterministic and provider-backed verification entry point."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
PYTHON_DIRS = ("config", "src", "cli", "evals", "skills", "dashboard", "scripts", "tests")
REQUIRED_FEATURE_FIELDS = {
    "id",
    "name",
    "behavior",
    "dependencies",
    "status",
    "owner",
    "risk_level",
    "allowed_paths",
    "forbidden_paths",
    "verification",
    "done_criteria",
    "baseline_commit",
    "evidence",
}
VALID_STATES = {"planned", "active", "blocked", "passing"}


def _load_json(relative: str) -> dict:
    path = ROOT / relative
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_state() -> list[str]:
    errors: list[str] = []
    required = (
        "CLAUDE.md",
        "PROGRESS.md",
        "feature_list.json",
        "feature_list.schema.json",
        "session-handoff.md",
        ".harness/scope.json",
        ".harness/arch-rules.json",
        ".harness/verification.json",
    )
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required harness file: {relative}")

    for relative in (
        "feature_list.json",
        "feature_list.schema.json",
        ".harness/scope.json",
        ".harness/arch-rules.json",
        ".harness/verification.json",
    ):
        try:
            _load_json(relative)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON in {relative}: {exc}")

    if errors:
        return errors

    ledger = _load_json("feature_list.json")
    schema = _load_json("feature_list.schema.json")
    for error in Draft202012Validator(schema).iter_errors(ledger):
        location = ".".join(str(part) for part in error.absolute_path) or "root"
        errors.append(f"feature schema at {location}: {error.message}")
    profiles = set(_load_json(".harness/verification.json")["profiles"])
    features = ledger.get("features")
    if not isinstance(features, list) or not features:
        return ["feature_list.json must contain a non-empty features array"]

    identifiers = [feature.get("id") for feature in features]
    if len(identifiers) != len(set(identifiers)):
        errors.append("feature IDs must be unique")
    active = [feature.get("id") for feature in features if feature.get("status") == "active"]
    if len(active) > 1:
        errors.append(f"only one feature may be active; found {active}")

    known = set(identifiers)
    pattern = re.compile(r"^feat-[0-9]{3}-[a-z0-9-]+$")
    for index, feature in enumerate(features):
        missing = REQUIRED_FEATURE_FIELDS - set(feature)
        if missing:
            errors.append(f"feature {index} missing fields: {sorted(missing)}")
            continue
        identifier = feature["id"]
        if not isinstance(identifier, str) or not pattern.fullmatch(identifier):
            errors.append(f"invalid feature id: {identifier!r}")
        if feature["status"] not in VALID_STATES:
            errors.append(f"{identifier}: invalid status {feature['status']!r}")
        unknown_dependencies = set(feature["dependencies"]) - known
        if unknown_dependencies:
            errors.append(f"{identifier}: unknown dependencies {sorted(unknown_dependencies)}")
        unknown_profiles = set(feature["verification"]) - profiles
        if unknown_profiles:
            errors.append(f"{identifier}: unknown verification profiles {sorted(unknown_profiles)}")
        if not feature["allowed_paths"]:
            errors.append(f"{identifier}: allowed_paths must not be empty")
        if not feature["done_criteria"]:
            errors.append(f"{identifier}: done_criteria must not be empty")
        if feature["status"] == "passing" and not feature["evidence"].strip():
            errors.append(f"{identifier}: passing feature has no evidence")

    if (ROOT / ".githubworkflowssentinel-fix.yml").exists():
        errors.append("flattened workflow remains at .githubworkflowssentinel-fix.yml")
    return errors


def check_syntax() -> list[str]:
    errors: list[str] = []
    for directory in PYTHON_DIRS:
        root = ROOT / directory
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except (OSError, SyntaxError, UnicodeError) as exc:
                errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return errors


def run(name: str, args: list[str]) -> bool:
    print(f"\n=== {name} ===", flush=True)
    completed = subprocess.run(args, cwd=ROOT, check=False)
    return completed.returncode == 0


def offline() -> bool:
    ok = True
    print("=== Harness state ===")
    state_errors = validate_state()
    if state_errors:
        ok = False
        for error in state_errors:
            print(f"  - {error}")
    else:
        print("Harness state passed.")

    print("\n=== Python syntax ===")
    syntax_errors = check_syntax()
    if syntax_errors:
        ok = False
        for error in syntax_errors:
            print(f"  - {error}")
    else:
        print("Python syntax passed.")

    checks = (
        ("Architecture", [sys.executable, "scripts/check_arch.py"]),
        (
            "Ruff",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "config",
                "src",
                "cli",
                "evals",
                "skills",
                "dashboard",
                "scripts",
                "tests",
            ],
        ),
        ("Pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
    )
    for name, args in checks:
        ok = run(name, args) and ok
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--agent-evals", action="store_true")
    mode.add_argument("--all", action="store_true")
    parser.add_argument("--min-pass", type=float, default=0.8)
    args = parser.parse_args()

    success = True
    if args.offline or args.all:
        success = offline()
    if args.agent_evals or args.all:
        success = (
            run(
                "Provider-backed agent evals",
                [sys.executable, "-m", "evals.run_evals", str(args.min_pass)],
            )
            and success
        )

    print(f"\nVerification {'passed' if success else 'failed'}.")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
