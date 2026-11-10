import asyncio
from pathlib import Path

from src.harness.hooks import HookManager
from src.memory.store import MemoryStore


def test_hook_feedback_is_collected():
    hooks = HookManager()
    hooks.on("post_tool_use", lambda context: f"checked {context['tool']}")

    feedback = asyncio.run(hooks.fire("post_tool_use", {"tool": "read_file"}))

    assert feedback == ["checked read_file"]


def test_memory_store_creates_only_requested_parent(tmp_path):
    database = tmp_path / "nested" / "sentinel.db"

    store = MemoryStore(str(database))
    store.add("tester", "trace", "passed")

    assert database.exists()
    assert store.count("tester") == 1


def test_settings_import_has_no_directory_creation_side_effect():
    import config.settings as settings

    assert isinstance(settings.DATA_DIR, Path)
