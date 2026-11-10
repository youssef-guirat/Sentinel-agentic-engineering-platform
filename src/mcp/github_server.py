"""MCP server for GitHub operations. Requires GITHUB_TOKEN + SENTINEL_REPO.
Concept: MCP Servers wrapping external APIs."""

import os

from mcp.server.fastmcp import FastMCP

from src.integrations.github import GitHubClient

gh = GitHubClient(os.environ.get("SENTINEL_REPO", "owner/repo"))
mcp = FastMCP("sentinel-github")


@mcp.tool()
async def get_issue(number: int) -> dict:
    """Fetch a GitHub issue's title, body and labels."""
    return await gh.get_issue(number)


@mcp.tool()
async def open_issues(label: str = "auto-fix") -> list[dict]:
    """List open issues with the given label."""
    return await gh.open_issues(label)


if __name__ == "__main__":
    mcp.run()
