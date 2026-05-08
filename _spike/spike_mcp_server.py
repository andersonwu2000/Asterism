"""Spike: minimal FastMCP HTTP server with one trivial tool.

Run standalone:
    python -m _spike.spike_mcp_server

Then point claude CLI at http://127.0.0.1:8765/mcp via --mcp-config
(see spike_mcp_config.json) and ask it to call `ping`.
"""
from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("spike")

_START_TIME = time.time()
_CALL_COUNT = 0


@mcp.tool()
def ping(message: str = "hello") -> str:
    """Echo the message back with server metadata. Verifies the
    HTTP-transport MCP server is reachable from claude CLI."""
    global _CALL_COUNT
    _CALL_COUNT += 1
    pid = os.getpid()
    uptime = time.time() - _START_TIME
    return (
        f"pong: msg={message!r} pid={pid} "
        f"uptime={uptime:.1f}s calls={_CALL_COUNT}"
    )


if __name__ == "__main__":
    print(f"[spike] starting FastMCP HTTP server on 127.0.0.1:8765 "
          f"pid={os.getpid()}", flush=True)
    mcp.run(transport="streamable-http")
