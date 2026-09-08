"""What changed under an agent's feet while it was working.

A spawn's system prompt and Context are written once, cached, and never
rewritten — that is what makes a long turn affordable. So everything the
framework learns AFTER the prompt was built has no way in: the owner
amends the problem's charter at 16:40, a theory document the agent is
about to re-derive is accepted at 16:44, a brick it is about to re-prove
lands in CATALOG.md — and the agent works on, for another forty minutes,
against a world that has moved.

The one channel that is still open is a TOOL RESULT. Every tool call
already returns text the agent reads, so this module appends a short
notice to the end of that text: what changed, once each, and where to
read it. The prefix stays byte-identical and cacheable; the news rides
the part that was going to be written fresh anyway.

WHAT COUNTS AS NEWS (v1, a fixed list — drafts and in-flight things are
deliberately absent, because a half-written document is not a fact and
an agent told about one would act on it):

  * the owner's own surfaces on this problem — `OWNER_PROBLEM_FILES`
    below, and every file under the Project's `_docs/user/**`;
  * a theory document reaching `accepted`;
  * a goal of this problem reaching `proved`.

`Root.lean` is NOT watched, and its absence is a decision rather than an
oversight. It is an owner file (`state/intent.USER_INTENT_FILES`, and
the spawn deny list names it beside `problem.json` / `Defs.lean`), but
the framework writes it too: Verify's promotion to `def main := @s<N>`
and its rollback are machine writes to a user file, recorded in
`user_file_history` under `source='framework'` precisely because they
are indistinguishable from an owner edit at the byte level. A content
hash cannot tell them apart, and "the owner edited the root statement"
is the most alarming line this notice can print — so it must never be
printed by a brick landing. That same event already arrives here as
`brick proved`.

DETECTION is a snapshot plus a diff. The snapshot is taken when the
spawn starts (the stdio tools server is one process per spawn; the
gateway is long-lived, so its baseline is taken at `/register`, which is
per-spawn), and each tool call diffs against it. What has been reported
is remembered, so a change is announced once — but the state kept per
file is its CONTENT HASH, not a "reported" flag, so a file edited twice
is announced twice. That is the honest behaviour: the second edit is a
second thing the agent has not seen.

Cost is bounded on both axes. Files are `stat`ed first and hashed only
when mtime/size moved; the database is opened only when its own (or its
WAL's) mtime moved, read-only, with both queries filtered by problem.

NOTHING HERE MAY RAISE. It runs on the return path of every tool on both
servers, and a notice that breaks a tool call is worse than no notice:
the agent would lose the answer it asked for over news it did not.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

#: The trailer's fixed text. Exact strings on purpose — an agent reads
#: this, and the last line is an instruction, not a summary.
HEADING = "## Changed since you started"
FOOTER = 'Read what bears on your task: inspect [{"read":"<path>"}].'

#: Lines one trailer may carry. A burst (a Strategist landing eleven
#: bricks in a minute) would otherwise bury the tool's own answer; the
#: overflow waits and rides the next call.
MAX_LINES = 12

#: The owner's authored surfaces inside a problem directory. These are
#: the three the spawn deny list fences agents out of
#: (`llm/claude_cli`: `Write(**/problem.json)` &c.) minus `Root.lean` —
#: see the module docstring for why that one is absent. `problem.json`
#: is the durable mirror of the DB-resident charter/word/settings
#: (`state/intent.write_seed` refreshes it after every sanctioned
#: change), so a charter edit made through the console or
#: `asterism charter` lands here as a file change.
OWNER_PROBLEM_FILES: "tuple[str, ...]" = (
    "problem.json", "charter.md", "Defs.lean")

#: Ceiling on the `_docs/user/**` walk. A document shelf is a person's
#: writing, not a tree; a runaway one must not turn every tool call into
#: a directory crawl.
MAX_USER_DOCS = 400

#: Hash read size. Streamed, so a pdf on the shelf costs bounded memory.
_CHUNK = 1 << 20


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(_CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _hhmmz(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%H:%MZ")


def _problem_dir(workspace: Path, problem: str) -> Path:
    """`Problems/<a>/<b>` for the dotted slug `a.b`.

    The rule is `state/db/paths.problem_dir`'s; it is spelled out here
    rather than imported because this module is loaded by the stdio
    tools server, which keeps the framework's DB layer out of its
    process on purpose."""
    return Path(workspace).joinpath("Problems", *problem.split("."))


def _user_docs_dir(workspace: Path, problem: str) -> "Path | None":
    """`Problems/<project>/_docs/user` — the person's shelf on the
    Project this problem belongs to (`llm/envelope.project_docs_dir`)."""
    try:
        from ..llm.envelope import project_docs_dir
        root = project_docs_dir(_problem_dir(workspace, problem))
    except Exception:  # noqa: BLE001 — a missing grant is not a failure
        return None
    return None if root is None else root / "user"


#: The catalog's name in a spawn's attempts dir. Named here rather than
#: imported from `agent/context` for the reason the whole module keeps
#: its distance from the framework's own layers: this file is loaded by
#: the stdio tools server, which does not carry them.
CATALOG_COMPANION = "CATALOG.md"


#: The stamp `agent/context.write_catalog_companion` puts in every
#: catalog it writes: `_Snapshot taken 2026-09-08 13:12 UTC. …_`. It is
#: the only thing on disk that says WHEN the file's contents were true.
_CATALOG_STAMP_RE = re.compile(
    r"_Snapshot taken (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC")
#: How far into the file that stamp can be. It is written in the
#: preamble, before the first entry, so a small read settles it — and a
#: catalog is a roster (1,333 sections, 30-60K) that this module must
#: never read whole on a tool return path.
_CATALOG_HEAD_BYTES = 4096


def _catalog_stamp(path: Path) -> "datetime | None":
    """When the catalog beside the reader was rendered, or None when the
    file carries no stamp we can read.

    Minute resolution, and the stamp is the FLOOR of the write (the
    writer formats `%H:%M`), so `stamp >= proved` is a sound test for
    "this file was written after that brick landed" — it can call a
    fresh catalog stale, never a stale one fresh. That asymmetry is the
    one to keep: a wrong "stale" costs a read of the proof file, which
    the same line names; a wrong "fresh" is the defect this exists to
    close."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(_CATALOG_HEAD_BYTES)
    except OSError:
        return None
    m = _CATALOG_STAMP_RE.search(head)
    if m is None:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _proved_at(value: "str | None") -> "datetime | None":
    """`goals.updated_at` (an ISO-8601 UTC instant — `db.now`) as a
    datetime. The row was just seen to be `proved`, so its last update
    IS when it landed."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        out = datetime.fromisoformat(text)
    except ValueError:
        return None
    return out if out.tzinfo is not None else out.replace(tzinfo=timezone.utc)


def _brick_line(slug: str, lean_path: str, catalog: "Path | None",
                catalog_stamp: "datetime | None" = None,
                proved_at: "datetime | None" = None) -> str:
    """One `brick proved:` line, in the two spellings the reader can act
    on — and no third one it cannot.

    The name is the goal's SLUG, because that is the only string
    `inspect({"decl": ...})` resolves: `knowledge/decl_answer.answer`
    matches `goals.slug` (exact first, then substring), scoped to the
    caller's problem. This used to print the proof file's STEM instead
    — `L_<slug>` — which resolves to nothing at all: the `L_` prefix is
    a filename convention and is not in the column the lookup reads. A
    root's slug (`main`) is already the name its wrapper declares, so
    the two cases need no branch.

    The pointer is the goal's own `lean_path`, workspace-relative, which
    is the spelling `inspect({"read": ...})` resolves for every seat
    (`knowledge/workspace_query._resolve` tries the workspace root) —
    and a file that exists, unlike the CATALOG the line used to name
    unconditionally. Eight Theorists on 2026-09-07 were sent to a
    `CATALOG.md` that a fresh pure-NL problem never writes (nothing
    proved and no alive goals = no companion) and to a declaration name
    the record has never held; both halves of that line were
    unreachable. The catalog is named only when one is actually beside
    the reader — see `ChangeNotice.__init__`'s `catalog_dir`.

    And only when that catalog is NEWER than this brick. Existence was
    the wrong question: `CATALOG.md` is rewritten on context-render
    paths (per wake), not when a brick lands, so a file sitting beside a
    long-running spawn routinely predates the news this very line is
    announcing. "(also in `CATALOG.md`)" then sent the reader to a
    catalog that does not contain the brick — one of them quoted its
    `(0 entries)` header back as evidence the brick had not landed
    (2026-09-08 field reading). A pointer is only worth printing when
    the thing pointed at has the answer; when it does not, the line says
    so and the proof file beside it is the address that does."""
    name = str(slug or "").strip() or Path(str(lean_path or "")).stem or "?"
    rel = str(lean_path or "").replace("\\", "/").strip()
    out = f"- brick proved: `{name}`"
    if rel:
        out += f" — `{rel}`"
    if catalog is None:
        return out
    if catalog_stamp is None:
        return out + (" (CATALOG.md carries no snapshot stamp — read the "
                      "proof file)")
    if proved_at is None or catalog_stamp < proved_at:
        return out + " (CATALOG.md predates this brick — read the proof file)"
    return out + f" (also in `{catalog.as_posix()}`)"


class ChangeNotice:
    """One spawn's view of what has moved since it started.

    Construct it when the spawn starts: `__init__` takes the baseline
    and reports nothing. Every later `trailer()` returns the notice for
    what has changed since the previous call, or `""`.
    """

    def __init__(self, workspace: "Path | str | None", problem: "str | None",
                 *, db_path: "Path | str | None" = None,
                 catalog_dir: "Path | str | None" = None) -> None:
        self.workspace = Path(workspace) if workspace else None
        self.problem = (problem or "").strip() or None
        self.db_path = (Path(db_path) if db_path is not None
                        else (self.workspace / "asterism.db"
                              if self.workspace else None))
        # Where THIS spawn's `CATALOG.md` would be, when the caller
        # knows — the attempts dir. Absent for a caller that does not
        # (the gateway serves many spawns and holds none of their
        # attempt dirs), and then no brick line names a catalog: a
        # pointer nobody can check is the failure this parameter exists
        # to end, not one to spread to a second server.
        self.catalog_dir = Path(catalog_dir) if catalog_dir else None
        self._pdir = (_problem_dir(self.workspace, self.problem)
                      if self.workspace and self.problem else None)
        self._docs_dir = (_user_docs_dir(self.workspace, self.problem)
                          if self.workspace and self.problem else None)
        # rel-path -> ((mtime_ns, size), sha256). The sha is what a
        # change is measured against; the stat pair is only there to
        # skip the read.
        self._files: "dict[str, tuple[tuple[int, int], str]]" = {}
        self._accepted: "set[int]" = set()
        self._proved: "set[int]" = set()
        self._db_stamp: "tuple | None" = None
        self._pending: "list[str]" = []
        self._lock = threading.Lock()
        # Baseline. `_primed` False = collect state, report nothing.
        self._primed = False
        try:
            self._file_lines()
            self._db_lines()
        except Exception:  # noqa: BLE001 — see the module docstring
            pass
        self._primed = True

    # ---------------------------------------------------------- public

    def trailer(self) -> str:
        """The notice to append to a tool result, or `""`."""
        try:
            with self._lock:
                queued = self._pending + self._file_lines() + self._db_lines()
                if not queued:
                    return ""
                self._pending = queued[MAX_LINES:]
                shown = queued[:MAX_LINES]
        except Exception:  # noqa: BLE001 — see the module docstring
            return ""
        return "\n\n" + HEADING + "\n" + "\n".join(shown) + "\n" + FOOTER

    # ----------------------------------------------------------- files

    def _watched(self) -> "list[Path]":
        out: "list[Path]" = []
        if self._pdir is not None:
            out += [self._pdir / name for name in OWNER_PROBLEM_FILES]
        docs = self._docs_dir
        if docs is None or not docs.is_dir():
            return out
        seen = 0
        for dirpath, dirnames, filenames in os.walk(docs, followlinks=False):
            dirnames.sort()
            for name in sorted(filenames):
                out.append(Path(dirpath) / name)
                seen += 1
                if seen >= MAX_USER_DOCS:
                    return out
        return out

    def _rel(self, path: Path) -> str:
        """The path as `inspect` accepts it.

        Workspace-relative, and that spelling is load-bearing:
        `knowledge/workspace_query._resolve` tries the spawn's cwd (its
        problem dir), then the WORKSPACE ROOT, then its attempts dir —
        so `Problems/<project>/_docs/user/note.md` resolves for every
        seat, including the ones whose cwd is a projection under no
        problem at all. A shelf-relative `_docs/user/note.md` resolves
        for none of them.
        """
        if self.workspace is not None:
            try:
                return path.relative_to(self.workspace).as_posix()
            except ValueError:
                pass
        return path.as_posix()

    def _file_lines(self) -> "list[str]":
        lines: "list[str]" = []
        current: "dict[str, tuple[tuple[int, int], str]]" = {}
        for path in self._watched():
            try:
                st = path.stat()
            except OSError:
                continue  # absent, or gone since the last look
            rel = self._rel(path)
            stamp = (st.st_mtime_ns, st.st_size)
            before = self._files.get(rel)
            if before is not None and before[0] == stamp:
                current[rel] = before        # not touched — no read
                continue
            try:
                sha = _sha(path)
            except OSError:
                continue
            current[rel] = (stamp, sha)
            if before is not None and before[1] == sha:
                continue                      # touched, same bytes
            if self._primed:
                lines.append(f"- owner edited `{rel}` ({_hhmmz(st.st_mtime)})")
        self._files = current
        return lines

    # -------------------------------------------------------------- db

    def _db_stamp_now(self) -> tuple:
        """The DB's own mtime, WAL included. Every commit moves one of
        them, so an unchanged pair means there is nothing to ask."""
        out: "list[tuple[int, int] | None]" = []
        for p in (self.db_path, Path(str(self.db_path) + "-wal")):
            try:
                st = p.stat()
                out.append((st.st_mtime_ns, st.st_size))
            except OSError:
                out.append(None)
        return tuple(out)

    def _db_lines(self) -> "list[str]":
        if self.db_path is None or self.problem is None:
            return []
        stamp = self._db_stamp_now()
        if stamp == self._db_stamp:
            return []
        self._db_stamp = stamp
        if not self.db_path.is_file():
            return []
        try:
            # `mode=ro` at the ENGINE level: this runs inside a spawn's
            # tool call against the live run's database, and a notice
            # that could write to it would be a second write channel
            # wearing a reader's name.
            conn = sqlite3.connect(
                f"file:{self.db_path.as_posix()}?mode=ro", uri=True,
                timeout=5)
        except sqlite3.Error:
            return []
        try:
            docs = self._rows(
                conn,
                "SELECT id, path FROM theory_documents"
                " WHERE problem = ? AND status = 'accepted'"
                " AND path IS NOT NULL")
            # `updated_at` is when the row reached `proved` (nothing
            # touches a proved goal afterwards on this path) — the
            # timestamp the catalog's own stamp is measured against.
            # A schema without the column is a workspace whose bricks
            # simply carry no landing time: `_rows` answers [], so the
            # query is asked in the plainer spelling too.
            goals = self._rows(
                conn,
                "SELECT id, slug, lean_path, updated_at FROM goals"
                " WHERE problem = ? AND status = 'proved'") or self._rows(
                conn,
                "SELECT id, slug, lean_path, NULL FROM goals"
                " WHERE problem = ? AND status = 'proved'")
        finally:
            conn.close()
        lines: "list[str]" = []
        for row in docs:
            if row[0] in self._accepted:
                continue
            self._accepted.add(row[0])
            if self._primed:
                # `theory_documents.path` is already workspace-relative
                # (schema: "under Problems/<project>/_docs/agent/"), so
                # it is what `inspect` resolves — only the separator
                # needs to be the one this project writes paths in.
                doc = str(row[1]).replace("\\", "/")
                lines.append(f"- theory document accepted: `{doc}`")
        cat = self._catalog()
        catalog, stamp = cat if cat is not None else (None, None)
        for row in goals:
            if row[0] in self._proved:
                continue
            self._proved.add(row[0])
            if self._primed:
                lines.append(_brick_line(
                    row[1], row[2], catalog, stamp,
                    _proved_at(row[3] if len(row) > 3 else None)))
        return lines

    def _catalog(self) -> "tuple[Path, datetime | None] | None":
        """This spawn's `CATALOG.md` and the moment it was rendered, or
        None when there is not one to name.

        Checked per trailer rather than once at construction: the
        companion is (re)written per wake, and a spawn whose problem
        proves its first brick gets one while it works. The STAMP is
        read on the same pass, because whether to name the file is a
        question about its contents, not its existence (`_brick_line`)."""
        if self.catalog_dir is None:
            return None
        cand = self.catalog_dir / CATALOG_COMPANION
        try:
            if not cand.is_file():
                return None
        except OSError:
            return None
        return cand, _catalog_stamp(cand)

    def _rows(self, conn: "sqlite3.Connection", sql: str) -> "list[tuple]":
        """One query, or nothing. A workspace whose schema predates a
        table is a workspace with no such news, never an error."""
        try:
            return list(conn.execute(sql, (self.problem,)))
        except sqlite3.Error:
            return []


# ---------------------------------------------------------------------
# the per-spawn registry
# ---------------------------------------------------------------------
#
# Both servers can host more than one spawn: the gateway is long-lived
# by design, and the tools module is imported once by the zen shim for
# many. So the baseline is keyed by the spawn, never by the process.

_WATCHERS: "dict[str, ChangeNotice]" = {}
_WATCHERS_LOCK = threading.Lock()
_MAX_WATCHERS = 256


def for_spawn(key: "str | None", *, workspace, problem: "str | None",
              db_path=None, catalog_dir=None) -> "ChangeNotice | None":
    """The watcher for one spawn, created (and baselined) on first ask.

    Call it when the spawn STARTS — the gateway does, at `/register` —
    so "since you started" means what it says. A later first call still
    works; its baseline is just later."""
    if not key or not (problem or "").strip() or workspace is None:
        return None
    try:
        with _WATCHERS_LOCK:
            found = _WATCHERS.get(key)
            if found is not None:
                return found
            if len(_WATCHERS) >= _MAX_WATCHERS:
                _WATCHERS.clear()
            made = ChangeNotice(workspace, problem, db_path=db_path,
                                catalog_dir=catalog_dir)
            _WATCHERS[key] = made
            return made
    except Exception:  # noqa: BLE001 — see the module docstring
        return None


def forget(key: "str | None") -> None:
    """Drop a spawn's baseline (the gateway calls this on `/release`)."""
    if not key:
        return
    with _WATCHERS_LOCK:
        _WATCHERS.pop(key, None)


# ---------------------------------------------------------------------
# the one wrap per server
# ---------------------------------------------------------------------

def install(server, resolve, *, suppress=None) -> None:
    """Make every tool on `server` carry the notice — in ONE place.

    `server` is a FastMCP instance. The wrap goes on its tool manager's
    dispatch rather than on the tools, because a per-tool decorator is a
    list that rots: the next tool added to either server would be born
    silent, and nothing would say so.

    `resolve()` is called per tool call and returns the `ChangeNotice`
    for the CALLING spawn, or None — the gateway serves many spawns at
    once and its answer is request-local.

    `suppress(name, arguments)` may veto the trailer for one call. Its
    one use is a byte-faithful answer (`inspect`'s `raw` read), where
    the agent writes the result back to a file and a notice appended to
    it would land IN that file. A suppressed call consumes nothing: the
    news is still unreported, so the next call carries it.
    """
    manager = getattr(server, "_tool_manager", None)
    if manager is None or getattr(manager, "_asterism_change_notice", False):
        return
    inner = manager.call_tool

    async def call_tool(name, arguments, *args, **kwargs):
        result = await inner(name, arguments, *args, **kwargs)
        try:
            if suppress is not None and suppress(name, arguments):
                return result
            watcher = resolve()
            text = watcher.trailer() if watcher is not None else ""
        except Exception:  # noqa: BLE001 — see the module docstring
            return result
        if not text:
            return result
        try:
            return append(result, text)
        except Exception:  # noqa: BLE001 — see the module docstring
            return result

    manager.call_tool = call_tool
    manager._asterism_change_notice = True


def append(result, text: str):
    """Put `text` at the end of whatever a FastMCP tool call returned.

    With `structured_output=False` — which is every tool on both servers
    — that is a list of content blocks, and the notice belongs on the
    LAST text block: the agent reads one string, and a second block
    would be a second message some clients render apart from the first.
    """
    if isinstance(result, str):
        return result + text
    if isinstance(result, tuple) and len(result) == 2:
        # (unstructured, structured) — the agent reads the first half.
        return (append(result[0], text), result[1])
    if isinstance(result, list):
        blocks = list(result)
        for i in range(len(blocks) - 1, -1, -1):
            block = blocks[i]
            if getattr(block, "type", None) == "text":
                blocks[i] = block.model_copy(
                    update={"text": (block.text or "") + text})
                return blocks
        made = _text_block(text.lstrip("\n"))
        return blocks + [made] if made is not None else blocks
    return result


def _text_block(text: str):
    try:
        from mcp.types import TextContent
    except Exception:  # noqa: BLE001 — no mcp = nothing to render into
        return None
    return TextContent(type="text", text=text)
