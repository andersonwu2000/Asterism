"""Library chapter — the harvested modules of ONE problem, read for
humans (module docstrings as prose, per-decl docstrings, the
kernel-true oracle signature). File parsing here is read-side
visualization only, same standing as `edges.py`'s citation scan —
nothing it extracts feeds soundness. The trailing telemetry/papers/
raw-file-read functions rode along: they sit in the file after the
"Library chapter" marker with no call edge to anything above it.

Split out of `data.py` 2026-08-28 (Phase B, B3) unchanged.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ...pipeline.librarian.astslice import _library_module_of
from ...quality.librarian.gates import IMPORT_LINE_PATTERN
from ...state import db
from .timeline import _goal_signature


# ---------------------------------------------------------------------
# Library chapter — the harvested modules of ONE problem, read for
# humans. The Library exists for readability (near-Mathlib files, fit
# to upstream or to read), so its reading surface shows the CURATED
# text: module docstrings as prose, per-decl docstrings, and the
# kernel-true signature from the declInfo oracle (stored at bridge
# time). File parsing here is read-side visualization only — nothing
# it extracts feeds soundness (same standing as `_citation_edges`).
# ---------------------------------------------------------------------

_MODULE_DOC_RE = re.compile(r"/-!(.*?)-/", re.S)
_DOCSTRING_RE = re.compile(r"/--(.*?)-/", re.S)
_DECL_RE = re.compile(
    r"^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?(?:private\s+|protected\s+)?"
    r"(theorem|lemma|def|abbrev|structure|class|instance|inductive|alias)\s+"
    r"([A-Za-z0-9_'₀-₉α-ω.]+)",
    re.M)
# the one spelling of a Lean import line (public/private prefixes,
# leading whitespace — gates.py owns it), compiled for whole-text scans
_IMPORT_RE = re.compile(IMPORT_LINE_PATTERN, re.M)


def _stmt_head(text: str, start: int) -> str:
    """The declaration header from `start` to its top-level `:=` /
    `where` — the statement without the proof body. Bracket-depth walk,
    display fallback only (the oracle signature wins when stored)."""
    depth = 0
    i = start
    limit = min(len(text), start + 4000)
    while i < limit:
        ch = text[i]
        if ch in "([{⟨":
            depth += 1
        elif ch in ")]}⟩":
            depth -= 1
        elif depth == 0:
            if text.startswith(":=", i):
                return text[start:i].rstrip()
            if text.startswith("where", i) and (i == 0 or text[i - 1].isspace()):
                return text[start:i].rstrip()
            if text.startswith("\n\n", i):  # header can't span a blank line
                return text[start:i].rstrip()
        i += 1
    return text[start:limit].rstrip()


_CTX_LINE_RE = re.compile(r"^(?:open(?:\s+scoped)?\b|universe\b|variable\b)")


def _context_preamble(text: str, first_decl_pos: int) -> str:
    """The module's context lines (`open` / `open scoped` / `universe`
    / `variable` + their indented continuations) before the first decl.
    A decl's source is NOT self-contained without them: the librarian
    hoists instance hypotheses into a `variable` block, so a probe
    that re-elaborates the bare source auto-binds `N`/`EH` as naked
    Types and every instance lookup fails (owner report, 2026-07-18:
    a wall of `failed to synthesize TopologicalSpace N` over a goal of
    sorries). Comments are stripped first so prose starting with
    "open …" inside the module docstring can't leak in."""
    head = re.sub(r"/-[\s\S]*?-/", "", text[:first_decl_pos])
    out: "list[str]" = []
    cont = False
    for ln in head.split("\n"):
        if _CTX_LINE_RE.match(ln):
            out.append(ln)
            cont = True
        elif cont and ln.strip() != "" and ln[:1] in (" ", "\t"):
            out.append(ln)
        else:
            cont = False
    return "\n".join(out).strip()


def _scan_library_file(
        text: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str, str | None]], list[str], str]":
    """(module_doc, {short_decl_name: (line, docstring, kind, stmt,
    source)}, imports, context). `line` is 1-based — same domain as the
    oracle-backed `library_decls.src_line`, so the two sort keys mix
    cleanly. `source` is the decl's full source block (attributes +
    header + body, docstring excluded) — the chapter's run state seeds
    an editor with it; `context` is the preamble that makes a source
    block elaborate standalone."""
    m = _MODULE_DOC_RE.search(text)
    module_doc = m.group(1).strip() if m else ""
    docs: "dict[str, tuple[int, str, str, str, str | None]]" = {}
    doc_ends = [(d.end(), d.group(1).strip()) for d in _DOCSTRING_RE.finditer(text)]
    matches = list(_DECL_RE.finditer(text))
    for i, dm in enumerate(matches):
        name = dm.group(2).split(".")[-1]
        if name in docs:
            continue  # first occurrence wins (aliases repeat names)
        doc = ""
        for end, body in doc_ends:
            if end > dm.start():
                break
            # attached iff only whitespace/attributes/line comments
            # separate them (corpus writes `--` notes between doc and
            # decl; those must not orphan the docstring)
            gap = text[end:dm.start()]
            if re.fullmatch(r"(?:\s|@\[[^\]]*\]|--[^\n]*)*", gap):
                doc = body
        nxt = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        src = text[dm.start():nxt].rstrip()
        # the tail may be the NEXT decl's docstring / section header /
        # `... in`-modifier lines (set_option, open, attributes) or an
        # `end Foo` namespace closer — all belong to what follows, not
        # to this decl; strip until the block ends in real content
        while True:
            tail = re.search(
                r"\n\s*(?:/(?:--|-!)(?:(?!-/)[\s\S])*-/|end\s+[\w.]+"
                r"|(?:set_option|open)[^\n]*\bin|@\[[^\]]*\]"
                r"|--[^\n]*)\s*$", src)
            if not tail:
                break
            src = src[:tail.start()].rstrip()
        docs[name] = (text.count("\n", 0, dm.start()) + 1, doc,
                      dm.group(1), _stmt_head(text, dm.start()),
                      src or None)
    context = _context_preamble(
        text, matches[0].start() if matches else len(text))
    return module_doc, docs, _IMPORT_RE.findall(text), context


#: path str -> (mtime_ns, module_doc, docs, imports, word-set, context)
#: — the _cite_file_cache pattern: stat everything, re-read only
#: changes. The chapter is polled every 30s; steady-state ~stat-only.
_chapter_scan_cache: "dict[str, tuple[int, str, dict, list[str], frozenset, str]]" = {}


def _scanned_library_file(
        workspace: Path, path: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str]], list[str], frozenset, str]":
    """Mtime-memoized `_scan_library_file` plus the file's whole-word
    token set — `short in words` is equivalent to the boundary-guarded
    regex search because decl short names are single `[\\w']+` tokens."""
    fp = workspace / path
    try:
        mtime = fp.stat().st_mtime_ns
    except OSError:
        _chapter_scan_cache.pop(path, None)
        return "", {}, [], frozenset(), ""
    cached = _chapter_scan_cache.get(path)
    if cached is None or cached[0] != mtime:
        try:
            # errors="replace": presentation must never fail the page
            # (same policy as _cite_file_cache)
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:  # transient read failure — retry next request
            return "", {}, [], frozenset(), ""
        module_doc, docs, imports, context = _scan_library_file(text)
        cached = (mtime, module_doc, docs, imports,
                  frozenset(re.findall(r"[\w']+", text)), context)
        _chapter_scan_cache[path] = cached
    return cached[1], cached[2], cached[3], cached[4], cached[5]


def library_chapter(conn: sqlite3.Connection, workspace: Path,
                    problem: str) -> "dict | None":
    """One bridged problem's contributed Library modules, in import
    order, each decl carrying its docstring + oracle signature and its
    goal-side meaning (claim = deliverable, def-kind = vocabulary)."""
    # the one bridged+placed definition (db.bridged_library_index),
    # narrowed to this problem; rows carry library_bridged_at
    rows = db.bridged_library_index(conn, problem=problem).get(problem, [])
    if not rows:
        return None
    # goal-side flag only: kind comes from library_decls.decl_kind
    # (kernel-true since v24; goals.kind would duplicate it worse)
    deliverable = {
        str(g["slug"]): bool(g["is_deliverable"])
        for g in conn.execute(
            "SELECT slug, is_deliverable FROM goals WHERE problem = ?",
            (problem,))}

    per_file: "dict[str, list[sqlite3.Row]]" = {}
    for r in rows:
        per_file.setdefault(str(r["target_file"] or ""), []).append(r)
    scanned = {path: _scanned_library_file(workspace, path)
               for path in per_file}

    # Import order tells the story: a module comes after the siblings
    # it imports (Kahn; ties keep path order for determinism).
    mod_of = {path: _library_module_of(path) for path in per_file}
    mod_paths = {v: k for k, v in mod_of.items()}
    deps_of = {path: [d for d in scanned[path][2]
                      if d in mod_paths and d != mod_of[path]]
               for path in per_file}
    ordered: "list[str]" = []
    pending = sorted(per_file)
    placed: "set[str]" = set()
    while pending:
        progressed = False
        for path in list(pending):
            if all(mod_paths[d] in placed for d in deps_of[path]):
                ordered.append(path)
                placed.add(path)
                pending.remove(path)
                progressed = True
        if not progressed:  # import cycle can't happen; guard anyway
            ordered.extend(pending)
            break

    # Cross-module usage: in how many OTHER modules of this problem
    # does the decl's name appear? Ingest weakens the anchor/claim
    # flags (older harvests never had them), but a lemma the other
    # files keep reaching for is a keystone by demonstration — the
    # honest importance weight for the highlights view. Whole-word
    # heuristic (blueprint precedent), display only.
    files = []
    for path in ordered:
        module_doc, docs, imports, _words, context = scanned[path]
        keyed: "list[tuple[int, dict]]" = []
        for r in per_file[path]:
            slug = str(r["slug"])
            short = str(r["target_name"] or slug).split(".")[-1]
            line, doc, file_kind, file_stmt, file_src = docs.get(
                short, (1 << 30, "", "", "", None))
            # oracle values win (v24: docstring/src_line stored at bridge;
            # docstring '' = confirmed none, NULL = pre-backfill row →
            # curated source text fallback)
            if r["docstring"] is not None:
                doc = r["docstring"]
            if r["src_line"] is not None:
                line = int(r["src_line"])
            used_by = sum(1 for q in per_file
                          if q != path and short in scanned[q][3])
            keyed.append((line, {
                "slug": slug,
                "name": r["target_name"],
                # oracle values win; older harvests fall back to the
                # curated source text (display only)
                "signature": r["signature"] or file_stmt or None,
                "decl_kind": r["decl_kind"] or file_kind or None,
                "doc": doc,
                # the decl's real source block — the run state seeds a
                # live editor with it (proof included, editable)
                "source": file_src,
                # the module preamble (opens + variable block) that
                # makes `source` elaborate standalone — without it the
                # probe's instance hypotheses vanish and the goal
                # collapses into sorries
                "context": context or None,
                "is_deliverable": deliverable.get(slug, False),
                "used_by": used_by,
            }))
        keyed.sort(key=lambda t: t[0])  # source order = narrative
        decls = [d for _, d in keyed]
        files.append({
            "path": path,
            "module_doc": module_doc,
            "decls": decls,
            # within-problem import edges — the file-level sky
            "imports_within": [mod_paths[i] for i in imports
                               if i in mod_paths and mod_paths[i] != path],
        })
    # Trust colophon (design round, 2026-07-13): the chapter states its
    # own guarantees from RECORDED facts only — decl count, and the
    # axiom whitelist the bridge gate enforced (Gate B re-derives the
    # root from the Library alone and rejects any axiom outside it;
    # the migrate gate rejects sorry). Read-side; nothing here feeds
    # soundness.
    axioms: "list[str]" = []
    try:
        from ...state import intent as _intent
        pintent = _intent.read(conn, problem)
        axioms = (_intent.effective_axioms(pintent, problem=problem)
                  if pintent is not None
                  else list(_intent.FRAMEWORK_DEFAULT_AXIOMS))
    except Exception:  # noqa: BLE001 — a colophon must never 500 the page
        axioms = []
    # The theorem itself: the problem's root statement — Gate B
    # re-derives exactly this from the Library modules alone, so it IS
    # what the chapter proves. Surfaced so the chapter can OPEN with
    # its main result (first-time QA, 2026-07-20: a mathematician
    # searched the stokes chapter and never found Stokes' theorem —
    # old harvests lost their claim flags, leaving Highlights all
    # vocabulary and keystones).
    root = None
    try:
        rrow = conn.execute(
            "SELECT slug, statement, lean_path FROM goals"
            " WHERE problem = ? AND origin = 'root'"
            " ORDER BY id LIMIT 1", (problem,)).fetchone()
        if rrow is not None:
            root = {
                "slug": str(rrow["slug"]),
                "statement": _goal_signature(
                    workspace, str(rrow["slug"]), rrow["lean_path"],
                    rrow["statement"]) or str(rrow["statement"]),
            }
    except sqlite3.OperationalError:
        pass
    return {
        "problem": problem,
        "bridged_at": rows[0]["library_bridged_at"],
        "root": root,
        "files": files,
        "colophon": {
            "decls": sum(len(f["decls"]) for f in files),
            "axioms": axioms,
        },
    }


def telemetry_usage(conn: sqlite3.Connection, *,
                    since: "str | None" = None,
                    project: "str | None" = None) -> dict:
    """spawn_usage aggregation: totals per problem and per (problem,
    pipeline kind). `since` (an ISO timestamp, same format as the `ts`
    column) restricts the window — pass the running daemon's start time
    to get THIS run's burn instead of the all-time ledger. `project`
    scopes it to one shelf (the Engine Room lives inside a Project,
    §1.4) by the FK — `problems_of`, never the name's first segment,
    which stops being the Project the moment someone renames one."""
    per_problem: dict[str, dict] = {}
    where = " WHERE ts >= ?" if since else ""
    params: tuple = (since,) if since else ()
    for r in conn.execute(
            "SELECT COALESCE(problem, '') AS problem, kind,"
            " COUNT(*) AS spawns,"
            " SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok,"
            " SUM(cache_read_tokens) AS cache_tok,"
            " SUM(cache_new_tokens) AS cache_new,"
            " SUM(turns) AS turns, SUM(wall_sec) AS wall"
            " FROM spawn_usage" + where + " GROUP BY problem, kind",
            params):
        p = per_problem.setdefault(str(r["problem"]) or "(none)", {
            "problem": str(r["problem"]) or "(none)",
            "spawns": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_new_tokens": 0,
            "turns": 0, "wall_sec": 0.0,
            "kinds": [],
        })
        row = {
            "kind": str(r["kind"]),
            "spawns": int(r["spawns"]),
            "input_tokens": int(r["in_tok"] or 0),
            "output_tokens": int(r["out_tok"] or 0),
            "cache_read_tokens": int(r["cache_tok"] or 0),
            "cache_new_tokens": int(r["cache_new"] or 0),
            "turns": int(r["turns"] or 0),
            "wall_sec": float(r["wall"] or 0.0),
        }
        p["kinds"].append(row)
        p["spawns"] += row["spawns"]
        p["input_tokens"] += row["input_tokens"]
        p["output_tokens"] += row["output_tokens"]
        p["cache_read_tokens"] += row["cache_read_tokens"]
        p["cache_new_tokens"] += row["cache_new_tokens"]
        p["turns"] += row["turns"]
        p["wall_sec"] += row["wall_sec"]
    rows = sorted(per_problem.values(),
                  key=lambda x: -(x["input_tokens"] + x["output_tokens"]))
    if project is not None:
        from ...state import projects as _projects
        shelf = _projects.problems_of(conn, project)
        rows = [r for r in rows if r["problem"] in shelf]
    return {"problems": rows}


def problem_papers_detail(conn: sqlite3.Connection, workspace: Path,
                          problem: str) -> dict:
    """One problem's citations: bindings joined with shelf meta (a
    binding whose shelf slot vanished still shows, flagged missing).

    `path` is the paper's address in the Project's documents (§3.9), so
    a row can link straight to what it cites; None when the slot is
    missing, which is the same fact `missing` reports."""
    from ...papers import shelf as _shelf
    from ...state import project_docs as _project_docs
    from ...state import projects as _projects
    project = _projects.project_of(conn, problem) \
        or problem.split(".", 1)[0]
    out = []
    for r in db.paper_bindings(conn, problem):
        pid = str(r["paper_id"])
        pdir = _shelf.paper_dir(workspace, pid, project=project)
        meta = _shelf.load_meta(workspace, pid, project=project)
        out.append({
            "id": pid,
            "origin": str(r["origin"]),
            "reason": r["reason"],
            "source_name": meta.source_name if meta else None,
            "path": None if pdir is None else pdir.relative_to(
                _project_docs.root(workspace, project)).as_posix(),
            "missing": meta is None,
        })
    return {"problem": problem, "papers": out}


def read_problem_file(workspace: Path, problem: str,
                      rel_path: str) -> str | None:
    """Read-only file fetch, sandboxed to the problem directory.
    Only .lean / .md files; traversal outside the dir is refused."""
    if not rel_path.endswith((".lean", ".md")):
        return None
    pdir = db.problem_dir(workspace, problem).resolve()
    target = (pdir / rel_path).resolve()
    if not str(target).startswith(str(pdir)):
        return None
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return None
