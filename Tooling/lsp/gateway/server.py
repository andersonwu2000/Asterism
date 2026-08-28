"""The MCP server object — one FastMCP instance, shared by every tool.

Split out of `gateway.py` 2026-08-29 (A1-4a) unchanged. It exists so
`rpc.py`'s `@mcp.tool` decorators can reach the instance at import time
without importing the package facade (which imports `rpc` in turn):
this module is a leaf, and the facade re-exports `mcp`, so
`gateway.mcp._tool_manager` reads the same object it always did and the
tool roster is unchanged.

`_offload_to_thread` lives here for the same reason. It is a decorator,
so it has to resolve BEFORE the facade finishes executing, and it is
worn by both `rpc.py`'s four tools and `__init__`'s `validate_file` —
shared plumbing with consumers on both sides of the cut.
"""
from __future__ import annotations

import asyncio
import functools

from mcp.server.fastmcp import FastMCP


# ─── MCP tools ───────────────────────────────────

mcp = FastMCP("lsp")

# Same class of waste as asterism_tools (see its
# _drop_empty_capabilities): zero resources/prompts, but FastMCP
# advertises the capability anyway and clients surface dead discovery
# tools. Mirrored here rather than imported — the gateway must not
# pull in the spawn-side tool server module.
from mcp import types as _mcp_types  # noqa: E402

for _req in (_mcp_types.ListResourcesRequest,
             _mcp_types.ReadResourceRequest,
             _mcp_types.ListResourceTemplatesRequest,
             _mcp_types.ListPromptsRequest,
             _mcp_types.GetPromptRequest):
    mcp._mcp_server.request_handlers.pop(_req, None)


def _offload_to_thread(fn):
    """Wrap a sync function so it runs in `asyncio.to_thread`.

    Critical for FastMCP `@mcp.tool()` handlers because FastMCP's
    `call_fn_with_arg_validation` calls sync tool bodies INLINE on the
    asyncio event loop (verified 2026-05-12: just `return fn(**args)`
    with no thread pool). For tools that block (here: every one calls
    sync `_acquire_slot` with up to 120s polling), inline execution
    saturates the event loop under concurrent load — `/health` /
    `/register` / `/release` HTTP requests all queue behind in-flight
    tool calls and eventually time out at urllib's budget. The miniF2F
    20-problem wider pilot 2026-05-12 hit this with pool=15: 15
    concurrent claude.exe spawns × ~5 tool calls each saturated the
    loop, daemon-side `urlopen('/register')` timed out at 120s,
    propagated as TimeoutError → cascade classified as
    transient_timeout → spawn re-dispatched → loop.

    Wrapping with this decorator pushes each invocation onto
    `asyncio.to_thread` (default executor, contextvars propagate so
    `_session_ctx.get()` still resolves the X-Asterism-Session header).
    Event loop stays responsive; sync polling no longer blocks other
    handlers.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return wrapper
