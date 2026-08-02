"""The framework's tool surface for agents, over MCP (stdio).

Why this exists rather than a shell allowlist. The claude CLI can express
"this module, any arguments" (`Bash(python -m Tooling.knowledge.loogle *)`)
and enforces it before the tool runs. The Antigravity CLI cannot: its
`command` matcher was MEASURED to take an exact literal or `*` and nothing
between (2026-07-30, seven probes), so the only expressible options there
are "no shell at all" or "any shell command". We ran with `command(*)`, and
within a day it cost a Strategist wake 32 minutes to an agent-authored
`python -c` loop that scanned to 10**15 — a compute channel nobody had
thought to fence, because the write channel had been the whole worry.

Patching that channel-by-channel is a losing game: writes yesterday,
compute today. The class-level fix is to stop granting a shell and move
the whitelist to a layer that can express it — this module. The framework
owns the command line; agents supply typed parameters; timeouts, output
caps and the tool list are all ours. What an agent may do is exactly the
set of functions below.

Measured agy semantics that make this work (`llm/antigravity_cli.py`
carries the full matrix): `mcp` permissions ARE enforced headless — with
no allow rule the call is auto-denied — and `mcp(*)` grants the server.
Per-server scoping (`mcp(<name>)`) does NOT match, which costs nothing:
the server is ours, so "every MCP tool" already means "every tool we chose
to expose".

Transport is stdio: the client spawns this module and talks over the pipe.
Nothing may be written to stdout — that is the protocol channel.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import loogle as _loogle

#: Hard ceiling on a single tool's output. An agent pays for every byte in
#: its next turn, and a runaway result is the framework's fault, not the
#: agent's.
MAX_CHARS = 8000

mcp = FastMCP("asterism_tools")


@mcp.tool()
def loogle(pattern: str = "", query: str = "",
           limit: int = _loogle.DEFAULT_LIMIT) -> str:
    """Search Mathlib (loogle.lean-lang.org).

    Pass the search as `pattern` (or `query` — both work):
      - by type, `_` a wildcard and `?x` a named hole:
        `Nat.factorial _ = _`, `?p.Prime → ∏ _ ∈ _, _ = -1`
      - by constant(s) mentioned: `List.sum, List.map`
      - by exact name, to recover a signature: `sq_pos_of_ne_zero`
      - by name substring, quoted: `"sq_pos_of"`

    Returns one line per hit: `name :: type [module]`. No hits is a
    valid answer — refine the pattern rather than retrying it verbatim.
    """
    # `query` is an alias because that is what a model reaches for first:
    # the acceptance run called `loogle(query=…)`, MCP raised, and agy
    # stamped the whole envelope ERROR over a recoverable slip. A schema
    # that accepts the natural guess costs one parameter.
    pattern = (pattern or query).strip()
    if not pattern:
        return "loogle: give a type pattern, e.g. `Nat.factorial _ = _`"
    rc, text = _loogle.query(pattern, limit=limit)
    if rc != 0:
        return f"loogle unavailable: {text}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n… (truncated; narrow the pattern)"
    return text


@mcp.tool()
def validate_json(text: str) -> str:
    """Check that `text` parses as JSON before you emit it.

    Returns `OK: <n> top-level key(s)` or the parser's own message with
    the line and column. Read-only — it tells you nothing about whether
    the framework will ACCEPT the decision, only that it can be read.
    """
    import json as _json
    try:
        obj = _json.loads(text)
    except ValueError as e:
        return f"INVALID: {e}"
    if isinstance(obj, dict):
        return f"OK: {len(obj)} top-level key(s)"
    if isinstance(obj, list):
        return f"OK: array of {len(obj)}"
    return f"OK: {type(obj).__name__}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
