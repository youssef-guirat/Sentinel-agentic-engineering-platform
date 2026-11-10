import json
from pathlib import Path

import pytest

from src.tools.registry import ROLE_POLICIES, make_tools, policy_for_role


def test_path_guard_rejects_sibling_with_shared_prefix(tmp_path):
    workspace = tmp_path / "repo"
    sibling = tmp_path / "repository"
    workspace.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret")
    tools = make_tools(str(workspace), allowed_tools={"read_file"})

    with pytest.raises(ValueError, match="escapes workspace"):
        tools["read_file"]("../repository/secret.txt")


def test_unknown_role_is_read_only(tmp_path):
    policy = policy_for_role("new-unreviewed-role")
    tools = make_tools(
        str(tmp_path),
        allowed_tools=policy.tools,
        allowed_git_commands=policy.git_commands,
    )

    assert set(tools) == {"read_file", "list_files", "grep"}


def test_reviewer_cannot_write_or_commit(tmp_path):
    policy = policy_for_role("reviewer")
    tools = make_tools(
        str(tmp_path),
        allowed_tools=policy.tools,
        allowed_git_commands=policy.git_commands,
    )

    assert "write_file" not in tools
    assert "edit_file" not in tools
    assert "not allowed" in tools["git"]('commit -m "no"')


def test_role_policy_matches_machine_readable_scope():
    scope = json.loads(
        (Path(__file__).parents[1] / ".harness" / "scope.json").read_text(encoding="utf-8")
    )

    for role, expected in scope["runtime_roles"].items():
        policy = ROLE_POLICIES[role]
        assert policy.tools == frozenset(expected["tools"])
        assert policy.git_commands == frozenset(expected["git_commands"])


def test_registry_rejects_unknown_tool(tmp_path):
    with pytest.raises(ValueError, match="unknown tools"):
        make_tools(str(tmp_path), allowed_tools={"shell"})
