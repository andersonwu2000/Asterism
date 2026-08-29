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

import fnmatch
import json
import os
import re
import time
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
#: How much of a deferred query is echoed back so the reader can resend
#: it. Bounded because the echo is an ADDRESS, not the payload: a batch
#: carrying long grep patterns otherwise produced a deferral note larger
#: than the reply it was appended to.
_ECHO_CHARS = 200
#: And the note as a WHOLE is bounded too: per-echo bounding fixed the
#: query-size vector, but the note's length was still a function of the
#: query COUNT — 1 read + 400 greps produced an 88,043-char reply
#: against a 30,000-char `delivery_chars` (acceptance pass, 2026-08-17),
#: ~200 chars of ticket per deferred query with no aggregate ceiling.
#: Echoes past this budget collapse to an index range; the caller still
#: holds the full list it sent.
_NOTE_CHARS = 2_000
#: `outline: true` lists a file whole only up to this many sections.
#: Past it the map IS the roster (CATALOG.md: 1,333 sections, 30-60K
#: chars — owner ruling 2026-08-29) and must be asked for by name:
#: `outline_prefix` / `outline_grep`, answered up to this many hits.
OUTLINE_INLINE_MAX = 120
OUTLINE_MATCH_MAX = 60

#: A markdown heading, which is how a framework document declares its
#: sections. Level 1-4 only: deeper is prose formatting, not structure.
_HEADING_RE = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")
#: Bytes read from any single file. Lean proofs are small; a stray
#: multi-megabyte artifact should not stall the call.
_MAX_FILE_BYTES = 4_000_000
_SKIP_DIRS = {".git", ".lake", "__pycache__", "node_modules", ".venv",
              "build", ".asterism"}

#: Big trees an agent almost never MEANS when it aims a walk at a broad
#: root — pruned unless the walk's root is explicitly inside one. The
#: 2026-08-23 fleet stall was one grep whose walk wandered into these
#: and read files for 28 minutes.
_HEAVY_DIRS = {".attempts", "Papers", "_spike", ".playwright-mcp"}

#: Scan budget for ONE grep query: whichever trips first stops the scan
#: with the partial hits and an actionable note (`after` continues; a
#: narrower `in` finishes). The budget protects the shared CPU, not the
#: reply size — output is bounded separately by `max`.
_SCAN_MAX_FILES = 3000
_SCAN_MAX_BYTES = 48 * 1024 * 1024
_SCAN_MAX_SEC = 60.0


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

    Declared by `spawn_guard.ATTEMPT_DIR_ENV`, which every adapter
    renders in the dialect that actually reaches THIS process — the MCP
    tools server, a child the provider starts, not the spawn itself.
    `ASTERISM_SPAWN_WRITE_ROOTS` is the fallback: it carries the same
    path first, and claude's whole-environment inheritance delivers it,
    but codex hands its MCP children a fixed core set that drops it.

    Each candidate is tried in turn — a first entry that no longer
    exists must not switch the whole mechanism off silently.

    The shim's request-local ContextVar comes FIRST: there one process
    serves many spawns concurrently, and the env route needed a global
    lock that a 28-minute grep turned into a fleet-wide stall
    (2026-08-23)."""
    from ..llm.spawn_guard import (ATTEMPT_DIR_CONTEXT, ATTEMPT_DIR_ENV,
                                   WRITE_ROOTS_ENV)
    ctx = ATTEMPT_DIR_CONTEXT.get()
    if ctx and Path(ctx).is_dir():
        return Path(ctx)
    for var in (ATTEMPT_DIR_ENV, WRITE_ROOTS_ENV):
        raw = (os.environ.get(var) or "").strip()
        for part in raw.split(os.pathsep):
            part = part.strip()
            if part and Path(part).is_dir():
                return Path(part)
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
    if own is not None:
        # Inside `own`, and STILL inside it after `..` — the second
        # branch is a new door, and `../<other-pid>/new_forward.lean`
        # walked straight through it into a sibling attempt, which is
        # the whole defect this resolution exists to close.
        cand = own / spec
        try:
            cand.resolve().relative_to(own.resolve())
        except (ValueError, OSError):
            return here
        if cand.exists():
            return cand
    return here


def _glob_split(p: Path) -> "tuple[Path, str]":
    """The deepest glob-free prefix of `p`, and the rest as a pattern.

    Only the LAST component used to be the pattern, so a multi-level
    glob (`Library/**/*.lean`) walked into a literal `**` directory and
    silently matched nothing — the presearch seat read that as "the
    Library is unavailable" and shipped an empty block every node
    (2026-08-22, the run's largest feedback cluster)."""
    parts = p.parts
    for i, part in enumerate(parts):
        if any(ch in part for ch in "*?["):
            return Path(*parts[:i]), "/".join(parts[i:])
    return p.parent, p.name


def _tokens_match(parts: "tuple[str, ...]", toks: "list[str]") -> bool:
    """Path components against glob tokens; `**` spans zero or more."""
    if not toks:
        return not parts
    t, rest = toks[0], toks[1:]
    if t == "**":
        return any(_tokens_match(parts[i:], rest)
                   for i in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatch(parts[0], t) \
        and _tokens_match(parts[1:], rest)


def _glob_hits(base: Path, pattern: str) -> "list[Path]":
    """Files under `base` matching `pattern` (glob, `**` included).

    `**` needs its own walk: `Path.glob` cannot prune, and an unpruned
    `**` from a workspace root would sweep `.lake`/`.git`. The walk
    skips `_SKIP_DIRS` exactly as a directory walk does — `.lake` stays
    reachable by aiming the glob-free prefix inside `.lake/packages`,
    the same explicit-target grant as everywhere else."""
    toks = pattern.split("/")
    if "**" not in toks:
        return sorted(x for x in base.glob(pattern) if x.is_file())
    allow = _lake_grant(base.resolve()) is True
    aimed = set(base.resolve().parts)
    hits: "list[Path]" = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(
            d for d in dirs
            if (d not in _SKIP_DIRS or (allow and d == ".lake"))
            and (d not in _HEAVY_DIRS or d in aimed))
        try:
            rel = Path(root).relative_to(base).parts
        except ValueError:
            continue
        rel = tuple(x for x in rel if x != ".")
        hits += (Path(root) / f for f in files
                 if _tokens_match(rel + (f,), toks))
    return sorted(hits)


def _expand(spec: str, cwd: Path) -> "list[Path]":
    """A path or a glob, relative to the agent's own directories."""
    p = _resolve(spec, cwd)
    if any(ch in spec for ch in "*?["):
        base, pattern = _glob_split(p)
        hits = _glob_hits(base, pattern)
        own = _own_attempt_dir()
        if not hits and own is not None and not Path(spec).is_absolute():
            # Same containment as `_resolve`: this fallback is the same
            # attempt-dir door, and a glob was the one spelling that
            # skipped the check — `in: "../<other-pid>/*.lean"` served a
            # sibling attempt's files after the literal path was fixed
            # (acceptance pass, 2026-08-17).
            base2, pattern2 = _glob_split(own / spec)
            try:
                # The glob-free prefix, not the full spec: `resolve()`
                # on a name with glob characters is undefined ground on
                # Windows. The directory is what containment is about.
                base2.resolve().relative_to(own.resolve())
            except (ValueError, OSError):
                return hits
            hits = _glob_hits(base2, pattern2)
        return hits
    if p.is_dir():
        grant = _lake_grant(p.resolve())
        if isinstance(grant, str):
            return []  # grep surfaces the teaching via _lake_grant
        if _skipped(p, allow_lake=grant is True):
            return []  # a walk ROOTED under a skip dir stays walled
        return _walk_files(p, allow_lake=grant is True)
    return [p] if p.exists() else []


def _walk_files(base: Path, *, allow_lake: bool) -> "list[Path]":
    """Directory walk with the skip list AND the heavy-dir rule (see
    `_HEAVY_DIRS`); pruning happens during the walk, so a broad root
    never pays for the trees it will not use."""
    aimed = set(base.resolve().parts)
    out: "list[Path]" = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(
            d for d in dirs
            if (d not in _SKIP_DIRS or (allow_lake and d == ".lake"))
            and (d not in _HEAVY_DIRS or d in aimed))
        out += (Path(root) / f for f in files)
    return sorted(out)


def _skipped(p: Path, *, allow_lake: bool = False) -> bool:
    if allow_lake:
        return any(part in _SKIP_DIRS and part != ".lake"
                   for part in p.parts)
    return any(part in _SKIP_DIRS for part in p.parts)


def _lake_grant(base: Path) -> "bool | str":
    """A walk whose ROOT the agent explicitly aimed inside `.lake` is a
    deliberate targeted query, not an accidental 69GB tree-walk — the
    skip list stops the latter, and it was also stopping agents from
    grepping Mathlib SOURCE for the real name of a half-remembered
    lemma, which fed the loogle-guessing spirals (owner ruling
    2026-08-22: explicit paths override the skip). Sources only:
    `.lake/packages/...`; the 60GB of build artifacts stay walled.

    Returns True (granted), False (no .lake involved), or a teaching
    string (aimed at .lake but outside packages/)."""
    parts = base.parts
    if ".lake" not in parts:
        return False
    i = parts.index(".lake")
    if len(parts) > i + 1 and parts[i + 1] == "packages":
        return True
    return (".lake is searchable only under .lake/packages/ (library "
            "SOURCES — e.g. in: \".lake/packages/mathlib/Mathlib\"); "
            "build artifacts are not.")


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
    spawn's own two directories.

    2026-08-24, the same defect through a different door: under the
    shim the tools run in-process, so `cwd` is the SHIM's cwd — the
    repo root — and the old `rglob` walked every attempt from it
    (`.attempts/` sorts before `Problems/`, so a foreign spawn's
    TREE.md answered a presearch's bare read on both fleets). rglob
    also bypassed the heavy-dir prune the grep walker has — the
    28-minute-stall shape. The walk now prunes _SKIP_DIRS and
    _HEAVY_DIRS from every root; the agent's own attempts dir is
    still covered because it is its own root."""
    roots = [cwd]
    own = _own_attempt_dir()
    if own is not None:
        roots.append(own)
    for root in roots:
        hits: "list[Path]" = []
        try:
            for r, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs
                                 if d not in _SKIP_DIRS
                                 and d not in _HEAVY_DIRS)
                if name in files:
                    hits.append(Path(r) / name)
        except OSError:
            continue
        for cand in sorted(hits):
            if cand.is_file() and not _skipped(cand):
                return cand
    return None


def _nearest_existing(p: Path, cwd: "Path | None" = None) -> str:
    """What a wrong path costs should be nothing.

    Before this, a mistyped path cost a whole round-trip: the agent got
    "no such file" and spent its next turn on `ls` to find out what was
    actually there. Answer both at once."""
    if p.is_dir():
        # Reading a directory as a file used to answer with the PARENT
        # listing, so telling "empty dir" from "wrong path" cost an
        # extra probe (feedback, 2026-08-25). The path exists — list
        # its own contents.
        try:
            names = sorted(x.name + ("/" if x.is_dir() else "")
                           for x in p.iterdir())[:20]
        except OSError:
            names = []
        listing = ", ".join(names) if names else "(empty)"
        return f"that path IS a directory — it holds: {listing}"
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


# ------------------------------------------------------------- writes

def run_write(spec: str, content: str) -> str:
    """Write `content` to `spec`, inside THIS spawn's attempts dir only.

    Why a server-side write exists at all: codex's Windows sandbox makes
    a session's FIRST `apply_patch` block for the whole sandbox warm-up
    — measured 142.6s on 2026-08-17, growing day over day — and agents
    give up long before that, so decision.json never lands and the wake
    dies as `agent_no_output`. This write happens in the tools server's
    own process, outside that sandbox: immediate, every time.

    The write authority is the same one the envelope already exports —
    `_own_attempt_dir()` — and the target must stay inside it: absolute
    paths are accepted (the prompts hand agents absolute paths) but only
    into that directory; everything else is refused with the address
    that would work. The problem dir stays out deliberately: agent files
    landing there is the stale-stray class (#218)."""
    own = _own_attempt_dir()
    if own is None:
        return ("write_file: no attempts directory is declared here — "
                "this tool only works inside a framework spawn.")
    p = Path(spec)
    target = p if p.is_absolute() else own / spec
    try:
        rel = target.resolve().relative_to(own.resolve())
    except (ValueError, OSError):
        return (f"write_file: only your attempts directory is writable — "
                f"write this as {(own / p.name).as_posix()}")
    replaced = target.is_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"write_file: could not write {target.as_posix()}: {exc}"
    return (f"wrote {len(content)} chars to {(own / rel).as_posix()}"
            + (" (replaced the previous version)" if replaced else ""))


def read_own_file(spec: str) -> "tuple[str | None, str]":
    """(content, err) — read a file inside THIS spawn's attempts dir.

    Same resolution and authority as `run_write` (bare name or absolute
    path, both must land inside the spawn's own attempts dir). Exists
    for disk-is-authority validators (`validate_json(file=...)`): what
    gets validated must be the bytes actually being handed in, not a
    paste that survived tool-call escaping."""
    own = _own_attempt_dir()
    if own is None:
        return None, ("no attempts directory is declared here — "
                      "this works only inside a framework spawn")
    p = Path(spec)
    target = p if p.is_absolute() else own / spec
    try:
        target.resolve().relative_to(own.resolve())
    except (ValueError, OSError):
        return None, (f"only your attempts directory is readable this "
                      f"way — name it as {(own / p.name).as_posix()}")
    if not target.is_file():
        return None, f"no file at {target.as_posix()} — write it first"
    try:
        return target.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return None, f"could not read {target.as_posix()}: {exc}"


# ------------------------------------------------------------ queries

def _q_grep(q: dict, cwd: Path, deny) -> "list[str]":
    pattern = str(q.get("grep") or "")
    where = str(q.get("in") or ".")
    ctx = int(q.get("context") or 0)
    after = str(q.get("after") or "").strip()
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return [f"bad pattern: {exc}"]
    files = _expand(where, cwd)
    if not files:
        grant = _lake_grant(_resolve(where, cwd).resolve())
        if isinstance(grant, str):
            return [grant]
        return [f"nothing to search at {where!r}; "
                f"{_nearest_existing(cwd / where, cwd)}"
                f" (relative paths resolve against {cwd})"]
    # `after: "<file>:<line>"` resumes a capped search past its last
    # delivered hit — the old truncation note said only "narrow", which
    # names no reachable action when the query is already as narrow as
    # the reader can make it (2026-08-22 feedback cluster).
    skip_rel, skip_line = "", 0
    if after:
        m = re.fullmatch(r"(.*):(\d+)", after)
        skip_rel, skip_line = (m.group(1), int(m.group(2))) if m else (after, 0)
    resumed = not after
    # The scan STOPS as soon as it has `max`+1 hits or trips the scan
    # budget — the old shape read every file to the end and only then
    # truncated the output, which is how one broad grep held a CPU for
    # 28 minutes (2026-08-23). `after` makes stopping safe: the reader
    # can always continue with no overlap.
    want = max(1, min(int(q.get("max", DEFAULT_MAX)), MAX_MAX))
    t0 = time.monotonic()
    n_files = read_bytes = 0
    budget_hit = ""
    more = False
    #: last fully-scanned file — the zero-hit resume anchor: with no
    #: hit to anchor `after` on, the old note led with "no matches"
    #: and offered only "narrow", which agents read as a NEGATIVE
    #: RESULT and moved on with wrong conclusions (feedback x3,
    #: 2026-08-24).
    last_scanned: "tuple[str, int]" = ("", 0)
    blocks: "list[tuple[str, int, list[str]]]" = []  # (rel, line, lines)
    for f in files:
        if len(blocks) > want:
            more = True
            break
        if n_files >= _SCAN_MAX_FILES:
            budget_hit = f"{n_files} files"
            break
        if read_bytes >= _SCAN_MAX_BYTES:
            budget_hit = f"{read_bytes >> 20} MB read"
            break
        if time.monotonic() - t0 > _SCAN_MAX_SEC:
            budget_hit = f"{int(time.monotonic() - t0)}s"
            break
        root = _denied(f.resolve(), deny)
        if root is not None:
            continue
        rel = _rel(f, cwd)
        boundary = after and rel == skip_rel
        if not resumed and not boundary:
            continue
        resumed = True
        n_files += 1
        text = _read_text(f)
        read_bytes += len(text)
        lines = text.splitlines()
        last_scanned = (rel, len(lines))
        for i, line in enumerate(lines):
            if boundary and i + 1 <= skip_line:
                continue
            if not rx.search(line):
                continue
            if ctx:
                lo, hi = max(0, i - ctx), min(len(lines), i + ctx + 1)
                blk = [f"{rel}:{i + 1}:"] + [
                    f"  {n + 1:>5}  {lines[n]}" for n in range(lo, hi)]
            else:
                blk = [f"{rel}:{i + 1}: {line.strip()}"]
            blocks.append((rel, i + 1, blk))
            if len(blocks) > want:
                more = True
                break
        if more:
            break
    if after and not resumed:
        return [f"resume point {after!r} names a file outside this "
                f"search — re-run without `after`."]
    delivered = blocks[:want]
    hits = [ln for _r, _n, blk in delivered for ln in blk]
    if not hits:
        base_msg = (f"no more matches past {after}" if after
                    else "no matches")
        if budget_hit:
            # NOT a negative result — say so first, and hand the
            # resume anchor (last fully-scanned file) so continuing
            # the SAME broad search is a reachable action, not just
            # "narrow".
            if last_scanned[0]:
                return [
                    f"search UNFINISHED — scan budget hit "
                    f"({budget_hit}) with {base_msg} in the files "
                    f"scanned so far. This is NOT a negative result. "
                    f"Continue with no overlap: `after: "
                    f'"{last_scanned[0]}:{last_scanned[1]}"` (same '
                    f"query), or narrow `in` to a subdirectory or a "
                    f"glob."]
            return [base_msg + f" so far — scan budget hit "
                    f"({budget_hit}) before the search finished; "
                    f"narrow `in` to a subdirectory or a glob"]
        return [base_msg]
    notes: "list[str]" = []
    if more or budget_hit:
        rel_l, line_l, _b = delivered[-1]
        why = (f"scan budget hit ({budget_hit})" if budget_hit
               else f"{len(delivered)} delivered, more exist")
        notes.append(
            f"… {why}. Continue with no overlap: "
            f'`after: "{rel_l}:{line_l}"` (same query)'
            + (", or narrow `in` to a subdirectory or a glob."
               if budget_hit else "."))
    return hits + notes


def _last_grep_anchor(kept: "list[str]") -> str:
    """`file:line` of the last delivered hit, for the `after` handle."""
    for ln in reversed(kept):
        m = re.match(r"(.+):(\d+):", ln)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
    return ""


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


#: A raw answer is byte-faithful file content and carries NO decoration,
#: so anything that is NOT content (a refusal, a miss, an ambiguity)
#: must say so in-band — this prefix is how `run_queries` tells the two
#: apart and keeps the label on the non-content case. Without it, a
#: refusal shipped undecorated reads as file content and gets written
#: back verbatim.
RAW_REFUSAL = "raw read refused: "


def _strip_parenthetical(s: str) -> str:
    """`programme (rev 3, judge-passed)` -> `programme` — the dynamic
    annotation is presentation on the same name, dropped on BOTH sides
    so yesterday's `(rev 2)` still names today's section."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()


def _heading_key(s: str) -> str:
    """A requested section name, normalized the way readers type it.

    The outline prints `## Programme (rev 3)` and `sections` used to
    accept only the bare heading text — copy-pasting from the outline,
    the obvious workflow, failed (40+ self-reports). Leading heading
    markers and wrapping backticks are presentation, not identity."""
    return str(s).strip().strip("`").lstrip("#").strip().lower()


def _outline_roster(secs, spec: str, why: str) -> "list[str]":
    """A roster-sized file's map is the roster itself (CATALOG.md: 1,333
    headings, 30-60K chars), so it is never shipped whole. What ships is
    the way to NAME a slice — heading-prefix counts, short by
    construction — and the two questions a roster actually answers."""
    counts: "dict[str, int]" = {}
    for text, *_ in secs:
        tok = re.split(r"[_\s]", _heading_key(text), 1)[0][:24]
        counts[tok] = counts.get(tok, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    return [
        f'{why} Name what you want: `outline_prefix: "<prefix>"` (case-'
        f"insensitive, up to {OUTLINE_MATCH_MAX} hits) or `outline_grep: "
        f'"<regex>"`; a live goal: {{"decl": "<slug or gNNNN>"}}; one '
        f'entry\'s text: {{"grep": "<name>", "in": {spec!r}}}.',
        f"heading prefixes (token before the first `_`; {len(counts)} "
        f"distinct, top {len(top)}): "
        + ", ".join(f"{k} ({n})" for k, n in top)]


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

    `raw: true` (2026-08-18) returns the content UNDECORATED — no line
    numbers, no section banners — for round-tripping into `write_file`
    / `validate_json` / `validate_file`. The decorated default was the
    slice's largest feedback cluster (57 entries): every write-back
    required hand-stripping the `NNNNN  ` prefixes, and one agent's
    full-overwrite pasted the presentation header into `proposal.md`
    and lost content.
    """
    spec = str(q.get("read") or "")
    p = _resolve(spec, cwd)
    raw_flag = bool(q.get("raw"))
    root = _denied(p.resolve(), deny)
    if root is not None:
        msg = (f"{p} is operator-private (under {root}) — Context.md, "
               f"BRIEF.md carry what you are meant to know")
        return [RAW_REFUSAL + msg] if raw_flag else [msg]
    if not p.is_file():
        msg = f"no file at {p}; {_nearest_existing(p, cwd)}"
        return [RAW_REFUSAL + msg] if raw_flag else [msg]
    lines = _read_text(p).splitlines()
    secs = _sections(lines)
    raw = bool(q.get("raw"))

    def _render(a: int, b: int) -> "list[str]":
        if raw:
            return lines[max(1, a) - 1:min(len(lines), b)]
        return _numbered(lines, a, b)

    if q.get("outline"):
        if not secs:
            return [f"{len(lines)} lines, no markdown headings — this file "
                    f"has no sections. Read it whole, or a window with "
                    f'`lines: "1-200"`.']
        pre = _heading_key(q.get("outline_prefix") or "")
        pat = str(q.get("outline_grep") or "")
        head = f"{len(secs)} sections, {len(lines)} lines"
        shown = secs
        if pre or pat:
            try:
                rx = re.compile(pat, re.I)
            except re.error as exc:
                return [f"bad `outline_grep` pattern: {exc}"]
            shown = [s for s in secs if _heading_key(s[0]).startswith(pre)
                     and rx.search(s[0])]
            sel = " and ".join(x for x in (pre and f"prefix {pre!r}",
                                           pat and f"grep {pat!r}") if x)
            if len(shown) > OUTLINE_MATCH_MAX:
                return [f"{len(shown)} of {len(secs)} headings match {sel} "
                        f"— more than the {OUTLINE_MATCH_MAX} an outline "
                        f"lists; narrow `outline_prefix` / `outline_grep`."]
            if not shown:
                return _outline_roster(secs, spec, f"no heading matches "
                                       f"{sel} among {len(secs)} sections.")
            head += f", {len(shown)} match"
        elif len(secs) > OUTLINE_INLINE_MAX:
            return _outline_roster(
                secs, spec, f"{head} — more than the {OUTLINE_INLINE_MAX} an "
                f"outline lists whole; this file's map IS the roster.")
        out = [head + ":"]
        for text, level, a, b in shown:
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
            by_name.setdefault(_heading_key(text), []).append((text, a, b))
        chosen: "list[str]" = []
        missing: "list[str]" = []
        for name in names:
            key = _heading_key(name)
            hits = by_name.get(key)
            matched_by = ""
            if hits is None and key:
                # Headings carry dynamic parenthetical suffixes
                # (`Programme (rev 3, judge-passed)`) the reader cannot
                # know in advance; the name with the suffix dropped is
                # the SAME name, not a fuzzy neighbour. Matching stays
                # exact on that stripped key ("Programm" still refuses)
                # and the full heading is disclosed in the banner.
                bare = _strip_parenthetical(key)
                cands = [h for k, hs in by_name.items()
                         if _strip_parenthetical(k) == bare for h in hs]
                if len(cands) == 1:
                    hits = cands
                    matched_by = f"  [matched {cands[0][0]!r}]"
            if hits is None:
                missing.append(name)
                continue
            text, a, b = hits[0]
            if raw and (len(hits) > 1 or matched_by):
                # raw is a byte-faithful round-trip surface: an answer
                # that needs a disclosure note cannot be pure content.
                return [RAW_REFUSAL + (
                    f"section {name!r} matched "
                    + (f"{len(hits)} headings" if len(hits) > 1
                       else f"{text!r} only via its suffix")
                    + " — raw carries no disclosure notes, so read it "
                      "by exact heading or `lines`.")]
            if not raw:
                chosen.append(f"── {text}  (lines {a}-{b}){matched_by}")
            chosen += _render(a, b)
            if not raw and all(not lines[n - 1].strip()
                               for n in range(a + 1, b + 1)):
                chosen.append("(this section is empty — the heading "
                              "exists but has no content yet)")
            if len(hits) > 1 and not raw:
                where = ", ".join(f"lines {a2}-{b2}"
                                  for _t, a2, b2 in hits[1:])
                chosen.append(
                    f"note: {len(hits)} sections share this heading — "
                    f"this is the first; the other"
                    f"{'s are' if len(hits) > 2 else ' is'} at {where} "
                    f"(read one with `lines`).")
        if missing:
            # No fuzzy ANSWERING: a near-miss that silently answers with
            # the wrong section is worse than a refusal (unique-prefix
            # above is disclosed, not silent). And NO roster (owner
            # ruling 2026-08-15): `outline` already IS the roster — on
            # the 383-section CATALOG.md the inlined listing was itself
            # a 12KB cap-hit. But a bounded HINT is not a roster: name
            # the closest headings so the retry is one call, not two.
            close = []
            for name in missing:
                k = _heading_key(name)
                cands = [hs[0][0] for key2, hs in by_name.items()
                         if k and (k in key2 or key2 in k)][:3]
                if cands:
                    close.append(f"{name!r} — close: "
                                 + ", ".join(map(repr, cands)))
            miss_note = (
                f"no section named {', '.join(map(repr, missing))} in "
                f"this file — it has {len(secs)} section"
                f"{'' if len(secs) == 1 else 's'}; `outline: true` "
                f"lists them." + ("".join(f"\n  {c}" for c in close)))
            if raw:
                return [RAW_REFUSAL + miss_note]
            chosen.append(miss_note)
        return chosen or [f"{len(lines)} lines, no sections matched"]

    rng = str(q.get("lines") or "").strip()
    if rng:
        lo, _, hi = rng.partition("-")
        try:
            a = int(lo) if lo else 1
            b = int(hi) if hi else len(lines)
        except ValueError:
            msg = f"bad `lines` {rng!r} — use \"380-420\", \"-40\" or \"40-\""
            return [RAW_REFUSAL + msg] if raw else [msg]
        return _render(a, b)
    # Whole file. The byte budget in `run_queries` bounds it and says
    # where to resume; an explicit `max` still caps by line for a caller
    # that wants a peek.
    if q.get("max") is not None:
        kept, note = _cap(_render(1, len(lines)), q["max"],
                          ", or name a section with `sections`")
        return kept + ([note] if note else [])
    return _render(1, len(lines))


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
        return [f"no directory at {base}; {_nearest_existing(base)}"
                f" (relative paths resolve against {cwd})"]
    grant = _lake_grant(base)
    if isinstance(grant, str):
        return [grant]
    matched = sorted(base.rglob(pattern))
    out = [_rel(p, cwd) for p in matched
           if not _skipped(p, allow_lake=grant)
           and _denied(p, deny) is None]
    if not out:
        # A bare "no matches" conflated three different worlds and the
        # reader could not tell which one it was in (adversaries judged
        # retargeting disputes "without the very files the rules call
        # decisive" — feedback ×28, 2026-08-25): scope-filtered is a
        # boundary, not absence; a clean miss names what IS there.
        if matched:
            return [f"{len(matched)} entr"
                    f"{'y matches' if len(matched) == 1 else 'ies match'}"
                    f" under {base} but none are within your read scope"
                    f" (framework-internal or fenced) — a scope"
                    f" boundary, NOT an empty directory"]
        try:
            names = sorted(x.name + ("/" if x.is_dir() else "")
                           for x in base.iterdir())[:20]
        except OSError:
            names = []
        holds = ", ".join(names) if names else "(empty directory)"
        return [f"no matches for {pattern!r} — {base} exists and"
                f" holds: {holds}"]
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
    # `gNNNN` is how TREE.md / Context.md label a goal — its row id, an
    # exact address; a slug is exact first, then substring: an agent
    # that typed the whole name wants THAT one, and burying it among six
    # near-misses is the same "answer is in there somewhere" failure the
    # CATALOG had.
    gid = re.fullmatch(r"g(\d+)", name)
    try:
        rows = conn.execute(
            "SELECT slug, lean_path, statement, status, problem, "
            "alias_target_id FROM goals "
            + ("WHERE id = ?" if gid else
               "WHERE slug = ? OR slug LIKE ? "
               "ORDER BY (slug = ?) DESC, slug LIMIT 6"),
            (int(gid.group(1)),) if gid else (name, f"%{name}%", name)
        ).fetchall()
        # An alias row's own file is `def slug := @sNNN` — truthful and
        # useless (90 self-reports: "shows the full statement for
        # unproved goals but only the alias for proved ones"). The
        # framework KNOWS the target; showing the pointer instead of
        # what it points at is the flattening family. Resolve it here,
        # disclosed, one hop at a time up to a short chain.
        alias_of: "dict[str, tuple[str, str, str, str]]" = {}
        for r in rows:
            tid, seen = r["alias_target_id"], 0
            target = None
            while tid is not None and seen < 4:
                target = conn.execute(
                    "SELECT slug, lean_path, statement, status, "
                    "alias_target_id FROM goals WHERE id = ?",
                    (tid,)).fetchone()
                if target is None:
                    break
                tid, seen = target["alias_target_id"], seen + 1
            if target is not None:
                alias_of[str(r["slug"])] = (
                    str(target["slug"]), target["lean_path"],
                    target["statement"], str(target["status"]))
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
        slug, lp, stmt = str(r["slug"]), r["lean_path"], r["statement"]
        target = alias_of.get(slug)
        if target is not None:
            tslug, lp, stmt, tstatus = target
            out.append(f"    alias of {tslug}  [{tstatus}] — "
                       f"showing the target's signature:")
            slug = tslug
        try:
            sig = _ctx.goal_display_signature(ws, slug, lp, stmt,
                                              flatten=False)
        except Exception:  # noqa: BLE001 — a missing stub falls back
            sig = stmt or ""
        if target is None:
            # Second alias shape (~29 reports, 2026-08-24): a proved
            # goal's file can be a WRAPPER `def slug ... := @…sNNN`
            # with no `alias_target_id` row — the promote path writes
            # the pointer without the DB marker. The framework knows
            # where the target lives (`_strategy_sNNN.lean` beside the
            # wrapper), so follow the pointer here, disclosed, instead
            # of shipping a line the reader must chase by hand.
            m = re.search(r":=\s*@[\w'.]*?\b(s\d+)\b", sig or "")
            if m:
                stok = m.group(1)
                sfile = (ws / lp).parent / f"_strategy_{stok}.lean"
                try:
                    stext = _read_text(sfile)
                except OSError:
                    stext = ""
                if stext.strip():
                    srel = sfile.relative_to(ws).as_posix()
                    dm = re.search(
                        r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
                        r"(?:noncomputable[ \t]+|private[ \t]+)*"
                        r"(?:theorem|def|instance)[ \t]+" + stok + r"\b",
                        stext)
                    body = stext[dm.start():] if dm else stext
                    out.append(f"    wrapper of @{stok} — showing "
                               f"{srel}'s declaration:")
                    sig, lp = body, srel
        sig_lines = (sig or "").strip().splitlines()
        out += [f"    {ln}" for ln in sig_lines[:16]]
        # Truncation is a VIEW, never a loss (framework rule): the old
        # silent `[:16]` cut is the same "stopped mid-definition" failure
        # the grep path already discloses — ~26 agent reports read a
        # clipped signature as the WHOLE declaration. Name the count and
        # the reachable action: the file path is already on the line
        # above, so `read` + `lines` picks up exactly where this left off.
        if len(sig_lines) > 16:
            out.append(
                f"    … {len(sig_lines) - 16} more line(s) elided — "
                f'read the rest: {{"read": {lp!r}, "lines": "17-"}}')
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
        if "grep" in q:
            anchor = _last_grep_anchor(kept.splitlines())
            if anchor:
                return (f'Continue with no overlap: resend the same '
                        f'grep with `after: "{anchor}"`.')
        return "Narrow the query."
    if "read" in q:
        return (f'Continue from line {last + 1}: '
                f'{{"read": {str(q["read"])!r}, "lines": "{last + 1}-"}} '
                f'— or name a section with `sections` / map it with '
                f'`outline: true`.')
    return f"Continue from line {last + 1} with `lines`."


def _big_section_refusal(q: dict, size: int, budget: int) -> str:
    """A section past 2x the budget is a ROSTER — uniform entries the
    reader wants ONE of, not a document to page through. Name the ways
    a roster is actually used (grep by name inside the file, `decl`
    for the live record, a `lines` window) instead of delivering the
    first twelfth and a dozen resume hops."""
    secs = ", ".join(str(s) for s in (q.get("sections") or []))
    rounds = (size + budget - 1) // budget
    return (f"section(s) [{secs}] total {size:,} chars — {rounds}x the "
            f"{budget:,}-char reply budget. A section this size is a "
            f"roster: grep it for the entry you want "
            f'({{"grep": "<name>", "in": {str(q.get("read"))!r}}}), ask '
            f'the live record ({{"decl": "<slug>"}}), or open an exact '
            f'window with `lines`. Paging the whole section would cost '
            f"~{rounds} calls and is almost never the question.")


#: A refusal may inline the outline only when the outline itself is
#: small — the 2026-08-15 roster ruling stands (on the 654-section
#: catalog the inlined listing was itself a 12KB cap-hit).
_REFUSAL_OUTLINE_CHARS = 2_000


def _whole_read_refusal(q: dict, here: Path, deny, size: int,
                        budget: int) -> str:
    """A whole-file read that cannot fit one reply is REFUSED with the
    way in — never silently clipped (owner call 2026-08-18).

    The clipped prefix was the trap: this slice's 1,011 truncations
    were 84% whole reads of the four big framework documents, and a
    12KB prefix reads exactly like the whole file to an agent that
    does not scroll to the truncation line. A refusal that names the
    precise asks (sections / lines / grep) turns the same round trip
    into a map instead of a misleading half-answer."""
    head = (f"whole file is {size:,} chars — more than one reply's "
            f"{budget:,}-char budget, so a whole read could only ever "
            f"deliver a silent prefix. Ask precisely instead:")
    try:
        outline = _q_read({"read": q.get("read"), "outline": True},
                          here, deny)
    except Exception:  # noqa: BLE001 — the refusal must never raise
        outline = []
    o_text = "\n".join(outline)
    if o_text and "no markdown headings" in o_text:
        first = o_text.splitlines()[0].split("—")[0].strip()
        return (head + f"\n{first} and no headings — take windows with "
                f'`lines: "1-200"`, or `grep` it by keyword.')
    if o_text and len(o_text) <= _REFUSAL_OUTLINE_CHARS:
        return head + "\n" + o_text
    first = o_text.splitlines()[0] if o_text else "many sections"
    return (head + f"\n{first} `outline: true` maps them (`outline_prefix` "
            f"narrows a big map); then `sections: [...]`, or `grep` it by "
            f"slug/keyword.")


def _deferral_note(deferred: "list[tuple[int, object]]", reason: str) -> str:
    """The way back for whole queries this reply could not carry:
    every one named, in the vocabulary the count limit already uses.

    It named them with `sorted(d)` until 2026-08-16 — the dict's KEYS —
    so a deferred `{"read": "charter.md", "sections": ["Proof"]}` came
    back as `[11] ['read', 'sections']` and "send these in a second
    call" was unfollowable: the reader had to reconstruct which file it
    had even asked about. Three agents reported it within an hour of
    the deferral shipping. Echo the query itself; it is what they
    resend.

    Echoing it made the note's length a function of the QUERY's length,
    and a batch carrying long grep patterns then produced a note bigger
    than the reply it was appended to — the very overflow it reports
    (measured 2026-08-16: a 41,600-char pattern gave a 41,747-char note
    against a 30,000-char budget, and starved the delivered answers from
    9 to 2). So each echo is itself bounded: enough to identify the
    query, never enough to become the payload. A truncated echo is
    marked, because a silently shortened path is one the reader would
    resend wrong."""
    def _echo(d: object) -> str:
        # Every query, not just the dict-shaped ones: a bare string or a
        # list is an accepted (if mistaken) query, and `f"{d}"` printed
        # it as a Python repr — `['read', 'b.md']`, byte-identical to
        # the shape this note exists to stop producing.
        s = json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)
        if len(s) <= _ECHO_CHARS:
            return s
        return s[:_ECHO_CHARS] + f"…(+{len(s) - _ECHO_CHARS} chars)"

    # Echoes up to the note's own budget; the tail collapses to an index
    # range. Per-echo bounding alone left the note proportional to the
    # deferred COUNT, and a 400-query call overflowed the very budget
    # the note reports. Indices are enough for the tail: they are the
    # positions in the list the caller itself sent.
    parts: "list[str]" = []
    used = 0
    tail: "list[int]" = []
    for i, d in deferred:
        if tail:
            tail.append(i)
            continue
        piece = f"[{i}] {_echo(d)}"
        if parts and used + 2 + len(piece) > _NOTE_CHARS:
            tail.append(i)
            continue
        parts.append(piece)
        used += (2 if len(parts) > 1 else 0) + len(piece)
    listed = "; ".join(parts)
    if tail:
        listed += (f"; … and {len(tail)} more — queries [{tail[0]}]–"
                   f"[{tail[-1]}] in the order you sent them")
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
    deferred by name — an answer that would overflow it waits for a
    second call, and later answers that still fit are delivered (owner
    ruling 2026-08-29: one oversize question must not hold ten small
    ones). Delivered answers keep their full per-query budget; the FIRST
    query is always answered even alone over the ceiling. None = a
    backend nobody has measured; no ceiling is applied
    (`llm/capabilities.mcp_result_delivery_chars` owns the numbers).
    """
    if cwd is None:
        # The shim runs tools in-process: ITS cwd is the repo root,
        # not the spawn's problem dir. The request-local context
        # (URL `/c/` segment) carries the real one; standalone MCP
        # servers keep the process-cwd route (they inherit the
        # agent's `-C problem_dir`).
        from ..llm.spawn_guard import TOOL_CWD_CONTEXT
        cwd = TOOL_CWD_CONTEXT.get()
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
        if not isinstance(q, dict):
            block = f"[{n}] not a query object: {q!r}"
        else:
            for key, fn in _KINDS:
                if key in q:
                    where = f" in {q['in']}" if q.get("in") else ""
                    head = f"[{n}] {key} {q[key]!r}{where}"
                    raw_read = key == "read" and bool(q.get("raw"))
                    if raw_read and len(queries) > 1:
                        # A raw answer is undecorated file bytes; it
                        # cannot share a reply with labelled answers
                        # without regrowing the very delimiters `raw`
                        # exists to strip (992-byte overwrite incident,
                        # 2026-08-19).
                        block = (head + "\nraw read must be the only "
                                 "query in the call — its answer is "
                                 "byte-faithful content with no labels. "
                                 "Send it alone.")
                        break
                    try:
                        body = fn(q, here, deny)
                    except Exception as exc:  # noqa: BLE001 — one bad query
                        body = [f"failed: {type(exc).__name__}: {exc}"]
                    text = "\n".join(body)
                    if raw_read:
                        # Byte-faithful or refused — never decorated,
                        # never clipped (a truncated round-trip corrupts
                        # the file on write-back).
                        if text.startswith(RAW_REFUSAL):
                            block = head + "\n" + text[len(RAW_REFUSAL):]
                        elif len(text) > per_query_chars:
                            block = (head + f"\nraw read is "
                                     f"{len(text):,} chars — over the "
                                     f"{per_query_chars:,}-char reply "
                                     f"budget, and raw never truncates. "
                                     f"Read a `sections`/`lines` slice "
                                     f"(still raw), or drop `raw` to "
                                     f"browse with the map.")
                        else:
                            block = text
                        break
                    if len(text) > per_query_chars:
                        if (key == "read" and not any(
                                k in q for k in ("sections", "lines",
                                                 "outline", "max"))):
                            # Whole-file read that cannot fit: refuse
                            # with the map, never clip (2026-08-18).
                            text = _whole_read_refusal(
                                q, here, deny, len(text), per_query_chars)
                        elif (key == "read" and q.get("sections")
                              and len(text) > 2 * per_query_chars):
                            # A section MORE than twice the budget is a
                            # roster, not a reading (user backlog item
                            # c, 2026-08-26: TREE.md's `## Lemmas` on a
                            # mature problem is 141KB — paging it costs
                            # ~12 calls and teaches nothing). Refuse
                            # with the ways a roster is actually used.
                            # Size-tiered on purpose: no filename
                            # sniffing, so it covers every future giant.
                            text = _big_section_refusal(
                                q, len(text), per_query_chars)
                        else:
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
        # Sorted: a deferral can sit between two delivered answers now,
        # and the note's collapsed tail speaks in send order.
        deferred = sorted(budget_deferred, key=lambda t: t[0]) + count_deferred
        if budget_deferred:
            note = _deferral_note(
                deferred, f"their answers would not fit this reply's "
                          f"{delivery_chars:,}-char budget beside the ones "
                          f"delivered.")
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
        budget_deferred.append(srcs.pop())
        joined -= len(blocks.pop()) + 2
    return "\n\n".join(blocks + ([note] if note else []))
