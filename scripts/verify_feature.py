"""Run a feature's declared verification profiles and record evidence."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "feature_list.json"
PROFILES_PATH = ROOT / ".harness" / "verification.json"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _write_ledger(ledger: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.splitlines() if result.returncode == 0 else []


def _head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _scope_errors(feature: dict) -> list[str]:
    baseline = feature.get("baseline_commit", "")
    if not baseline:
        print(
            "Scope diff skipped for initial uncommitted bootstrap; future features require a baseline."
        )
        return []
    changed = set(_git_lines("diff", "--name-only", baseline, "HEAD"))
    changed.update(_git_lines("diff", "--name-only"))
    changed.update(_git_lines("diff", "--cached", "--name-only"))
    changed.update(_git_lines("ls-files", "--others", "--exclude-standard"))
    errors = []
    for path in sorted(changed):
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in feature["forbidden_paths"]):
            errors.append(f"forbidden path changed: {path}")
        elif not any(fnmatch.fnmatchcase(path, pattern) for pattern in feature["allowed_paths"]):
            errors.append(f"out-of-scope path changed: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_id")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="activate this feature after confirming its dependencies are passing",
    )
    args = parser.parse_args()

    ledger = _load(LEDGER_PATH)
    features = {feature["id"]: feature for feature in ledger["features"]}
    feature = features.get(args.feature_id)
    if feature is None:
        print(f"Unknown feature: {args.feature_id}")
        return 2

    unmet = [
        dependency
        for dependency in feature["dependencies"]
        if features[dependency]["status"] != "passing"
    ]
    if unmet:
        print(f"Cannot verify {args.feature_id}; dependencies are not passing: {unmet}")
        return 2

    if args.activate:
        active = [item["id"] for item in features.values() if item["status"] == "active"]
        if active and active != [args.feature_id]:
            print(f"Cannot activate {args.feature_id}; already active: {active}")
            return 2
        feature["status"] = "active"
        feature["baseline_commit"] = _head()
        feature["evidence"] = ""
        _write_ledger(ledger)
        print(f"Feature {args.feature_id} is active. Implement it before verification.")
        return 0

    if feature["status"] not in {"active", "passing"}:
        print(f"Feature {args.feature_id} must be active before verification.")
        return 2

    scope_errors = _scope_errors(feature)
    if scope_errors:
        print("Feature scope check failed:")
        for error in scope_errors:
            print(f"  - {error}")
        return 2

    profiles = _load(PROFILES_PATH)["profiles"]
    completed: list[str] = []
    for name in feature["verification"]:
        profile = profiles[name]
        command = [part.replace("{python}", sys.executable) for part in profile["args"]]
        print(f"=== {name}: {profile['description']} ===", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"Feature remains {feature['status']}; profile failed: {name}")
            return result.returncode
        completed.append(name)

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    feature["status"] = "passing"
    baseline = feature.get("baseline_commit") or "initial-uncommitted-bootstrap"
    feature["evidence"] = f"{stamp}: profiles passed: {', '.join(completed)}; baseline: {baseline}"
    _write_ledger(ledger)
    print(f"Feature {args.feature_id} is passing. Evidence recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
