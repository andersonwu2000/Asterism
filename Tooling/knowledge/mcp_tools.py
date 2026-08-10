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


@mcp.tool()
def inspect(queries: list) -> str:
    """Ask several questions about the files here, in one call.

    Each query is an object; results come back labelled and capped.

        [{"decl":  "uc_four_set_deficit"},
         {"grep":  "BoundedOrder", "in": "proofs/*.lean", "context": 3},
         {"read":  "CATALOG.md", "lines": "380-420"},
         {"find":  "*deficit*.lean"},
         {"size":  "proofs/*.lean"}]

    `decl` answers from the framework's own record — the statement, the
    file and whether it is proved — so use it instead of grepping for a
    keyword at the start of a line. `in` and `read` take paths relative
    to your own directory, or globs. `max` raises a query's own line cap;
    a truncated answer always says how many lines were dropped and how
    to see them.
    """
    from . import workspace_query
    return workspace_query.run_queries(queries, max_chars=MAX_CHARS)


@mcp.tool()
def compute(code: str) -> str:
    """Run a short Python calculation and get back what it prints.

    NOT A PROOF. Nothing computed here establishes a mathematical claim,
    in either direction — a clean sweep over a million points settles
    nothing, and neither does an identity that checks out numerically.
    Only the Lean kernel decides what is proved. Use this to hunt
    counterexamples and to check your own arithmetic before you commit
    to it in prose.

    numpy is available. There is no filesystem, no network and no shell:
    put the data you need inline in the code and return results with
    `print()`. Each call is a fresh process, so define everything you
    use. Time and memory are capped by the framework.
    """
    from ..sandbox import run as _run
    if not (code or "").strip():
        return ("compute: give it some code, e.g. "
                "`print(sum(1/k**2 for k in range(1, 10**6)))`")
    return _run(code).render()


@mcp.tool()
def paper_search(query: str = "", doi: str = "") -> str:
    """Find a paper by citation text, keywords, or DOI.

    `query` searches OpenAlex, arXiv and Crossref; `doi` lists the
    open-access copies of one DOI. Returns JSON hits. Refine the query
    until you are sure which hit IS the work you are looking for —
    fetching the wrong paper costs a whole wake.
    """
    import io
    import json as _json
    from contextlib import redirect_stdout

    from ..papers import search as _search
    argv = ["--doi", doi] if doi else (query or "").split()
    if not argv:
        return "paper_search: give a citation, some keywords, or a doi."
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _search.main(argv)
    out = buf.getvalue().strip()
    if rc != 0:
        return f"paper_search failed: {out[:500]}"
    if len(out) > MAX_CHARS:
        try:
            hits = _json.loads(out)
            out = _json.dumps(hits[:8], ensure_ascii=False, indent=1)
        except ValueError:
            out = out[:MAX_CHARS]
        out += "\n… narrowed to the first hits; refine the query."
    return out


@mcp.tool()
def paper_fetch(target: str, problem: str = "", reason: str = "") -> str:
    """Download a paper, shelve it, and bind it to the problem.

    `target` is an arXiv id or a URL on a whitelisted host. This is the
    success action of a Scholar wake: say in `reason` why the work is
    needed — the binding is audited.
    """
    import io
    from contextlib import redirect_stdout
    from pathlib import Path as _Path

    from ..papers import fetch as _fetch
    if not (target or "").strip():
        return "paper_fetch: give an arXiv id or a whitelisted URL."
    argv = [target, "--workspace", str(_workspace_root())]
    if problem:
        argv += ["--problem", problem]
    if reason:
        argv += ["--reason", reason]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _fetch.main(argv)
    out = buf.getvalue().strip() or f"(no output, rc={rc})"
    _ = _Path  # keep the import honest for readers of the argv above
    return out


def _workspace_root():
    """The workspace, resolved the same way `inspect` resolves it — the
    Scholar's cwd is its own problem directory, and `fetch` needs the
    root to shelve into. One resolver, not two."""
    from pathlib import Path as _Path

    from . import workspace_query
    return workspace_query.workspace_of(_Path.cwd()) or _Path.cwd()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
