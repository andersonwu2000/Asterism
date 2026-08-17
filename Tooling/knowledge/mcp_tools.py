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

import os

from mcp.server.fastmcp import FastMCP

from . import loogle as _loogle

#: Hard ceiling on a single tool's output. An agent pays for every byte in
#: its next turn, and a runaway result is the framework's fault, not the
#: agent's.
MAX_CHARS = 8000

#: NO TOOL HERE HAS A REQUIRED PARAMETER, and that is a rule about the
#: transport, not about politeness.
#:
#: A model guesses parameter names. When it guesses wrong, FastMCP's
#: pydantic model raises `Field required`, and on the Antigravity CLI a
#: raising MCP tool stamps the WHOLE envelope `status: ERROR` — the run
#: exits 1, and the postmortem turn that `--resume`s the same session to
#: collect feedback dies with it. One wrong parameter name therefore
#: costs a spawn's entire feedback record.
#:
#: Measured 2026-08-10, first live minute of the Gemini formalizer seat:
#: the model called `inspect(inspect_requests=[…])`. Six spawns filed no
#: feedback that window. The same failure is recorded four lines below
#: for `loogle(query=…)` — the lesson was written down and then not
#: applied to the next tool.
#:
#: The fix is deliberately NOT a list of accepted aliases: enumerating
#: the names a model might invent is the "列舉會爛" trap, and the next
#: model invents a new one. Instead every parameter is optional, so
#: nothing raises, and a call that binds nothing returns a TEACHING
#: STRING naming the real parameter. Extra unknown fields are already
#: dropped silently by pydantic, so a mis-named argument lands as an
#: empty call — which is exactly the case the teaching string covers.
#: Cost: one recoverable round-trip instead of a dead spawn.
_ARG_HELP = "{tool}: {hint}"

mcp = FastMCP("asterism_tools")


@mcp.tool(structured_output=False)
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
        return _ARG_HELP.format(
            tool="loogle",
            hint='the parameter is `pattern` (or `query`), e.g. '
                 'loogle(pattern="Nat.factorial _ = _")')
    rc, text = _loogle.query(pattern, limit=limit)
    if rc != 0:
        return f"loogle unavailable: {text}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n… (truncated; narrow the pattern)"
    return text


@mcp.tool(structured_output=False)
def validate_json(text: str = "") -> str:
    """Check that `text` parses as JSON before you emit it.

    Returns `OK: <n> top-level key(s)` or the parser's own message with
    the line and column. Read-only — it tells you nothing about whether
    the framework will ACCEPT the decision, only that it can be read.
    """
    import json as _json
    if not (text or "").strip():
        return _ARG_HELP.format(
            tool="validate_json",
            hint='the parameter is `text`, a string — e.g. '
                 'validate_json(text=\'{"a": 1}\')')
    try:
        obj = _json.loads(text)
    except ValueError as e:
        return f"INVALID: {e}"
    if isinstance(obj, dict):
        return f"OK: {len(obj)} top-level key(s)"
    if isinstance(obj, list):
        return f"OK: array of {len(obj)}"
    return f"OK: {type(obj).__name__}"


@mcp.tool(structured_output=False)
def inspect(queries: list = None) -> str:
    """Ask several questions about the files here, in one call.

    Each query is an object; results come back labelled.

        [{"decl":  "uc_four_set_deficit"},
         {"read":  "Context.md", "sections": ["Programme"]},
         {"read":  "Manifest.md", "outline": true},
         {"grep":  "BoundedOrder", "in": "proofs/*.lean", "context": 3},
         {"read":  "patch.lean", "lines": "380-420"},
         {"find":  "*deficit*.lean"},
         {"size":  "proofs/*.lean"}]

    Batch freely: each query gets its own full budget, and a second
    question never shrinks the answer to the first. Queries that would
    overflow one reply are deferred by name — resend just those.

    READ BY THE SECTION. `sections` takes heading text (`## Programme`
    → "Programme") and returns that heading with everything under it.
    The framework's documents — Context.md, Manifest.md, PROGRAMME.md,
    CATALOG.md, decisions.md — are written with stable headings, so this
    is the cheap way to read them; naming a section you already know
    beats paging. `outline: true` returns the map (headings, line
    ranges, sizes) when you do not know which section you want. `lines`
    is for files with no headings, such as `.lean`. With none of the
    three, `read` returns the whole file.

    `decl` answers from the framework's own record — the statement, the
    file and whether it is proved — so use it instead of grepping for a
    keyword at the start of a line. `in` and `read` take paths relative
    to your own directory, or globs. A truncated answer always says
    where to resume, with no overlap.
    """
    from . import workspace_query
    if not queries:
        return _ARG_HELP.format(
            tool="inspect",
            hint='the parameter is `queries`, a list — e.g. '
                 'inspect(queries=[{"decl": "foo"}, '
                 '{"grep": "Bar", "in": "proofs/*.lean"}])')
    # No `max_chars`: `inspect` budgets PER QUERY (workspace_query
    # owns the number), unlike the single-answer tools above which this
    # module's `MAX_CHARS` still governs. The env var is the backend's
    # DELIVERY ceiling — set into this server's env by the provider
    # adapter from `llm/capabilities.mcp_result_delivery_chars`; unset
    # (an unmeasured backend) means no ceiling, never a guessed one.
    raw = os.environ.get("ASTERISM_INSPECT_DELIVERY_CHARS", "").strip()
    delivery = int(raw) if raw.isdigit() and int(raw) > 0 else None
    return workspace_query.run_queries(queries, delivery_chars=delivery)


@mcp.tool(structured_output=False)
def write_file(path: str = "", content: str = "") -> str:
    """Write a file into your attempts directory. Full-file overwrite.

    This is how your outputs land — decision.json, proposal.md,
    _plan.md, verdict.json, any `proof_file` / `brief_file` target.
    The write happens in the framework's own process and completes
    immediately; prefer it over `apply_patch` for every file you
    produce. Pass the absolute path your prompt gave you, or a bare
    filename — both land in YOUR attempts directory, which is the only
    writable place. The whole file is replaced; there is no partial
    edit, so send the complete text.
    """
    from . import workspace_query
    if not (path or "").strip():
        return _ARG_HELP.format(
            tool="write_file",
            hint='the parameters are `path` and `content`, e.g. '
                 'write_file(path="decision.json", content="[…]")')
    if not content:
        # A mis-named argument arrives as an empty call (pydantic drops
        # unknown fields), and an empty decision.json is never wanted.
        return _ARG_HELP.format(
            tool="write_file",
            hint='`content` is empty — the whole file body goes in '
                 '`content` (a mis-spelled parameter name lands here)')
    return workspace_query.run_write(path, content)


@mcp.tool(structured_output=False)
def compute(code: str = "") -> str:
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
    if not (code or "").strip():
        return _ARG_HELP.format(
            tool="compute",
            hint='the parameter is `code`, a string — e.g. '
                 'compute(code="print(sum(1/k**2 for k in range(1, 10**6)))")')
    return _compute_via_gateway(code)


#: The sandbox runs in the GATEWAY, not here.
#:
#: Measured 2026-08-11: no subprocess started from this stdio server
#: ever runs. Twelve consecutive `compute` calls returned "sandbox
#: interpreter will not start … timed out after 60 seconds", and the
#: control spawn — the very interpreter hosting this server, same
#: creation flags, same cwd — hung identically, while the same command
#: from a shell takes 95ms. So the venv was never the problem and this
#: tool had not worked once since it shipped on 08-10: agents lost
#: their only calculator the same day the shell closed, and the polite
#: "unavailable" message read as "temporarily down" rather than "never
#: worked here". An Adversary hand-checked ~15 sums and abandoned a
#: brute-force enumeration; a Strategist did a 256-family sweep in its
#: own output and hit the 64k token ceiling.
#:
#: The gateway spawns `lake serve` and a pool of lean workers all day,
#: and `pin_check._gateway_probe` already calls it over plain HTTP from
#: THIS server on every loogle hit — so both halves of this path were
#: already proven in production before it carried compute.
_GATEWAY_TIMEOUT_SEC = 180


def _gateway_silence_hint() -> str:
    """Which silence this is — and they call for opposite actions.

    A gateway that is still coming up will answer on its own, so the
    move is to wait. One that is not running will not, so the move is
    to say so and carry on without a calculator. Told as one message,
    an agent picks wrong half the time.

    The marker is a file and survives an abnormal death, so its mere
    presence proves nothing; `lifecycle.warming_pid` is the one place
    that pairs it with liveness."""
    try:
        from ..lsp import lifecycle
        pid = lifecycle.warming_pid(_workspace_root())
    except Exception:  # noqa: BLE001 — a hint must never be the failure
        pid = None
    if pid is not None:
        return (f"The framework's gateway (pid {pid}) is starting up right "
                f"now, so this is a matter of seconds: carry on with "
                f"something else and use compute again later this turn.")
    return ("This is a framework fault, not a problem with your code: "
            "retry once, and if it repeats say so in your framework "
            "feedback rather than working around it.")


def _compute_via_gateway(code: str) -> str:
    import json
    import os
    import urllib.error
    import urllib.request

    from ..sandbox import ComputeResult
    port = os.environ.get("ASTERISM_GATEWAY_PORT", "8765")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/compute",
        data=json.dumps({"code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_GATEWAY_TIMEOUT_SEC) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        # The service ANSWERED and named its own failure in the body;
        # `str(HTTPError)` is "HTTP Error 500: Internal Server Error" for
        # every cause alike. Telling the agent "did not answer" when it
        # did — and hiding what it said — sends it to the wait-vs-report
        # fork with no way to choose.
        from ..lsp.lifecycle import read_http_error
        refused = read_http_error(exc, endpoint="/compute")
        return ComputeResult(
            rc=127, seconds=0.0,
            output=f"[compute] the framework's compute service refused "
                   f"this call: {refused.detail[:300]}",
        ).render()
    except Exception as exc:  # noqa: BLE001
        # Say which side failed, and WHICH of the two silences this is.
        # The old message named the venv and guessed "base Python
        # upgraded under it?"; that hard-coded guess sent every reader —
        # the operator included — after the wrong thing for two days.
        # "Wait" and "report it" are opposite instructions, so the two
        # states must not share one sentence.
        return ComputeResult(
            rc=127, seconds=0.0,
            output=f"[compute] the framework's compute service did not "
                   f"answer ({type(exc).__name__}: {str(exc)[:160]}). "
                   f"{_gateway_silence_hint()}",
        ).render()
    # `killed` is what turns a bare empty result into an instruction.
    # Dropping it here (2026-08-12) cost a Strategist two calls: a
    # timed-out sweep came back as the standing header and nothing at
    # all, so it probed with `print("hello", 1+1)` to see whether the
    # tool existed.
    return ComputeResult(rc=int(data.get("rc", 1)),
                         output=str(data.get("output") or ""),
                         seconds=float(data.get("seconds") or 0.0),
                         killed=str(data.get("killed") or "")).render()


@mcp.tool(structured_output=False)
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
        return _ARG_HELP.format(
            tool="paper_search",
            hint='the parameters are `query` (citation or keywords) or '
                 '`doi`, e.g. paper_search(query="Frankl union-closed")')
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


@mcp.tool(structured_output=False)
def paper_fetch(target: str = "", problem: str = "", reason: str = "") -> str:
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
        return _ARG_HELP.format(
            tool="paper_fetch",
            hint='the parameter is `target` — an arXiv id or a whitelisted '
                 'URL, e.g. paper_fetch(target="2211.11504", '
                 'reason="cited for the closure bound")')
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
