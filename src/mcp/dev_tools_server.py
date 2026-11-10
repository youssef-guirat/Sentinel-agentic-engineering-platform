"""MCP server exposing Sentinel's tools to ANY MCP client (Claude Code etc.).
Run: python -m src.mcp.dev_tools_server
Concept: MCP Servers — standardized tool access over a protocol."""

import os

from mcp.server.fastmcp import FastMCP

from src.tools.registry import make_tools

WORKDIR = os.environ.get("SENTINEL_WORKDIR", ".")
T = make_tools(WORKDIR)
mcp = FastMCP("sentinel-devtools")


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file inside the workspace root."""
    return T["read_file"](path)


@mcp.tool()
def grep(pattern: str, path: str = ".") -> str:
    """Search for a text pattern in the workspace."""
    return T["grep"](pattern, path)


@mcp.tool()
def list_files(path: str = ".") -> str:
    """List all files in the workspace."""
    return T["list_files"](path)


@mcp.tool()
def run_tests(pattern: str = "") -> str:
    """Run pytest in the workspace."""
    return T["run_tests"](pattern)


if __name__ == "__main__":
    mcp.run()
