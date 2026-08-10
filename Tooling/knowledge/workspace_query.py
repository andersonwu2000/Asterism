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

import os
import re
from pathlib import Path

#: Per-query line cap when the caller does not choose one.
DEFAULT_MAX = 40
#: Ceiling on one query's cap, so `max: 100000` cannot be used to dump
#: the tree into a context window.
MAX_MAX = 400
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

def _expand(spec: str, cwd: Path) -> "list[Path]":
    """A path or a glob, relative to the agent's own directory."""
    p = (cwd / spec) if not Path(spec).is_absolute() else Path(spec)
    if any(ch in spec for ch in "*?["):
        base = p.parent
        return sorted(x for x in base.glob(p.name) if x.is_file())
    if p.is_dir():
        return sorted(x for x in p.rglob("*")
                      if x.is_file() and not _skipped(x))
    return [p] if p.exists() else []


def _skipped(p: Path) -> bool:
    return any(part in _SKIP_DIRS for part in p.parts)


def _nearest_existing(p: Path) -> str:
    """What a wrong path costs should be nothing.

    Before this, a mistyped path cost a whole round-trip: the agent got
    "no such file" and spent its next turn on `ls` to find out what was
    actually there. Answer both at once."""
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
        return [f"nothing to search at {where!r}; {_nearest_existing(cwd / where)}"]
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


def _q_read(q: dict, cwd: Path, deny) -> "list[str]":
    spec = str(q.get("read") or "")
    p = (cwd / spec) if not Path(spec).is_absolute() else Path(spec)
    root = _denied(p.resolve(), deny)
    if root is not None:
        return [f"{p} is operator-private (under {root}) — Context.md, "
                f"BRIEF.md and the Manifest carry what you are meant to know"]
    if not p.is_file():
        return [f"no file at {p}; {_nearest_existing(p)}"]
    lines = _read_text(p).splitlines()
    rng = str(q.get("lines") or "").strip()
    if rng:
        lo, _, hi = rng.partition("-")
        try:
            a = int(lo) if lo else 1
            b = int(hi) if hi else len(lines)
        except ValueError:
            return [f"bad `lines` {rng!r} — use \"380-420\", \"-40\" or \"40-\""]
        chosen = [f"{n:>5}  {lines[n - 1]}"
                  for n in range(max(1, a), min(len(lines), b) + 1)]
    else:
        chosen = [f"{n:>5}  {ln}" for n, ln in enumerate(lines, 1)]
    kept, note = _cap(chosen, q.get("max", DEFAULT_MAX),
                      ", or ask for a line range with `lines`")
    return kept + ([note] if note else [])


def _q_find(q: dict, cwd: Path, deny) -> "list[str]":
    pattern = str(q.get("find") or "*")
    base = (cwd / str(q.get("in") or ".")).resolve()
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


def run_queries(queries: "list[dict]", *, cwd: "Path | None" = None,
                max_chars: int = 8000) -> str:
    """Answer each query, labelled and capped, in one string."""
    here = Path(cwd or Path.cwd())
    deny = _deny_roots(here)
    if not isinstance(queries, list) or not queries:
        return ("inspect: pass a list of queries, e.g. "
                '[{"decl": "uc_four_set_deficit"}, '
                '{"grep": "BoundedOrder", "in": "proofs/*.lean"}]')
    blocks: "list[str]" = []
    for n, q in enumerate(queries, 1):
        if not isinstance(q, dict):
            blocks.append(f"[{n}] not a query object: {q!r}")
            continue
        for key, fn in _KINDS:
            if key in q:
                where = f" in {q['in']}" if q.get("in") else ""
                head = f"[{n}] {key} {q[key]!r}{where}"
                try:
                    body = fn(q, here, deny)
                except Exception as exc:  # noqa: BLE001 — one bad query
                    body = [f"failed: {type(exc).__name__}: {exc}"]
                blocks.append(head + "\n" + "\n".join(body))
                break
        else:
            blocks.append(
                f"[{n}] no known query key in {sorted(q)}. Use one of: "
                f"decl, grep, read, find, size.")
    out = "\n\n".join(blocks)
    if len(out) > max_chars:
        out = (out[:max_chars]
               + f"\n\n… whole result truncated at {max_chars} chars. "
                 f"Ask fewer questions per call, or lower `max`.")
    return out
