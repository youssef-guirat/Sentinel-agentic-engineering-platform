from src.agents.base import BaseAgent


class TesterAgent(BaseAgent):
    role, task_type = "tester", "test"
    system_prompt = """You write regression tests reproducing a reported bug.
Rules:
- Look at existing tests to copy style/import patterns (list_files, read_file).
- Write ONE focused test file under tests/ using pytest.
- The test MUST fail on the buggy code (that is its purpose).
- Commit with git add -A then git commit -m "test: reproduce <issue>".
Final result MUST be JSON:
{"test_file": "...", "test_names": [...], "summary": "..."}"""
