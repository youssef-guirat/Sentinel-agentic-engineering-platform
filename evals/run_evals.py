"""Provider-backed repair evaluations with deterministic behavior checks."""

import asyncio
import subprocess
import sys
import tempfile
import types
from pathlib import Path

from evals.cases import CASES
from src.agents.fixer import FixerAgent
from src.llm.provider import LLMRouter

JUDGE_WARNING_THRESHOLD = 0.5


def load_module(source: str):
    module = types.ModuleType("case")
    exec(compile(source, "bug.py", "exec"), module.__dict__)
    return module


def initialize_repository(path: Path) -> None:
    commands = (
        ("init", "-b", "main"),
        ("config", "user.name", "Sentinel Eval"),
        ("config", "user.email", "sentinel-eval@example.invalid"),
        ("add", "bug.py"),
        ("commit", "-m", "eval: buggy baseline"),
    )
    for command in commands:
        subprocess.run(
            ["git", *command],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )


async def run_case(router, case) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "bug.py").write_text(case["code"], encoding="utf-8")
        initialize_repository(root)
        output = await FixerAgent(router, root).run(
            f"Fix this bug: {case['issue']}. The buggy code is in bug.py. Fix it and commit."
        )
        if not output.success:
            return False, f"agent failed: {output.reason}"
        try:
            fixed = (root / "bug.py").read_text(encoding="utf-8")
            ok = case["check"](load_module(fixed))
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "behavior check failed"

        response = await router.complete(
            [
                {
                    "role": "user",
                    "content": f"Rate this bug fix 0.0-1.0 for correctness and minimality. "
                    f"Reply with ONLY the number.\nBUG: {case['issue']}\nFIXED CODE:\n{fixed}",
                }
            ],
            task_type="judge",
            max_tokens=10,
        )
        try:
            if float(response.text.strip()[:3]) < JUDGE_WARNING_THRESHOLD:
                return True, "passed deterministic checks; low judge score"
        except ValueError:
            pass
        return True, "passed"


async def main(min_pass: float = 0.8):
    router = LLMRouter()
    results = []
    for case in CASES:
        ok, note = await run_case(router, case)
        results.append(ok)
        marker = "PASS" if ok else "FAIL"
        print(f"  {marker} {case['id']}: {note}")
    rate = sum(results) / len(results)
    print(f"\nEval pass rate: {rate:.0%} (gate: {min_pass:.0%})")
    print("Token stats:", router.stats())
    raise SystemExit(0 if rate >= min_pass else 1)


if __name__ == "__main__":
    asyncio.run(main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.8))
