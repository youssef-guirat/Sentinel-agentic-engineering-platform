"""Idempotent bootstrap shared by Bash and PowerShell wrappers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
SUPPORTED_PYTHON = (3, 11, 9)


def venv_python() -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return VENV / relative


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"+ {' '.join(args)}", flush=True)
    return subprocess.run(args, cwd=ROOT, check=check)


def require_supported_python() -> None:
    current = sys.version_info[:3]
    if current != SUPPORTED_PYTHON:
        version = ".".join(map(str, current))
        raise SystemExit(
            f"Sentinel requires Python 3.11.9; bootstrap is running under {version}. "
            "Install Python 3.11.9 and rerun the platform init script."
        )


def ensure_git_repository() -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise SystemExit("Sentinel must be bootstrapped from a Git working tree.")


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        print(f"Creating canonical environment at {VENV}")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    return python


def relaunch_in_venv(python: Path, arguments: list[str]) -> None:
    if Path(sys.executable).resolve() == python.resolve():
        return
    completed = subprocess.run(
        [str(python), str(Path(__file__).resolve()), "--inside-venv", *arguments],
        cwd=ROOT,
        check=False,
    )
    raise SystemExit(completed.returncode)


def active_feature() -> str:
    ledger = json.loads((ROOT / "feature_list.json").read_text(encoding="utf-8"))
    active = [feature["id"] for feature in ledger["features"] if feature["status"] == "active"]
    return active[0] if active else "none"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--inside-venv", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    os.chdir(ROOT)
    require_supported_python()
    ensure_git_repository()
    if (ROOT / "harness" / "pyvenv.cfg").exists():
        print("Warning: legacy root environment 'harness/' is ignored; use '.venv/'.")

    python = venv_python()
    if args.check_only and not python.exists():
        raise SystemExit(".venv does not exist; run init without --check-only first.")
    if not args.check_only:
        python = ensure_venv()
    relaunch_args = []
    if args.skip_install:
        relaunch_args.append("--skip-install")
    if args.check_only:
        relaunch_args.append("--check-only")
    relaunch_in_venv(python, relaunch_args)

    if not args.skip_install and not args.check_only:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    run([sys.executable, "-m", "pip", "check"])
    result = run([sys.executable, "scripts/verify.py", "--offline"], check=False)
    print(f"Active feature: {active_feature()}")
    if result.returncode != 0:
        print("Bootstrap completed with a red baseline; repair it before adding scope.")
        return result.returncode
    print("Bootstrap complete. The offline baseline is green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
