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

from ..sandbox import TIMEOUT_SEC as _SANDBOX_TIMEOUT_SEC
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

#: (spawn attempts-dir, normalized pattern) → times asked. Bounded by
#: periodic clear; process-global because the tools run in the shim.
_LOOGLE_REPEATS: "dict[tuple[str, str], int]" = {}

#: The way out of a name miss: Mathlib SOURCE is greppable in place
#: (explicit `.lake/packages/...` paths override the skip list — owner
#: ruling 2026-08-22).
_GREP_THE_SOURCE = (
    'Grep the source for the current name: inspect([{"grep": '
    '"<name fragment>", "in": ".lake/packages/mathlib/Mathlib"}]) '
    '— or a subdir of it for speed.')

mcp = FastMCP("asterism_tools")

# FastMCP registers resource/prompt handlers unconditionally, so the
# initialize response ADVERTISES capabilities this server has zero of
# — and every codex intake burned its first calls discovering that
# (`list_mcp_resources` -> empty, x23 feedback 2026-08-25). Dropping
# the handlers un-advertises the capability at the source; the client
# then never surfaces those tools at all.
from mcp import types as _mcp_types  # noqa: E402


def _drop_empty_capabilities(server) -> None:
    for _req in (_mcp_types.ListResourcesRequest,
                 _mcp_types.ReadResourceRequest,
                 _mcp_types.ListResourceTemplatesRequest,
                 _mcp_types.ListPromptsRequest,
                 _mcp_types.GetPromptRequest):
        server._mcp_server.request_handlers.pop(_req, None)


_drop_empty_capabilities(mcp)

# ── Seat gate (owner ruling 2026-08-22) ───────────────────────────────
# The server registers only the seat's declared surface. ASTERISM_SEAT
# is written into this server's env by the pipeline config writers; the
# whitelist itself lives in llm/envelope.SEAT_ASTERISM_TOOLS so every
# provider reads the same table. No env var = full surface (operator
# use, tests, the shim's in-process import — the shim enforces
# per-request declared tools itself).
_SEAT = os.environ.get("ASTERISM_SEAT", "")
if _SEAT:
    from ..llm.envelope import asterism_tools_for as _seat_tools
    _ALLOWED = _seat_tools(_SEAT)
else:
    _ALLOWED = None


def ping() -> str:
    """Tool-plane liveness for the shim's `{"probe": "tools"}` — a real
    call through the execution path, not the HTTP door (which answered
    through the whole 2026-08-23 stall). Deliberately NOT a seat tool:
    agents never see it."""
    return "pong"


def _seat_tool(**tool_kwargs):
    """`@mcp.tool` that registers only when the seat's whitelist says
    so; the function itself always exists (the shim imports this module
    and dispatches by getattr — its own gate is the request's declared
    tool list)."""
    def deco(fn):
        if _ALLOWED is None or fn.__name__ in _ALLOWED:
            return mcp.tool(**tool_kwargs)(fn)
        return fn
    return deco


@_seat_tool(structured_output=False)
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
    # Exact-repeat teaching: agents resent ONE identical query up to
    # ×114 in a session (both fleets, 2026-08-22 — the top killer of
    # timed-out formalizer turns). The answer cannot change; say so,
    # with the way out. Keyed per spawn so parallel agents don't
    # cross-pollute.
    from ..llm.spawn_guard import current_attempt_dir
    spawn = current_attempt_dir() or ""
    rkey = (spawn, " ".join(pattern.split()))
    if len(_LOOGLE_REPEATS) > 512:
        _LOOGLE_REPEATS.clear()
    n = _LOOGLE_REPEATS[rkey] = _LOOGLE_REPEATS.get(rkey, 0) + 1
    if n >= 4:
        return (f"you have sent this EXACT query {n} times — the "
                f"answer has not changed and will not. Repeated misses "
                f"on one shape usually mean Mathlib lacks it in this "
                f"form OR renamed it: " + _GREP_THE_SOURCE + " Or plan "
                f"without it / prove the special case you need inline.")
    rc, text = _loogle.query(pattern, limit=limit)
    if rc != 0:
        return f"loogle unavailable: {text}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n… (truncated; narrow the pattern)"
    if "no hits" in text:
        # A miss on a REMEMBERED name is usually a Mathlib rename
        # (models' Mathlib memory trails the deprecation cycle; 4 of 6
        # safari'd names measured absent, 2026-08-22) — the source has
        # the current name one grep away.
        text = text.rstrip() + " " + _GREP_THE_SOURCE
    if n >= 2:
        text = (f"[you have sent this exact query {n} times — same "
                f"answer] " + text)
    return text


def _audit_snapshot_here() -> "list[dict] | None":
    """The routine audit's roots snapshot for THIS spawn, or None when
    this spawn is not the auditor. `None` and `[]` mean different
    things and the caller reads both."""
    from ..pipeline.strategist import audit as _audit
    from . import workspace_query as _wq
    own = _wq._own_attempt_dir()
    return _audit.read_roots_snapshot(own) if own else None


#: The rubric a verdict is judged against, DECLARED by the wake that
#: seated the judge — `{"criteria_keys": [...], "multi_clear": bool}`.
#:
#: Ownership again, one layer past `_audit_roots.json`. Shape cannot
#: answer WHICH rubric a verdict was written against: since 2026-09-07
#: the batch judge and the theory review both adjudicate criteria
#: "1".."4", and before that a complete four-criterion review verdict
#: was told "`criteria` missing criterion 5" — a framework fault worded
#: as the judge's mistake, about a criterion its prompt does not have.
#: The judge cannot act on that: it can only invent one. The rules
#: still differ (multi-clear, bullet shape), so the declaration, not
#: the key count, is what decides.
_RUBRIC_FILE = "_verdict_rubric.json"


def _declared_rubric_here() -> "tuple[list[str], bool] | None":
    """`(criteria_keys, multi_clear)` for THIS spawn, or None.

    A missing OR malformed declaration reads as ABSENT, never as an
    error: the judge did not write this file and cannot repair it, so
    the worst a broken one may cost is the old generic check — a
    refusal with no action behind it is the failure mode this whole
    channel exists to remove."""
    import json as _json
    from . import workspace_query as _wq
    own = _wq._own_attempt_dir()
    if own is None:
        return None
    try:
        obj = _json.loads((own / _RUBRIC_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    keys = obj.get("criteria_keys") if isinstance(obj, dict) else None
    if not (isinstance(keys, list) and keys
            and all(isinstance(k, str) and k for k in keys)):
        return None
    return keys, bool(obj.get("multi_clear"))


def _render_keys(keys: "list[str]") -> str:
    """`1–4` for a contiguous numeric rubric, else the list."""
    if (len(keys) > 2 and all(k.isdigit() for k in keys)
            and [int(k) for k in keys]
            == list(range(int(keys[0]), int(keys[0]) + len(keys)))):
        return f"{keys[0]}–{keys[-1]}"
    return ", ".join(keys)


def _declared_verdict_notes(obj: dict, keys: "list[str]",
                            multi_clear: bool) -> "list[str]":
    """What the declared rubric's parser would refuse.

    STRING bullets, because that is what the declaration says. The
    review parser also tolerates an object-rendered bullet and a bare
    string, but a probe looser than the declaration teaches a shape the
    declaration does not promise to keep — so this holds the declared
    shape and the message names the one to write."""
    import re as _re
    crit = obj.get("criteria")
    if not isinstance(crit, dict):
        return [f"`criteria` is not an object — one list of bullets per "
                f"criterion, keyed {_render_keys(keys)}"]
    notes: "list[str]" = []
    missing = [k for k in keys if k not in crit]
    if missing:
        notes.append(f"`criteria` missing criterion "
                     f"{', '.join(missing)} — this rubric has "
                     f"{len(keys)} criteria ({', '.join(keys)}), and "
                     f"every one gets a line")
    for k in keys:
        if k not in crit:
            continue
        vals = crit[k]
        if not (isinstance(vals, list) and vals
                and all(isinstance(x, str) for x in vals)):
            notes.append(f"criterion {k} must be a list of plain "
                         f"strings, one bullet per item, each beginning "
                         f"`clear:` or `fired:` — this rubric declares "
                         f'STRING bullets, so an object bullet '
                         f'({{"ruling": …}}) or a bare string is not it')
            continue
        heads = [("clear" if _re.match(r"clear\b", x.strip(), _re.I)
                  else "fired" if _re.match(r"fired\b", x.strip(), _re.I)
                  else "?") for x in vals]
        if "?" in heads:
            notes.append(f"criterion {k}: every bullet must begin "
                         f'"clear" or "fired: <objection>"')
            continue
        if "clear" in heads and "fired" in heads:
            notes.append(f'criterion {k} mixes "clear" and "fired" '
                         f"bullets — a criterion is one ruling")
            continue
        if heads[0] == "clear":
            # A criterion is clear iff EVERY bullet is: a document with
            # several theorems or several leads is answered one bullet
            # each. Where the declaration does not say `multi_clear`,
            # the batch judge's rule stands (one proposal, one clear).
            if not multi_clear and len(vals) > 1:
                notes.append(f'criterion {k}: "clear" takes exactly one '
                             f"entry under this rubric")
                continue
            if any(not x.strip()[len("clear"):].strip(" -—–:")
                   for x in vals):
                notes.append(f'criterion {k} never takes a bare "clear" '
                             f"— say why it holds HERE: "
                             f'`"clear: <one concrete reason>"`')
            continue
        if any(not (x.strip().split(":", 1)[1].strip() if ":" in x
                    else x.strip()[len("fired"):].strip(" -—–:"))
               for x in vals):
            notes.append(f"criterion {k} is fired but carries no "
                         f'objection — `"fired: <objection>"`')
    if "reservations" in obj and not isinstance(
            obj.get("reservations"), list):
        notes.append("`reservations` must be a list of strings")
    return notes


@_seat_tool(structured_output=False)
def validate_json(text: str = "", file: str = "") -> str:
    """Check your JSON hand-in (decision.json / verdict.json).

    Prefer `file`: name the file you wrote (bare name or the absolute
    path your prompt gave you) and the bytes ON DISK are validated —
    the same disk-is-authority rule as `validate_file`: what you
    validate IS what the framework will read. `text` validates a
    pasted string instead; long payloads mangled by tool-call escaping
    made it report offsets that do not exist in the real file
    (adversary feedback, 2026-08-25).

    Returns `OK: <n> top-level key(s)` or the parser's own message with
    the line and column. A verdict is also checked against the rubric
    YOUR wake declared, so the criteria it names are the ones your
    prompt gave you. Read-only — it tells you nothing about whether the
    framework will ACCEPT the decision, only that it can be read.
    """
    import json as _json
    if (file or "").strip():
        from . import workspace_query
        content, err = workspace_query.read_own_file(file)
        if content is None:
            return f"validate_json: {err}"
        src = content
    elif (text or "").strip():
        src = text
    else:
        return _ARG_HELP.format(
            tool="validate_json",
            hint='pass `file` (preferred — validates the DISK file, '
                 'e.g. validate_json(file="verdict.json")) or `text` '
                 '(a pasted string)')
    try:
        # strict=False mirrors every framework parser of agent JSON
        # (decision / verdict / librarian): raw control characters
        # inside strings are accepted, so this probe cannot call
        # INVALID what the hand-in parser would take (p324 class).
        obj = _json.loads(src, strict=False)
    except ValueError as e:
        return f"INVALID: {e}"
    if isinstance(obj, dict):
        # Verdict-shaped payloads get their SHAPE checked here too —
        # "syntactically valid with a misspelled criterion key sailed
        # through as OK" and died a whole round later at the parser
        # (4 judge self-reports, 2026-08-22). Same facts the server
        # parser enforces, surfaced before the hand-in.
        # WHICH verdict this is is decided by OWNERSHIP, never by shape.
        # The routine AUDIT verdict (criteria 1-4, 3 and 4 per line in
        # flight) is the one written in a spawn the routine wake seated
        # as the auditor — and that wake, alone in the framework, drops
        # `_audit_roots.json` into the attempts dir as the snapshot its
        # verdict is checked against. Its presence IS the signal.
        #
        # The shape guess it replaces ("criterion 3 is a list and
        # there is no criterion 5") also matched a theory-wake verdict,
        # whose rubric is criteria "1".."3" or "1".."4" with string
        # bullets — and since 2026-09-07 the batch judge's own rubric is
        # "1".."4" too, so no key count could tell them apart:
        # the tool told the arm3h_r2 judge twice to convert criterion 3
        # into `{goal_id, verdict, reason}` objects and add a criterion
        # 4 its rubric does not have, and both tries died on it (the
        # arm3h_r2 failure record of the 2026-09-04 theory-wake
        # experiment, kept in the operator's archive history — the run
        # artefacts left the tree 2026-09-06). An empty snapshot still
        # dispatches to the
        # audit parser: a group with no line in flight is an audit with
        # nothing to rule on per line, not a different document.
        snap = _audit_snapshot_here() if "criteria" in obj else None
        if snap is not None and isinstance(obj.get("criteria"), dict):
            from ..pipeline.strategist import audit as _audit
            # Shape errors are what the hand-in parser would refuse;
            # coverage notes are advisory — a line left unruled is
            # recorded as unaudited, never invented as fired.
            _v, err = _audit.parse_verdict(src, snap)
            if err:
                return f"OK as JSON, but the audit parser will reject it: {err}"
            notes = _audit.coverage_report(obj, snap)
            if notes:
                return ("OK as JSON, audit-shaped; coverage: "
                        + "; ".join(notes))
            return (f"OK: audit-shaped, criteria 1-4 present, every line "
                    f"in flight ruled on ({len(snap)} line(s))")
        # Next ownership signal, same rule: a wake that seats a judge on
        # a rubric OTHER than the batch judge's declares it, and
        # the declaration — not the shape, and not this tool's default
        # — is the key set the verdict is checked against.
        rubric = _declared_rubric_here() if "criteria" in obj else None
        if rubric is not None:
            keys, multi_clear = rubric
            notes = _declared_verdict_notes(obj, keys, multi_clear)
            if notes:
                # Who is refusing, not "the parser": most of these are
                # parser refusals, but the string-bullet rule is the
                # DECLARATION being stricter than the parser's
                # tolerance, and a message that misnames its own
                # authority is one an agent cannot argue with correctly.
                return ("OK as JSON, review-shaped, but the declared "
                        "rubric rejects it: " + "; ".join(notes))
            return (f"OK as JSON, review-shaped "
                    f"(keys {_render_keys(keys)})")
        if "criteria" in obj:
            # The judge's own parser, not a second implementation of its
            # rules: key-presence answered "OK: verdict-shaped, every
            # criterion present" for verdicts `parse_verdict` refused on
            # their BULLET shape, and six union_closed Strategist wakes
            # died on that green light (2026-09-05) — the judge
            # validated, finished, and the wake discarded the proposal.
            # A preview that can disagree with the parser is worse than
            # none, so it IS the parser.
            from ..pipeline.adversary import parse_verdict as _parse
            verdict, perr = _parse(src)
            if verdict is None:
                return ("OK as JSON, but the judge parser will reject "
                        "it: " + perr)
            return (f"OK: {len(obj)} top-level key(s); verdict-shaped, "
                    f"the judge parser accepts it and derives "
                    f"\"{verdict['verdict']}\"")
        return f"OK: {len(obj)} top-level key(s)"
    if isinstance(obj, list):
        return f"OK: array of {len(obj)}"


@_seat_tool(structured_output=False)
def inspect(queries: list = None) -> str:
    """Ask several questions about the files here, in one call.

    Each query is an object; results come back labelled.

        [{"decl":  "uc_four_set_deficit"},
         {"read":  "Context.md", "sections": ["Programme"]},
         {"read":  "charter.md", "outline": true},
         {"grep":  "BoundedOrder", "in": "proofs/*.lean", "context": 3},
         {"read":  "patch.lean", "lines": "380-420"},
         {"find":  "*deficit*.lean"},
         {"size":  "proofs/*.lean"}]

    Batch freely: each query gets its own full budget, and a second
    question never shrinks the answer to the first. Queries that would
    overflow one reply are deferred by name — resend just those.

    READ BY THE SECTION. `sections` takes heading text (`## Programme`
    → "Programme") and returns that heading with everything under it.
    The framework's documents — Context.md, charter.md, PROGRAMME.md,
    CATALOG.md, decisions.md — are written with stable headings, so this
    is the cheap way to read them; naming a section you already know
    beats paging. `outline: true` returns the map (headings, line
    ranges, sizes) when you do not know which section you want; on a
    roster-sized file (CATALOG.md) add `outline_prefix: "uc_four"` or
    `outline_grep: "<regex>"` — its whole map is refused. `lines`
    is for files with no headings, such as `.lean`. With none of the
    three, `read` returns the whole file. Add `"raw": true` to get the
    content UNDECORATED (no line numbers, no banners) — use it whenever
    the text will be written back or validated (`write_file`,
    `validate_json`, `validate_file`), so nothing needs hand-stripping.
    A `raw` read must be the ONLY query in its call: its answer is
    byte-faithful content with no labels, so it cannot share a reply.

    `decl` answers from the framework's own record — the statement, the
    file, whether it is proved, and why a goal is still unsettled when
    its strategy succeeded. `in` and `read` take a path relative to your
    own directory, a glob, or an ABSOLUTE path, used as given. A
    truncated answer always says where to resume, with no overlap.
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


@_seat_tool(structured_output=False)
def write_file(path: str = "", content: str = "") -> str:
    """Write a file into your attempts directory. Full-file overwrite.

    This is how your outputs land — decision.json, proposal.md,
    _plan.md, verdict.json.
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


@_seat_tool(structured_output=False)
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
    use. Time and memory are capped by the framework: 15 minutes of
    wall clock and 512 MB, which is room for an exhaustive sweep of a
    few million cases — size the search to fit rather than sampling it.
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
#:
#: DERIVED, never typed twice: the client must outlive everything the
#: framework is entitled to spend before answering. A client that hangs
#: up first turns "stopped at the 900s limit, shrink the search" — an
#: instruction — into "the compute service did not answer", which is
#: the wait-vs-report fork with no way to choose.
#:
#: That budget is a QUEUE WAIT PLUS A FULL RUN, hence 2× (owner ruling
#: 2026-09-03). The gateway admits `_COMPUTE_SLOTS = 2` sandboxes, so a
#: third caller may legitimately wait one whole wall for a slot and
#: then run a whole wall of its own; sized for one run, this socket
#: would time out on precisely the caller the gate creates. The other
#: two ways to close that gap were both refused: a soft gate that lets
#: a third sandbox through loses the invariant it exists to hold, and
#: refusing the queued caller hands the agent a fault it cannot act on.
#:
#: The 15-minute wall (owner ruling 2026-09-04) makes this 1860, which
#: is PAST the 1500s ceiling every provider's MCP client used to put on
#: one tool call — so that ceiling moved with it and is now
#: `llm/base.MCP_TOOL_TIMEOUT_SEC`. The relation is pinned by
#: `tests/test_compute_sandbox.py`, because neither this module nor the
#: gateway can be imported from a dispatcher cheaply enough to compute
#: it there.
#:
#: The import is one stdlib-only module (`sandbox.provision` reaches no
#: further), so it does not breach this server's rule against pulling
#: the framework's heavy modules into the stdio process.
_GATEWAY_TIMEOUT_SEC = 2 * _SANDBOX_TIMEOUT_SEC + 60


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
    output = str(data.get("output") or "")
    # The gateway runs two sandboxes at a time, so a call can be slow
    # for a reason that has nothing to do with the code in it. Unsaid,
    # the agent reads the wall clock as its own search being too big
    # and shrinks a sweep that was the right size.
    try:
        waited = float(data.get("waited_sec") or 0.0)
    except (TypeError, ValueError):
        waited = 0.0
    if waited >= 1.0:
        output += (f"\n[compute] this call queued {waited:.0f}s for a free "
                   f"sandbox — the framework runs two at a time. Your code "
                   f"was not the slow part.")
    return ComputeResult(rc=int(data.get("rc", 1)),
                         output=output,
                         seconds=float(data.get("seconds") or 0.0),
                         killed=str(data.get("killed") or "")).render()


@_seat_tool(structured_output=False)
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


@_seat_tool(structured_output=False)
def paper_fetch(target: str = "", problem: str = "", reason: str = "") -> str:
    """Download a paper, shelve it on the problem's Project, and bind it.

    `target` is an arXiv id or a URL on a whitelisted host — use
    `paper_search` first to resolve a citation to fetchable open
    copies. `problem` is REQUIRED: it names the Project whose documents
    hold the paper. Say in `reason` why the work is needed — the
    binding is audited.
    """
    import io
    from contextlib import redirect_stdout
    from pathlib import Path as _Path

    from ..papers import fetch as _fetch
    if not (target or "").strip():
        return _ARG_HELP.format(
            tool="paper_fetch",
            hint='the parameter is `target` — an arXiv id or a whitelisted '
                 'URL, with the problem it is for, e.g. '
                 'paper_fetch(target="2211.11504", problem="Erdos.p1", '
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


# ── The console Assistant's surface (HID §1.1, §3.5, §3.8) ───────────
#
# Registered only for the `explainer` seat (`envelope._ASSISTANT_TOOLS`),
# which is why they can be written here beside the workers' tools without
# widening anyone's surface: the server reads ASTERISM_SEAT and registers
# the seat's table.
#
# The write is ONE call into `state/project_docs.write(area='user')`.
# Everything the Assistant may ever write goes through that function, and
# the area is its argument — so "the Assistant cannot write outside
# `_docs/user/`" is a property of the call, not of the prompt.
#
# `user/` — the area the Documents rail calls "yours" — and not `agent/`
# (owner, 2026-09-06). The Assistant writes FOR the person: a summary,
# a note, a draft they will revise. `agent/` is read-only in the console,
# so a document landed there was one the reader could not touch. The
# theory layer keeps `agent/`; that shelf is the engine's own record.


def _project_docs_error(e: Exception, *, tool: str, project: str) -> str:
    """A refusal a model can act on. `KeyError` = the thing is not there,
    `ValueError` = it is refused and the message already names the way
    out (`state/project_docs` owes that); this only adds the tool-level
    next step."""
    if isinstance(e, KeyError):
        return (f"{tool}: {e.args[0]!r} is not in {project}'s documents "
                f"— call list_project_docs(project=\"{project}\") to see "
                f"what is.")
    return f"{tool}: {e}"


@_seat_tool(structured_output=False)
def write_project_doc(project: str = "", path: str = "",
                      content: str = "") -> str:
    """Write a document into the Project's `user/` shelf — "yours" in
    the console's Documents rail.

    This is your ONLY write. `path` is relative to the Project's
    document root and must start with `user/`; every other area is
    read-only to you, `agent/` included. Full-file overwrite: send the
    whole text.

    Extensions: .md .tex .txt .lean .png .jpg .svg .pdf. Write the
    mathematics in LaTeX; a document a mathematician reads is the point.
    A `.tex` you wrote can be compiled with `tex_check` before you hand
    it over.

        write_project_doc(project="Erdos", path="user/p1_summary.md",
                          content="# What the route proves\\n…")
    """
    from ..state import project_docs
    if not (project or "").strip() or not (path or "").strip():
        return _ARG_HELP.format(
            tool="write_project_doc",
            hint='the parameters are `project`, `path` and `content`, '
                 'e.g. write_project_doc(project="Erdos", '
                 'path="user/notes.md", content="# …")')
    if not content:
        return _ARG_HELP.format(
            tool="write_project_doc",
            hint='`content` is empty — the whole document body goes in '
                 '`content` (a mis-spelled parameter name lands here)')
    try:
        rel = project_docs.write(_workspace_root(), project, path,
                                 content, area=project_docs.AREA_USER)
    except (KeyError, ValueError, OSError) as e:
        return _project_docs_error(e, tool="write_project_doc",
                                   project=project)
    return f"wrote {rel} ({len(content)} chars) in {project}'s documents"


@_seat_tool(structured_output=False)
def list_project_docs(project: str = "") -> str:
    """List the Project's documents — every shelf.

    `user/` is the person's shelf and the one you write into; `agent/`
    is the theory layer's, readable and not yours. One line per entry:
    path, kind, size.
    """
    from ..state import project_docs
    if not (project or "").strip():
        return _ARG_HELP.format(
            tool="list_project_docs",
            hint='the parameter is `project`, e.g. '
                 'list_project_docs(project="Erdos")')
    try:
        entries = project_docs.tree(_workspace_root(), project)
    except (ValueError, OSError) as e:
        return f"list_project_docs: {e}"
    if not entries:
        return (f"{project} has no documents yet. Write one with "
                f"write_project_doc(project=\"{project}\", "
                f"path=\"user/<name>.md\", content=…).")
    lines = [f"{e['path']}{'/' if e['kind'] == 'dir' else ''}"
             + ("" if e["kind"] == "dir" else f"  {e['size']}B")
             for e in entries]
    out = "\n".join(lines)
    return out if len(out) <= MAX_CHARS else out[:MAX_CHARS] + "\n… (truncated)"


@_seat_tool(structured_output=False)
def read_project_doc(project: str = "", path: str = "") -> str:
    """Read one of the Project's documents, from any shelf.

    `path` is relative to the document root (`user/…` or `agent/…`).
    Read the person's own notes before writing beside them.
    """
    from ..state import project_docs
    if not (project or "").strip() or not (path or "").strip():
        return _ARG_HELP.format(
            tool="read_project_doc",
            hint='the parameters are `project` and `path`, e.g. '
                 'read_project_doc(project="Erdos", path="user/plan.md")')
    if project_docs.is_binary(path):
        return (f"read_project_doc: {path} is an image or a pdf — the "
                f"person can see it; you cannot read it here.")
    try:
        raw = project_docs.read(_workspace_root(), project, path)
    except (KeyError, ValueError, OSError) as e:
        return _project_docs_error(e, tool="read_project_doc",
                                   project=project)
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n… (truncated; the file is longer)"
    return text


#: Where a `tex_check` build runs. Under `.asterism/`, never under the
#: Project: a compile that could write into the document's own folder
#: would be a second write channel wearing a compiler's name.
_TEX_BUILD = ("tmp", "tex_check")


@_seat_tool(structured_output=False)
def tex_check(project: str = "", path: str = "",
              keep_pdf: bool = False) -> str:
    """Compile a `.tex` you wrote and hand back what LaTeX said.

    `path` is one of the Project's documents under `user/` — the same
    shelf `write_project_doc` writes. The document is copied into a
    scratch directory and compiled there, so this never touches what is
    on the shelf; pass `keep_pdf=True` to have the resulting pdf placed
    beside the source when it succeeds.

    Answers: the error lines (`user/paper.tex:12: message`), or
    `compiled OK (N pages)`, or the fact that this machine has no TeX
    engine at all. Time-boxed; the engine is looked for at call time and
    named in the answer.

        tex_check(project="Erdos", path="user/note.tex")
    """
    from ..core import tex_engine
    from ..state import project_docs
    if not (project or "").strip() or not (path or "").strip():
        return _ARG_HELP.format(
            tool="tex_check",
            hint='the parameters are `project` and `path`, e.g. '
                 'tex_check(project="Erdos", path="user/note.tex")')
    rel = str(path).replace("\\", "/").strip("/")
    if not rel.lower().endswith(".tex"):
        return (f"tex_check: {path!r} is not a .tex file — this compiles "
                f"LaTeX documents. Give it the .tex you wrote.")
    workspace = _workspace_root()
    try:
        # the fence FIRST, and the same one the write goes through: the
        # area argument is what makes "only the person's shelf" a
        # property of the call rather than of this docstring
        doc = project_docs.locate(workspace, project, rel,
                                  area=project_docs.AREA_USER)
        if not doc.is_file():
            raise KeyError(rel)
        source = doc.read_bytes().decode("utf-8", errors="replace")
    except (KeyError, ValueError, OSError) as e:
        return _project_docs_error(e, tool="tex_check", project=project)

    name, exe = tex_engine.find_engine()
    if name is None or exe is None:
        return f"tex_check: {tex_engine.NO_ENGINE_DETAIL}. Nothing was run."

    import hashlib
    key = hashlib.sha1(f"{project}\0{rel}".encode("utf-8", "replace")
                       ).hexdigest()[:16]
    build = workspace.joinpath(".asterism", *_TEX_BUILD, key)
    res = tex_engine.compile_into(build, source, doc.parent, name, exe)
    if res.status == "timeout":
        # the build was stopped, but what it had already written is
        # still the diagnosis — dropping it costs the reader the one
        # line they can act on (2026-09-06: the log held `:110: …
        # Environment definition* undefined` and the answer said only
        # that a clock had run out)
        errors = tex_engine.error_lines(res.log, as_name=rel)
        if not errors:
            return (f"tex_check: {res.detail} and was stopped, with nothing "
                    f"in its log yet — an error is waiting for input, or "
                    f"the document is far larger than a note.")
        return (f"tex_check: {res.detail} and was stopped. This is how far "
                f"the log had got:\n" + "\n".join(errors))
    if res.status != "ok":
        errors = tex_engine.error_lines(res.log, as_name=rel)
        head = (f"tex_check: {name} could not compile {rel} "
                f"({res.detail}).")
        if not errors:
            tail = "\n".join(res.log.splitlines()[-20:])
            return f"{head} It printed:\n{tail}"
        return head + "\n" + "\n".join(errors)

    pages = tex_engine.page_count(res.log)
    said = f"compiled OK ({pages} pages)" if pages else "compiled OK"
    out = f"tex_check: {said} with {name}."
    if keep_pdf and res.pdf is not None:
        beside = rel[: -len(".tex")] + ".pdf"
        try:
            project_docs.write(workspace, project, beside,
                               res.pdf.read_bytes(),
                               area=project_docs.AREA_USER)
        except (KeyError, ValueError, OSError) as e:
            return f"{out} The pdf could not be placed beside it: {e}"
        out += f" The pdf is beside the source at {beside}."
    return out


@_seat_tool(structured_output=False)
def prepare_command(problem: str = "", kind: str = "",
                    payload: dict = None) -> str:
    """Prepare a framework command for the person to confirm.

    THIS DOES NOT RUN ANYTHING. It checks the command's own fields and
    returns what it WOULD affect, so the person can press the button in
    the console — running it is theirs to decide, always (§3.8).

    `kind` is one of Delegate, ReturnToParent, MarkDeliverable,
    ConfirmShelve, Inject, Signal. `payload` carries that decision's own
    fields, the same ones a Strategist writes:

        ConfirmShelve   target_goal_id, reason (a person's park is final)
        ReturnToParent  group_id, reason
        MarkDeliverable target_goal_id, optional reason
        Delegate        charter, or target_goal_id to take one from
        Inject          target_goal_id, proof (the `## Proof` to settle)
        Signal          pipeline_id, signal (return_to_parent | shelve |
                        return_to_nl) — stops ONE in-flight Formalizer;
                        `reason` is required for return_to_parent

    Returns JSON: `preview.affected` is every node the command would
    close, `revision` is the state the person is acting on, and
    `payload` is the command as it would be submitted.
    """
    import json as _json

    from ..state import commands as _commands
    from ..state import db as _db
    if not (problem or "").strip() or not (kind or "").strip():
        return _ARG_HELP.format(
            tool="prepare_command",
            hint='the parameters are `problem`, `kind` and `payload`, '
                 'e.g. prepare_command(problem="Erdos.p1", '
                 'kind="ConfirmShelve", payload={"target_goal_id": 12, '
                 '"reason": "the route is dead"})')
    body = payload if isinstance(payload, dict) else {}
    if kind not in _commands.KINDS:
        return (f"prepare_command: {kind!r} is not a command. The kinds "
                f"are {', '.join(sorted(_commands.KINDS))}.")
    try:
        _commands.validate_fields(kind, body)
    except ValueError as e:
        return f"prepare_command: {e}"
    path = _workspace_root() / "asterism.db"
    if not path.exists():
        return "prepare_command: this workspace has no database yet."
    # READ-ONLY connection: "never enqueues" is then a property of the
    # handle, not of this function's good behaviour.
    try:
        conn = _db.connect_readonly(path)
    except Exception as e:  # noqa: BLE001 — schema behind / locked
        return f"prepare_command: cannot read the database ({e})."
    try:
        if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            return (f"prepare_command: no problem named {problem!r} — "
                    f"check the name on the problem's own page.")
        preview = _commands.preview(conn, problem=problem, kind=kind,
                                    payload=body)
    finally:
        conn.close()
    return _json.dumps({"preview": preview, "payload": body, "kind": kind,
                        "problem": problem}, ensure_ascii=False)


@_seat_tool(structured_output=False)
def daemon_status() -> str:
    """What the engine is doing right now — running, scope, in flight.

    Read-only: nothing here starts, stops or steers a run.
    """
    import json as _json

    from ..core.cli import daemon_status as _status
    try:
        return _json.dumps(_status(_workspace_root()), ensure_ascii=False,
                           default=str)
    except Exception as e:  # noqa: BLE001 — a status must never raise
        return f"daemon_status: could not read the engine's state ({e})."


def _workspace_root():
    """The workspace, resolved the same way `inspect` resolves it — the
    Scholar's cwd is its own problem directory, and `fetch` needs the
    root to shelve into. One resolver, not two."""
    from pathlib import Path as _Path

    from . import workspace_query
    return workspace_query.workspace_of(_Path.cwd()) or _Path.cwd()


def main() -> None:
    # The two pipes below are the protocol, and until this call they are
    # also what every child of this process inherits. `tex_check` spawns
    # a TeX toolchain; a spawn that inherits stdin does not run AT ALL on
    # win32 (2026-09-06, measured — see `process_group`), and one that
    # inherits stdout writes into the middle of a JSON-RPC frame. Fenced
    # here, once, so no tool below has to know that.
    from ..core import process_group
    process_group.fence_std_handles_from_children()
    mcp.run()


if __name__ == "__main__":
    main()
