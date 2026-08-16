"""`inspect` — several read questions, one round-trip.

Sized from the shell survey (2026-08-10, 32,993 calls over 6,264 spawn
transcripts). In the current policy era ~91% of shell use is plain
reading, and the shape of it is the design brief:

    60% chain two or more commands      -> several queries per call
    32% pipe into `head`                -> every query carries its own cap
    12% use `echo ===` as a separator   -> labelled result sections
    10% read a line range               -> `read` with `lines`
     7% `wc`                            -> `size`
     6% `grep -A/-B`                    -> `context`

So the gap was never "grep is too weak" — Grep already takes context and
a limit. It was that ONE call could ask three questions and cap its own
output, and per-question tools could not. Hence a batch.

`decl` is the one query that is not a shell verb, and it is the point.
The single most common six-segment chain in the corpus is

    cd proofs && grep -n -A25 "^theorem foo" *.lean | head -40

— a semantic question ("what is `foo`?") approximated with file, line
and regex because a shell cannot know what a declaration is. The
framework does: it has the statement, the file and the proof status in
its own tables. The tool answers from those and the agent never touches
the database.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

#: Per-query line cap when the caller does not choose one. Applies to
#: the queries that return a LIST of hits (`grep`, `find`, `size`),
#: where 40 is a sane page. It does NOT apply to `read`: a document is
#: read by the section, and a section arrives whole (see `_q_read`).
DEFAULT_MAX = 40
#: Ceiling on one query's cap, so `max: 100000` cannot be used to dump
#: the tree into a context window.
MAX_MAX = 400

#: Byte budget for ONE query's answer. NOT a pool: every query in a
#: batch gets this much, and asking a second question never shrinks the
#: answer to the first. It used to be `8000 // len(queries)` with a 600
#: floor, which punished the very batching the tool asks for — measured
#: 2026-08-15 on the codex probe: 24 of 51 calls carried exactly ONE
#: query, 24 of 51 answers came back truncated, and half of that run's
#: turns were `inspect` round-trips at ~4,273 fresh tokens each. Sized
#: at 12KB because the largest single section across the 1,459 framework
#: documents agents actually read is 9.5KB (p90: 2.4KB).
PER_QUERY_CHARS = 12_000
#: Queries answered in one call. The call-level limit is a COUNT, not a
#: byte pool, and that is the whole point: a count defers whole
#: questions by name, while a shared byte budget has to cut into
#: answers that were already computed. Every answer is complete or
#: explicitly deferred.
MAX_QUERIES = 20

#: A markdown heading, which is how a framework document declares its
#: sections. Level 1-4 only: deeper is prose formatting, not structure.
_HEADING_RE = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")
#: Bytes read from any single file. Lean proofs are small; a stray
#: multi-megabyte artifact should not stall the call.
_MAX_FILE_BYTES = 4_000_000
_SKIP_DIRS = {".git", ".lake", "__pycache__", "node_modules", ".venv",
              "build", ".asterism"}


# --------------------------------------------------------- resolution

def workspace_of(start: Path) -> "Path | None":
    """Walk up to the directory that owns both `Problems` and `Tooling`.

    The MCP server is spawned with the AGENT's cwd and no `cwd` key in
    the config schema (`pipeline.tools_mcp_entry`), so where it runs is
    where the agent is — which is exactly what makes relative paths in a
    query mean what the agent expects."""
    for d in (start, *start.parents):
        if (d / "Problems").is_dir() and (d / "Tooling").is_dir():
            return d
    env = (os.environ.get("PYTHONPATH") or "").split(os.pathsep)
    for p in env:
        if p and (Path(p) / "Problems").is_dir():
            return Path(p)
    return None


def _problem_dir_of(cwd: Path, workspace: "Path | None") -> "Path | None":
    if workspace is None:
        return None
    try:
        rel = cwd.resolve().relative_to((workspace / "Problems").resolve())
    except (ValueError, OSError):
        # An Adversary runs in `.attempts/<pid>/adversary/rN`, which is
        # under no problem at all. The fence then keeps the three
        # operator-private subtrees and drops the foreign-problem part —
        # the same "err toward a working spawn" fallback `envelope`
        # makes, and for the same reason: a read fence that blinds a
        # legitimate reader is the more expensive failure.
        return None
    parts = rel.parts
    return (workspace / "Problems" / parts[0] / parts[1] if len(parts) >= 2
            else workspace / "Problems" / parts[0] if parts else None)


def _deny_roots(cwd: Path) -> "tuple[Path, ...]":
    from ..llm.envelope import read_deny_roots
    ws = workspace_of(cwd)
    return read_deny_roots(ws, _problem_dir_of(cwd, ws))


def _denied(path: Path, deny: "tuple[Path, ...]") -> "Path | None":
    for root in deny:
        try:
            path.relative_to(root)
            return root
        except ValueError:
            continue
    return None


# ------------------------------------------------------------ helpers

def _own_attempt_dir() -> "Path | None":
    """This spawn's own attempts directory, or None outside a spawn.

    `envelope.Envelope.write_roots[0]` IS the attempts sandbox and the
    spawn already carries it as `ASTERISM_SPAWN_WRITE_ROOTS` — the tool
    simply never read it."""
    raw = (os.environ.get("ASTERISM_SPAWN_WRITE_ROOTS") or "").strip()
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            p = Path(part)
            return p if p.is_dir() else None
    return None


def _resolve(spec: str, cwd: Path) -> Path:
    """A relative path against the TWO directories a spawn works in.

    A spawn's cwd is its problem dir, but its briefing — `Context.md`,
    `CATALOG.md`, its seeded `new_*.lean` — lives in its attempts dir.
    Bare framework filenames must find that, and must find THIS spawn's
    copy: before 2026-08-16 a miss fell through to a basename scan of
    the whole `.attempts/` tree, which returned whatever sorted first
    and handed the agent another spawn's state (43 self-reports in one
    day; a formalizer read one attempt's `new_forward.lean` while the
    LSP edited its own)."""
    if Path(spec).is_absolute():
        return Path(spec)
    here = cwd / spec
    if here.exists():
        return here
    own = _own_attempt_dir()
    if own is not None and (own / spec).exists():
        return own / spec
    return here


def _expand(spec: str, cwd: Path) -> "list[Path]":
    """A path or a glob, relative to the agent's own directories."""
    p = _resolve(spec, cwd)
    if any(ch in spec for ch in "*?["):
        base = p.parent
        hits = sorted(x for x in base.glob(p.name) if x.is_file())
        own = _own_attempt_dir()
        if not hits and own is not None and not Path(spec).is_absolute():
            ob = (own / spec).parent
            hits = sorted(x for x in ob.glob(Path(spec).name) if x.is_file())
        return hits
    if p.is_dir():
        return sorted(x for x in p.rglob("*")
                      if x.is_file() and not _skipped(x))
    return [p] if p.exists() else []


def _skipped(p: Path) -> bool:
    return any(part in _SKIP_DIRS for part in p.parts)


def _find_by_basename(name: str, cwd: Path) -> "Path | None":
    """Where a file of this name is, among the agent's OWN roots.

    A spawn works in TWO directories — the problem dir it is launched in
    and the attempts dir its briefing, `Context.md` and `CATALOG.md` live
    in — and a relative path resolves against only the first. So
    `inspect({"grep": "…", "in": "CATALOG.md"})` failed, and the hint
    walked up to the workspace root and listed the repo. Naming the file
    where it IS costs one glob and saves the round trip.

    It searched the whole `.attempts/` tree until 2026-08-16 and
    returned whatever sorted first — a SIBLING spawn's file, complete
    and plausible and not this agent's. A hint that points at another
    spawn's state is worse than no hint, so the search stops at this
    spawn's own two directories."""
    roots = [cwd]
    own = _own_attempt_dir()
    if own is not None:
        roots.append(own)
    for root in roots:
        try:
            for cand in sorted(root.rglob(name)):
                if cand.is_file() and not _skipped(cand):
                    return cand
        except OSError:
            continue
    return None


def _nearest_existing(p: Path, cwd: "Path | None" = None) -> str:
    """What a wrong path costs should be nothing.

    Before this, a mistyped path cost a whole round-trip: the agent got
    "no such file" and spent its next turn on `ls` to find out what was
    actually there. Answer both at once."""
    if cwd is not None:
        found = _find_by_basename(p.name, cwd)
        if found is not None:
            return f"but a file of that name is at {found} — use that path"
    for d in p.parents:
        if d.is_dir():
            try:
                names = sorted(x.name + ("/" if x.is_dir() else "")
                               for x in d.iterdir())[:20]
            except OSError:
                names = []
            listing = ", ".join(names) if names else "(empty)"
            return f"nearest existing directory is {d} — it holds: {listing}"
    return "no existing parent directory"


def _read_text(p: Path) -> str:
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.read(_MAX_FILE_BYTES)
    except OSError as exc:
        return f"<unreadable: {exc}>"


def _cap(lines: "list[str]", want: int, how_to_get_more: str
         ) -> "tuple[list[str], str]":
    """Truncation is a VIEW, never a loss: say how many were dropped and
    exactly how to see them (`能 grep/懶載入的東西不需要 cap` — a cap that
    hides its own existence is the thing that rule forbids)."""
    want = max(1, min(int(want), MAX_MAX))
    if len(lines) <= want:
        return lines, ""
    dropped = len(lines) - want
    return lines[:want], (f"… {dropped} more. Re-run with "
                          f"max: {min(len(lines), MAX_MAX)}{how_to_get_more}")


# ------------------------------------------------------------ queries

def _q_grep(q: dict, cwd: Path, deny) -> "list[str]":
    pattern = str(q.get("grep") or "")
    where = str(q.get("in") or ".")
    ctx = int(q.get("context") or 0)
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return [f"bad pattern: {exc}"]
    files = _expand(where, cwd)
    if not files:
        return [f"nothing to search at {where!r}; {_nearest_existing(cwd / where, cwd)}"]
    hits: "list[str]" = []
    for f in files:
        root = _denied(f.resolve(), deny)
        if root is not None:
            continue
        lines = _read_text(f).splitlines()
        for i, line in enumerate(lines):
            if not rx.search(line):
                continue
            rel = _rel(f, cwd)
            if ctx:
                lo, hi = max(0, i - ctx), min(len(lines), i + ctx + 1)
                hits.append(f"{rel}:{i + 1}:")
                hits += [f"  {n + 1:>5}  {lines[n]}" for n in range(lo, hi)]
            else:
                hits.append(f"{rel}:{i + 1}: {line.strip()}")
    if not hits:
        return ["no matches"]
    kept, note = _cap(hits, q.get("max", DEFAULT_MAX),
                      ", or narrow `in` to fewer files")
    return kept + ([note] if note else [])


def _sections(lines: "list[str]") -> "list[tuple[str, int, int, int]]":
    """(heading text, level, first line, last line) for each section.

    A section runs to the next heading of the SAME OR SHALLOWER level, so
    asking for `## Programme` brings its `###` subsections with it — the
    nesting a reader means when it names a section. Line numbers are
    1-based and inclusive, so they can be handed straight back as
    `lines`."""
    heads = []
    for i, ln in enumerate(lines, 1):
        m = _HEADING_RE.match(ln)
        if m:
            heads.append((m.group(2), len(m.group(1)), i))
    out = []
    for k, (text, level, start) in enumerate(heads):
        end = len(lines)
        for text2, level2, start2 in heads[k + 1:]:
            if level2 <= level:
                end = start2 - 1
                break
        out.append((text, level, start, end))
    return out


def _numbered(lines: "list[str]", a: int, b: int) -> "list[str]":
    return [f"{n:>5}  {lines[n - 1]}"
            for n in range(max(1, a), min(len(lines), b) + 1)]


def _q_read(q: dict, cwd: Path, deny) -> "list[str]":
    """A document is read by the SECTION; a window is the fallback.

    `sections: ["Programme"]` is the cheap, precise request a framework
    document supports by construction — its headings are a stable API,
    written by the same code that writes the prose. `outline: true` buys
    the map when the caller does not know which section it wants, and
    `lines` still serves files with no headings at all (`.lean`).

    What is gone is the old default: 40 numbered lines, which turned
    reading one 25KB `Context.md` into a four-call ladder and still
    delivered it truncated. Measured 2026-08-15: `Context.md` was read
    22 times across 6 codex sessions, and 24 of that run's 51 answers
    carried a truncation notice.
    """
    spec = str(q.get("read") or "")
    p = _resolve(spec, cwd)
    root = _denied(p.resolve(), deny)
    if root is not None:
        return [f"{p} is operator-private (under {root}) — Context.md, "
                f"BRIEF.md and the Manifest carry what you are meant to know"]
    if not p.is_file():
        return [f"no file at {p}; {_nearest_existing(p, cwd)}"]
    lines = _read_text(p).splitlines()
    secs = _sections(lines)

    if q.get("outline"):
        if not secs:
            return [f"{len(lines)} lines, no markdown headings — this file "
                    f"has no sections. Read it whole, or a window with "
                    f'`lines: "1-200"`.']
        out = [f"{len(secs)} sections, {len(lines)} lines:"]
        for text, level, a, b in secs:
            size = sum(len(lines[n - 1]) + 1 for n in range(a, b + 1))
            out.append(f'  {"#" * level} {text}   lines {a}-{b}, '
                       f'{size:,} chars')
        out.append('Ask for one with `sections: ["<heading text>"]`.')
        return out

    want = q.get("sections")
    if want is not None:
        names = [str(w) for w in (want if isinstance(want, list) else [want])]
        # Lists, not single tuples: stacked documents carry the same
        # heading more than once (the adversary's charter.md stacks a
        # chain of charters, two of which said "## The claim to settle"
        # — measured 2026-08-15), and a dict comprehension silently
        # kept one of them. Duplicates are answered with the first AND
        # disclosed, so the reader knows there is another.
        by_name: "dict[str, list[tuple[str, int, int]]]" = {}
        for text, _l, a, b in secs:
            by_name.setdefault(text.lower(), []).append((text, a, b))
        chosen: "list[str]" = []
        missing: "list[str]" = []
        for name in names:
            hits = by_name.get(name.strip().lower())
            if hits is None:
                missing.append(name)
                continue
            text, a, b = hits[0]
            chosen.append(f"── {text}  (lines {a}-{b})")
            chosen += _numbered(lines, a, b)
            if len(hits) > 1:
                where = ", ".join(f"lines {a2}-{b2}"
                                  for _t, a2, b2 in hits[1:])
                chosen.append(
                    f"note: {len(hits)} sections share this heading — "
                    f"this is the first; the other"
                    f"{'s are' if len(hits) > 2 else ' is'} at {where} "
                    f"(read one with `lines`).")
        if missing:
            # No fuzzy matching: a near-miss that silently answers with
            # the wrong section is worse than a refusal. And NO roster
            # (owner ruling 2026-08-15): `outline` already IS the
            # roster, with line ranges and sizes — on the 383-section
            # CATALOG.md the inlined listing was itself a 12KB cap-hit,
            # a refusal whose length scaled with the file. The count
            # stays: one number, and it tells the reader whether to
            # think before calling `outline` at all.
            chosen.append(
                f"no section named {', '.join(map(repr, missing))} in "
                f"this file — it has {len(secs)} section"
                f"{'' if len(secs) == 1 else 's'}; `outline: true` "
                f"lists them.")
        return chosen or [f"{len(lines)} lines, no sections matched"]

    rng = str(q.get("lines") or "").strip()
    if rng:
        lo, _, hi = rng.partition("-")
        try:
            a = int(lo) if lo else 1
            b = int(hi) if hi else len(lines)
        except ValueError:
            return [f"bad `lines` {rng!r} — use \"380-420\", \"-40\" or \"40-\""]
        return _numbered(lines, a, b)
    # Whole file. The byte budget in `run_queries` bounds it and says
    # where to resume; an explicit `max` still caps by line for a caller
    # that wants a peek.
    if q.get("max") is not None:
        kept, note = _cap(_numbered(lines, 1, len(lines)), q["max"],
                          ", or name a section with `sections`")
        return kept + ([note] if note else [])
    return _numbered(lines, 1, len(lines))


def _q_find(q: dict, cwd: Path, deny) -> "list[str]":
    pattern = str(q.get("find") or "*")
    base = _resolve(str(q.get("in") or "."), cwd).resolve()
    # An absolute pattern is the natural phrasing when the only path you
    # were given is absolute (the Adversary's projection is), and
    # `rglob` answers it with `NotImplementedError: Non-relative
    # patterns are unsupported` — a Python type name, which tells an
    # agent nothing it can act on. The request is unambiguous, so honour
    # it: the directory part becomes the search root and the last
    # component stays the pattern.
    if Path(pattern).is_absolute() or (q.get("in") is None
                                       and "/" in pattern):
        p = Path(pattern)
        base, pattern = (p.parent.resolve() if p.parent != p
                         else base), p.name
    if not base.is_dir():
        return [f"no directory at {base}; {_nearest_existing(base)}"]
    out = [_rel(p, cwd) for p in sorted(base.rglob(pattern))
           if not _skipped(p) and _denied(p, deny) is None]
    if not out:
        return ["no matches"]
    kept, note = _cap(out, q.get("max", DEFAULT_MAX), "")
    return kept + ([note] if note else [])


def _q_size(q: dict, cwd: Path, deny) -> "list[str]":
    files = [f for f in _expand(str(q.get("size") or "."), cwd)
             if _denied(f.resolve(), deny) is None]
    if not files:
        return ["nothing there"]
    rows = []
    for f in files:
        text = _read_text(f)
        rows.append(f"{_rel(f, cwd)}: {len(text.splitlines())} lines, "
                    f"{len(text)} chars")
    kept, note = _cap(rows, q.get("max", DEFAULT_MAX), "")
    return kept + ([note] if note else [])


def _q_decl(q: dict, cwd: Path, deny) -> "list[str]":
    """Answered from the framework's own tables, not from a regex.

    The agent asks "what is `foo`" and gets the statement, where it
    lives and whether it is proved — three facts the shell could only
    approximate by grepping for a keyword at the start of a line."""
    name = str(q.get("decl") or "").strip()
    if not name:
        return ["give a declaration name"]
    ws = workspace_of(cwd)
    if ws is None:
        return ["cannot locate the workspace from here"]
    try:
        from ..state import db as _db
        conn = _db.connect_readonly(ws / "asterism.db")
    except Exception as exc:  # noqa: BLE001 — never fail the whole batch
        return [f"declaration index unavailable ({type(exc).__name__})"]
    try:
        rows = conn.execute(
            # Exact first, then substring: an agent that typed the whole
            # name wants THAT one, and burying it among six near-misses
            # is the same "answer is in there somewhere" failure the
            # CATALOG had.
            "SELECT slug, lean_path, statement, status, problem FROM goals "
            "WHERE slug = ? OR slug LIKE ? "
            "ORDER BY (slug = ?) DESC, slug LIMIT 6",
            (name, f"%{name}%", name)).fetchall()
    except Exception as exc:  # noqa: BLE001
        return [f"declaration index unavailable ({type(exc).__name__})"]
    finally:
        conn.close()
    if not rows:
        return [f"no declaration named {name!r} in this run's record. "
                f"For a Mathlib name use `loogle`."]
    # The FULL signature from the stub file, not the stored `statement`.
    # `goals.statement` holds the pp-canonical CONCLUSION only, so a
    # by_contra sub-goal renders as literally `False` — which is why the
    # eager `## Active goals` section had used `goal_display_signature`
    # since 2026-07-18. When that section went lazy (2026-08-10) this
    # query became its replacement and, for one hour, gave back LESS than
    # what it replaced: the exact goals whose signature matters most were
    # the ones it flattened. Same helper, so the lazy path is equivalent
    # to the eager one it retired rather than a cheaper imitation of it.
    from ..agent import context as _ctx
    # An EXACT hit answers alone. Substring matching is the fallback for
    # a half-remembered name, but once the caller has typed the whole
    # thing, attaching every near-miss is the CATALOG's old failure in a
    # new place — the answer is in there somewhere, under two others.
    # Measured: three matches on one query, ~1,000 characters each,
    # because a full signature is a full signature.
    exact = [r for r in rows if r["slug"] == name]
    others = len(rows) - len(exact)
    if exact:
        rows, note = exact, (f"({others} other slug(s) contain {name!r} — "
                             f"ask for one by its full name)" if others else "")
    else:
        note = ""
    out: "list[str]" = []
    if note:
        out.append(note)
    for r in rows:
        out.append(f"{r['slug']}  [{r['status']}]  {r['lean_path']}")
        try:
            sig = _ctx.goal_display_signature(
                ws, str(r["slug"]), r["lean_path"], r["statement"])
        except Exception:  # noqa: BLE001 — a missing stub falls back
            sig = r["statement"] or ""
        out += [f"    {ln}" for ln in (sig or "").strip().splitlines()[:16]]
    return out


_KINDS = (("decl", _q_decl), ("grep", _q_grep), ("read", _q_read),
          ("find", _q_find), ("size", _q_size))


def _rel(p: Path, cwd: Path) -> str:
    # Forward slashes on every platform: these paths get pasted straight
    # into `import`s, into the next query and into prose, and a mixed
    # `proofs\L_x.lean` reads as an escape sequence half the time.
    try:
        return p.resolve().relative_to(cwd.resolve()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _resume_hint(text: str, kept: str, q: dict) -> str:
    """Where to pick up, with NO overlap and nothing to count by hand.

    The numbered output makes this exact: the last line that survived
    the cut is the last one the reader has, so the next request starts
    at the one after it. A hint that says "re-run this query alone"
    (the old one) is not a continuation — it re-sends everything the
    reader already paid for."""
    last = 0
    for ln in kept.splitlines():
        head = ln[:5].strip()
        if head.isdigit():
            last = int(head)
    if not last:
        return "Narrow the query."
    if "read" in q:
        return (f'Continue from line {last + 1}: '
                f'{{"read": {str(q["read"])!r}, "lines": "{last + 1}-"}} '
                f'— or name a section with `sections` / map it with '
                f'`outline: true`.')
    return f"Continue from line {last + 1} with `lines`."


def _deferral_note(deferred: "list[tuple[int, object]]", reason: str) -> str:
    """The way back for whole queries this reply could not carry:
    every one named, in the vocabulary the count limit already uses.

    It named them with `sorted(d)` until 2026-08-16 — the dict's KEYS —
    so a deferred `{"read": "charter.md", "sections": ["Proof"]}` came
    back as `[11] ['read', 'sections']` and "send these in a second
    call" was unfollowable: the reader had to reconstruct which file it
    had even asked about. Three agents reported it within an hour of
    the deferral shipping. Echo the query itself; it is what they
    resend."""
    listed = "; ".join(
        f"[{i}] {json.dumps(d, ensure_ascii=False, sort_keys=True)}"
        if isinstance(d, dict) else f"[{i}] {d}"
        for i, d in deferred)
    return (f"— {len(deferred)} quer"
            f"{'y' if len(deferred) == 1 else 'ies'} not answered: "
            f"{reason} Send these in a second call: {listed}")


def run_queries(queries: "list[dict]", *, cwd: "Path | None" = None,
                per_query_chars: int = PER_QUERY_CHARS,
                max_queries: int = MAX_QUERIES,
                delivery_chars: "int | None" = None) -> str:
    """Answer each query, labelled, in one string.

    EVERY QUERY GETS THE WHOLE BUDGET. It used to get `8000 //
    len(queries)`, and that was a pool: a second question shrank the
    answer to the first, so the tool asked for batches and then charged
    for them. Agents learned the lesson the pricing taught — on the
    2026-08-15 codex probe, 24 of 51 calls carried exactly one query,
    and half that run's turns were `inspect` round-trips at ~4,273 fresh
    tokens each. Batching is now free.

    The call-level limit is a COUNT, not a byte pool. A count defers
    whole questions by name and answers the rest in full; a shared
    budget has to cut into answers that were already computed. Every
    answer here is complete, or explicitly named as deferred.

    `delivery_chars` is the TRANSPORT's ceiling, not another pool. The
    codex exec channel hands the model ~10K tokens of tool output and
    amputates the middle of anything larger (measured 2026-08-15: a
    90,417-char reply delivered as 39,700, mid-batch answers gone). So
    the reply must fit the pipe HERE, where whole queries can still be
    deferred by name — once the next answer would overflow it, that
    query and every later one wait for a second call. Answers already
    delivered keep their full per-query budget; the FIRST query is
    always answered even alone over the ceiling. None = a backend
    nobody has measured; no ceiling is applied (`llm/capabilities.
    mcp_result_delivery_chars` owns the numbers).
    """
    here = Path(cwd or Path.cwd())
    deny = _deny_roots(here)
    if not isinstance(queries, list) or not queries:
        return ("inspect: pass a list of queries, e.g. "
                '[{"decl": "uc_four_set_deficit"}, '
                '{"read": "Context.md", "sections": ["Programme"]}]')
    count_deferred: "list[tuple[int, object]]" = [
        (max_queries + i, d)
        for i, d in enumerate(queries[max_queries:], 1)]
    budget_deferred: "list[tuple[int, object]]" = []
    blocks: "list[str]" = []
    srcs: "list[tuple[int, object]]" = []  # blocks[i] answers srcs[i]
    joined = 0  # len("\n\n".join(blocks))
    for n, q in enumerate(queries[:max_queries], 1):
        if budget_deferred:  # ceiling hit — everything later waits too
            budget_deferred.append((n, q))
            continue
        if not isinstance(q, dict):
            block = f"[{n}] not a query object: {q!r}"
        else:
            for key, fn in _KINDS:
                if key in q:
                    where = f" in {q['in']}" if q.get("in") else ""
                    head = f"[{n}] {key} {q[key]!r}{where}"
                    try:
                        body = fn(q, here, deny)
                    except Exception as exc:  # noqa: BLE001 — one bad query
                        body = [f"failed: {type(exc).__name__}: {exc}"]
                    text = "\n".join(body)
                    if len(text) > per_query_chars:
                        kept = text[:per_query_chars]
                        text = (kept + f"\n… [{n}] truncated at "
                                       f"{per_query_chars:,} chars. "
                                + _resume_hint(text, kept, q))
                    block = head + "\n" + text
                    break
            else:
                block = (f"[{n}] no known query key in {sorted(q)}. Use one "
                         f"of: decl, grep, read, find, size.")
        sep = 2 if blocks else 0
        if (delivery_chars is not None and blocks
                and joined + sep + len(block) > delivery_chars):
            budget_deferred.append((n, q))
            continue
        blocks.append(block)
        srcs.append((n, q))
        joined += sep + len(block)
    while True:
        deferred = budget_deferred + count_deferred
        if budget_deferred:
            note = _deferral_note(
                deferred, f"delivering more would overflow this reply's "
                          f"{delivery_chars:,}-char budget.")
        elif count_deferred:
            note = _deferral_note(
                deferred, f"this call carried {len(queries)} and the limit "
                          f"is {max_queries}.")
        else:
            note = ""
        total = joined + (2 + len(note) if note else 0)
        if (delivery_chars is None or total <= delivery_chars
                or len(blocks) <= 1):
            # ≤ 1: the first query is answered whatever it costs — a
            # reply that deferred everything would answer nothing.
            break
        # The deferral note itself needs room: hand back the last
        # delivered answer, whole, rather than cutting anything.
        budget_deferred.insert(0, srcs.pop())
        joined -= len(blocks.pop()) + 2
    return "\n\n".join(blocks + ([note] if note else []))
