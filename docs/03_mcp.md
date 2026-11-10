# MCP Servers — concept: Model Context Protocol

## Role
`src/mcp/dev_tools_server.py` and `github_server.py` expose Sentinel's tools
over MCP, so external clients (Claude Code, other MCP hosts) can use the
exact same capabilities Sentinel's agents use. Tools are defined once in
`src/tools/registry.py` and served two ways: in-process and via MCP.

## How it works
FastMCP wraps typed Python functions; the server runs on stdio and speaks
JSON-RPC. `SENTINEL_WORKDIR` env var sets the sandbox root.

## Limitations
- Tool definitions duplicated between registry and MCP decorators
- No MCP resources or prompt templates exposed yet
- Sentinel's own harness calls tools in-process (not through MCP) —
  MCP here is an *export* surface, not the internal bus

## Improvements
- Make the harness a real MCP *client* so internal and external tool access
  share one protocol
- Generate MCP tool wrappers from the registry automatically
- Add auth + SSE transport for remote serving