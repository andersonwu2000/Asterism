"""Librarian pipeline — turn a proved problem into a mathlib-shaped Library.

Multi-work-kind agent (mirrors Strategist's multi-decision shape), with
the migrate kind borrowing Builder's LSP + commit-retry loop. See
docs/internal/librarian_plan.md §12.

Work kinds:
  - dedup    — emit per-decl verdicts (keep/cite-*/drop/merge) → library_decls
  - classify — emit a file-layout plan → library_decls target_file/order
  - migrate  — reshape one decl into its Library file (LSP + retry; later stage)

This module (stage A) is the pure parse + verify + commit core for the
two structured-JSON work kinds (dedup, classify). The agent stage
(spawn + Context.md) and the migrate LSP loop are later stages.

Pure surface (no gateway / no LLM):
  - VERDICTS / DEDUP keys
  - parse_dedup(json_text)     -> (list[DedupVerdict] | None, err)
  - parse_classify(json_text)  -> (ClassifyPlan | None, err)
  - verify_dedup(verdicts, inventory_slugs) -> "" | err
  - verify_classify(plan, kept_slugs)       -> "" | err
  - commit_dedup(conn, problem, verdicts)
  - commit_classify(conn, problem, plan)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..state import db


# Verdicts the dedup work kind may emit (mirrors prompts/librarian/dedup.md).
VERDICTS: frozenset[str] = frozenset({
    "keep", "cite-mathlib", "cite-library", "drop", "merge",
})

# Verdicts that must name a citation/canonical target to be actionable.
_NAMED_VERDICTS: frozenset[str] = frozenset({
    "cite-mathlib", "cite-library", "drop", "merge",
})


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------

@dataclass
class DedupVerdict:
    slug: str
    verdict: str
    citation: str | None = None   # mathlib_name / library_name / canonical
    reason: str = ""


@dataclass
class ClassifyFile:
    path: str
    imports: list[str] = field(default_factory=list)
    decls: list[str] = field(default_factory=list)


@dataclass
class ClassifyPlan:
    files: list[ClassifyFile]


# ---------------------------------------------------------------------
# JSON parsing (mirrors strategist.parse_decisions fence-stripping)
# ---------------------------------------------------------------------

def _load_json(json_text: str):
    """Strip ```json fences and parse. Returns (obj, "") or (None, err)."""
    text = json_text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines()
                 if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def parse_dedup(json_text: str) -> tuple[list[DedupVerdict] | None, str]:
    """Parse the dedup agent's verdict array. Accepts a single object or
    an array. All-or-nothing: any malformed entry rejects the batch."""
    obj, err = _load_json(json_text)
    if err:
        return None, err
    if isinstance(obj, dict):
        obj = [obj]
    if not isinstance(obj, list):
        return None, f"expected object or array, got {type(obj).__name__}"
    if not obj:
        return None, "empty verdict array"

    out: list[DedupVerdict] = []
    for i, e in enumerate(obj):
        if not isinstance(e, dict):
            return None, f"entry {i}: not an object"
        slug = e.get("slug")
        verdict = e.get("verdict")
        if not slug or not isinstance(slug, str):
            return None, f"entry {i}: missing/invalid 'slug'"
        if verdict not in VERDICTS:
            return None, (f"entry {i} ({slug}): verdict {verdict!r} not in "
                          f"{sorted(VERDICTS)}")
        # Citation can arrive under several keys depending on verdict.
        citation = (e.get("citation") or e.get("mathlib_name")
                    or e.get("library_name") or e.get("canonical"))
        out.append(DedupVerdict(
            slug=slug, verdict=verdict,
            citation=citation if isinstance(citation, str) else None,
            reason=str(e.get("reason", "")),
        ))
    return out, ""


def parse_classify(json_text: str) -> tuple[ClassifyPlan | None, str]:
    """Parse the classify agent's layout plan: `{"files": [...]}`."""
    obj, err = _load_json(json_text)
    if err:
        return None, err
    if not isinstance(obj, dict):
        return None, f"expected object with 'files', got {type(obj).__name__}"
    files_raw = obj.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        return None, "missing/empty 'files' array"

    files: list[ClassifyFile] = []
    for i, f in enumerate(files_raw):
        if not isinstance(f, dict):
            return None, f"file {i}: not an object"
        path = f.get("path")
        if not path or not isinstance(path, str):
            return None, f"file {i}: missing/invalid 'path'"
        decls = f.get("decls")
        if not isinstance(decls, list) or not decls:
            return None, f"file {i} ({path}): missing/empty 'decls'"
        if not all(isinstance(d, str) for d in decls):
            return None, f"file {i} ({path}): non-string in 'decls'"
        imports = f.get("imports") or []
        if not isinstance(imports, list) or \
                not all(isinstance(m, str) for m in imports):
            return None, f"file {i} ({path}): 'imports' must be string list"
        files.append(ClassifyFile(path=path, imports=list(imports),
                                  decls=list(decls)))
    return ClassifyPlan(files=files), ""


# ---------------------------------------------------------------------
# Verify (semantic checks before commit)
# ---------------------------------------------------------------------

def dedup_slug_universe(inv) -> set[str]:
    """Slugs a dedup batch may pass verify: proved declarations PLUS
    Defs.lean decls. The dedup agent is asked to judge both (a def can
    reinvent a mathlib notion — see prompts/librarian/dedup.md), so the
    verify slug set must match the universe shown in Context.md. Keep this
    the single source of that union — _run_structured and the candidate-row
    upsert both derive from it."""
    return {d.slug for d in inv.decls} | set(inv.defs_decls)


def verify_dedup(verdicts: list[DedupVerdict],
                 inventory_slugs: set[str]) -> str:
    """Reject a dedup batch that is not actionable. Returns "" on ok."""
    seen: set[str] = set()
    for v in verdicts:
        if v.slug not in inventory_slugs:
            return f"{v.slug}: not in this problem's inventory"
        if v.slug in seen:
            return f"{v.slug}: duplicate verdict"
        seen.add(v.slug)
        if v.verdict in _NAMED_VERDICTS and not v.citation:
            return (f"{v.slug}: verdict {v.verdict!r} requires a named "
                    f"target (mathlib lemma / Library entry / canonical "
                    f"sibling)")
        if v.verdict == "merge" and v.citation not in inventory_slugs:
            return (f"{v.slug}: merge canonical {v.citation!r} is not a "
                    f"sibling in this problem")
    return ""


def verify_classify(plan: ClassifyPlan, kept_slugs: set[str]) -> str:
    """Reject a layout plan that doesn't cover exactly the kept decls,
    imports a non-Library module, or has an import cycle. "" on ok."""
    # Every kept decl placed exactly once; no stray slugs.
    placed: list[str] = [d for f in plan.files for d in f.decls]
    placed_set = set(placed)
    if len(placed) != len(placed_set):
        dup = next(d for d in placed if placed.count(d) > 1)
        return f"decl {dup!r} placed in more than one file"
    missing = kept_slugs - placed_set
    if missing:
        return f"kept decls not placed: {sorted(missing)}"
    stray = placed_set - kept_slugs
    if stray:
        return f"plan places non-kept decls: {sorted(stray)}"

    # Imports must be Library modules; build the file-module graph.
    modules = {_path_to_module(f.path): f for f in plan.files}
    for f in plan.files:
        for imp in f.imports:
            if not imp.startswith("Library."):
                return f"{f.path}: import {imp!r} is not a Library module"
    # Acyclicity over the intra-plan dependency edges.
    cycle = _find_cycle({
        _path_to_module(f.path): [m for m in f.imports if m in modules]
        for f in plan.files
    })
    if cycle:
        return f"import cycle: {' -> '.join(cycle)}"
    return ""


def _path_to_module(path: str) -> str:
    """`Library/LinearAlgebra/Jordan.lean` -> `Library.LinearAlgebra.Jordan`."""
    p = path[:-5] if path.endswith(".lean") else path
    return p.replace("/", ".").replace("\\", ".")


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """DFS cycle detection; returns a cycle path or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def dfs(n: str) -> list[str] | None:
        color[n] = GRAY
        stack.append(n)
        for m in graph.get(n, []):
            if color.get(m, BLACK) == GRAY:
                return stack[stack.index(m):] + [m]
            if color.get(m, BLACK) == WHITE:
                r = dfs(m)
                if r:
                    return r
        stack.pop()
        color[n] = BLACK
        return None

    for n in graph:
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


# ---------------------------------------------------------------------
# Commit (side effects into library_decls)
# ---------------------------------------------------------------------

def commit_dedup(conn, problem: str,
                 verdicts: list[DedupVerdict]) -> None:
    """Persist dedup verdicts. Each slug must already have a candidate
    row (created by Step 0 inventory); set_library_verdict advances its
    lifecycle by the verdict→state map."""
    for v in verdicts:
        db.set_library_verdict(conn, problem=problem, slug=v.slug,
                               verdict=v.verdict, citation=v.citation)


def commit_classify(conn, problem: str, plan: ClassifyPlan) -> None:
    """Persist the layout plan: per decl, its target file + in-file
    order. Only `deduped` (kept) decls advance to `classified`."""
    for f in plan.files:
        for order, slug in enumerate(f.decls):
            db.set_library_classification(
                conn, problem=problem, slug=slug,
                target_file=f.path, target_name=None, file_order=order)


# ---------------------------------------------------------------------
# Stage B — migrate work: commit gate (Gate A import-closure + build)
# ---------------------------------------------------------------------
# The migrate work kind reshapes one classified decl into its target
# Library file, using the same LSP + session-retry loop as Builder
# (run_with_session_retries). The agent writes `patch.lean` in the
# sandbox; on a clean spawn the framework runs this commit gate, and on
# success copies patch.lean to the target Library file + marks the decl
# 'migrated'. Mirrors builder.py's builder_parse commit window.
#
# `migrate_commit_gate` is the pure, gateway-optional core: it takes the
# candidate patch text + target path and returns (ok, detail). The
# build-verify step is injectable (`build_verifier`) so it is unit-
# testable without a live gateway, same pattern as gates.check_root_
# rederivation's `prober`.

from pathlib import Path as _Path


@dataclass
class MigrateResult:
    ok: bool
    detail: str = ""


_DECL_KW = ("theorem", "lemma", "def", "abbrev", "structure",
            "class", "instance")
_DECL_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(?:" + "|".join(_DECL_KW) + r")\s+([A-Za-z_][\w']*)")
_NS_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)")


def extract_decl_fq_name(patch_text: str) -> str | None:
    """The fully-qualified name of the single declaration a migrate patch
    introduces — `<namespace>.<decl>` — for `#print axioms`. The decl's
    FQ name is namespace-derived, independent of the (temp) file name, so
    the axiom probe resolves it regardless of where the patch is written.

    Scans for the last `namespace …` before the first named declaration.
    Returns None when no named decl is found (anonymous `instance : …` or
    a malformed patch) — the caller fails the gate rather than skipping
    the axiom check, keeping the per-file invariant honest."""
    ns: str | None = None
    for line in patch_text.splitlines():
        m = _DECL_RE.match(line)
        if m:
            return f"{ns}.{m.group(1)}" if ns else m.group(1)
        m = _NS_RE.match(line)
        if m:
            ns = m.group(1)
    return None


# Decl-kind detector (Gate D must distinguish def/abbrev from nominal
# kinds). Reuses _DECL_KW; captures the keyword rather than the name.
_DECL_KW_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(def|abbrev|theorem|lemma|structure|class|inductive|instance)\b")

# Nominal kinds: two separate declarations are never definitionally equal
# even with identical fields, so `rfl` (Gate D) cannot equate them.
_NOMINAL_KINDS = ("structure", "class", "inductive")


def extract_decl_kind(patch_text: str) -> str | None:
    """The keyword (`def` / `abbrev` / `theorem` / `structure` / …) of the
    first named declaration in a patch, or None when none is found.
    Mirrors `extract_decl_fq_name`'s scan; together they classify the
    migrated declaration for Gate D."""
    for line in patch_text.splitlines():
        m = _DECL_KW_RE.match(line)
        if m:
            return m.group(1)
    return None


def _library_module_of(rel_lean_path: str) -> str:
    """Map a Library file's repo-relative path to its Lean module name:
    `Library/LinearAlgebra/JordanForm/Defs.lean` →
    `Library.LinearAlgebra.JordanForm.Defs`."""
    p = rel_lean_path.replace("\\", "/")
    if p.endswith(".lean"):
        p = p[:-5]
    return p.replace("/", ".")


def migrate_defeq_gate(
    patch_text: str, *, problem: str, target_slug: str,
    defs_decls: "list[str]", target_module: str,
    defeq_verifier=None, workspace: "_Path | None" = None,
) -> MigrateResult:
    """Gate D for the migrate path — the def-tampering guard (plan §2).

    Only Defs-originated declarations are checked; a regular migrated
    lemma passes untouched. The kernel can't prove a strong root from a
    weakened lemma, so lemmas need no defeq pin — only a `def` body, which
    spans a statement's hypothesis AND conclusion, can be silently
    tampered while every other gate still passes.

      - `target_slug` not in `defs_decls` → ok (not a Defs decl).
      - structure / class / inductive Defs decl → fail (nominal; `rfl`
        cannot equate two declarations — decline-and-flag for a verbatim
        special-case).
      - def / abbrev Defs decl → `@Problems.<p>.<slug> = @<target> := rfl`
        must elaborate (via `gates.check_def_equivalence`). The probe
        imports the problem's Defs and the migrated Library module, so the
        caller MUST have the Library file on disk before calling.

    `defeq_verifier` is injectable (forwarded to check_def_equivalence) so
    unit tests run gateway-free."""
    if target_slug not in defs_decls:
        return MigrateResult(True, "")
    kind = extract_decl_kind(patch_text)
    if kind in _NOMINAL_KINDS:
        return MigrateResult(
            False, f"Gate D: Defs decl `{target_slug}` is a {kind} "
                   "(nominal) — `rfl` cannot equate two separate "
                   "declarations; needs a verbatim special-case "
                   "(decline-and-flag).")
    target_fq = extract_decl_fq_name(patch_text)
    if target_fq is None:
        return MigrateResult(
            False, "Gate D: could not extract the migrated declaration's "
                   "name (anonymous or malformed decl)")
    from ..quality.librarian import gates
    defs_fq = f"Problems.{problem}.{target_slug}"
    res = gates.check_def_equivalence(
        defs_fq, target_fq,
        imports=[f"Problems.{problem}.Defs", target_module],
        verifier=defeq_verifier, workspace=workspace)
    if res.ok:
        return MigrateResult(True, "")
    return MigrateResult(False, "; ".join(res.issues))


def migrate_commit_gate(
    patch_text: str, target_path: "_Path", *,
    whitelist: "list[str] | None" = None,
    build_verifier=None, axiom_verifier=None,
    workspace: "_Path | None" = None,
) -> MigrateResult:
    """Decide whether a migrate patch may be committed to its Library
    file. Hard checks (plan §2 Gate A + build + per-file axiom check):

      1. import-closure — patch imports only Mathlib/Library (Gate A).
      2. build — `lake env lean` clean (0 errors, 0 sorry) via the warm
         gateway. Injectable as `build_verifier(text) -> (ok, detail)`
         so tests run without a gateway; defaults to the real warm probe.
      3. axiom check — when `whitelist` is set, the migrated declaration's
         transitive axiom set must be ⊆ whitelist (operator's authorized
         axioms; falls back to the 3 standard axioms upstream). This is
         the per-Library-file `#print axioms` the operator requires:
         build alone accepts a file whose imports carry `sorry`, only
         `#print axioms` walks the kernel graph. Injectable as
         `axiom_verifier(text, fq_name, whitelist) -> (ok, detail)`;
         defaults to the real warm probe. `whitelist=None` skips it
         (unit tests that only exercise closure/build don't pass one).

    Does NOT write anything — the caller (migrate parse_fn) does the
    file copy + `mark_library_migrated` on ok=True.
    """
    from ..quality.librarian import gates

    closure = gates.check_import_closure_text(
        patch_text, label=target_path.name)
    if not closure.ok:
        return MigrateResult(False, "; ".join(closure.issues))

    if "sorry" in patch_text:
        # Cheap pre-check; the build also catches it, but a clear message
        # here beats a generic "declaration uses sorry" diagnostic.
        return MigrateResult(False, "patch still contains `sorry`")

    if build_verifier is None:
        build_verifier = _warm_build_verifier(workspace)
    ok, detail = build_verifier(patch_text)
    if not ok:
        return MigrateResult(False, f"build failed: {detail}")

    if whitelist is not None:
        fq_name = extract_decl_fq_name(patch_text)
        if fq_name is None:
            return MigrateResult(
                False, "axiom check: could not extract the declaration "
                       "name (anonymous or malformed decl)")
        if axiom_verifier is None:
            axiom_verifier = _warm_axiom_verifier(workspace)
        ok, detail = axiom_verifier(patch_text, fq_name, whitelist)
        if not ok:
            return MigrateResult(False, f"axiom check failed: {detail}")
    return MigrateResult(True, "")


def _warm_build_verifier(workspace):
    """Default build_verifier: write the candidate to a temp file under
    the workspace and run the warm-gateway verify. Returns (ok, detail).

    The temp file lives under `Library/` so the gateway resolves the
    Library import path; it is removed after the probe."""
    import os
    import tempfile

    def _verify(patch_text: str) -> tuple[bool, str]:
        from ..lsp import lifecycle as gateway_lifecycle
        ws = workspace or _Path(".")
        libdir = ws / "Library"
        libdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_migrate_probe_",
                                   dir=str(libdir))
        tmp_path = _Path(tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(patch_text)
            r = gateway_lifecycle.verify_file(
                tmp_path, write_olean=False, workspace=ws)
            if "error" in r and r.get("error"):
                return False, f"verify infra error: {r['error']}"
            if not r.get("ok"):
                errs = "; ".join(
                    d.get("message", "")[:120]
                    for d in (r.get("diagnostics") or [])
                    if d.get("severity") == "error"
                )[:300]
                return False, errs or "(no error diagnostics)"
            return True, ""
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return _verify


def _warm_axiom_verifier(workspace):
    """Default axiom_verifier: write the candidate under `Library/`, run
    the warm-gateway verify with `axioms_for=<fq_name>`, and check the
    reported axiom set ⊆ whitelist. Returns (ok, detail). Mirrors
    `_warm_build_verifier`'s temp-file staging; the rogue-axiom logic
    matches `pipeline/_axiom.axiom_probe` (which can't be reused directly
    — it resolves a module to an existing source path, but the migrate
    candidate is a throwaway temp file)."""
    import os
    import tempfile

    def _verify(patch_text: str, fq_name: str,
                whitelist: list[str]) -> tuple[bool, str]:
        from ..lsp import lifecycle as gateway_lifecycle
        ws = workspace or _Path(".")
        libdir = ws / "Library"
        libdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_migrate_axiom_",
                                   dir=str(libdir))
        tmp_path = _Path(tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(patch_text)
            r = gateway_lifecycle.verify_file(
                tmp_path, write_olean=False, axioms_for=fq_name,
                workspace=ws)
            if "error" in r and r.get("error"):
                return False, f"axiom probe infra error: {r['error']}"
            if r.get("axiom_error"):
                return False, f"axiom probe error: {r['axiom_error']}"
            used: set[str] = set(r.get("axioms") or [])
            rogue = used - set(whitelist)
            if rogue:
                return False, f"rogue axioms: {sorted(rogue)}"
            return True, ""
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return _verify


# ---------------------------------------------------------------------
# Stage C — Context.md compiler (per work kind)
# ---------------------------------------------------------------------
# Librarian context is problem/decl-centric (vs Strategist's goal-tree
# Context.md). Each work kind sees only what it needs:
#   dedup    — every proved decl + its statement (the audit surface)
#   classify — the kept (deduped) decls + their deps (the layout surface)
#   migrate  — the one target decl's original source + its dedup verdict


def _read_statement(conn, problem: str, slug: str) -> str:
    row = conn.execute(
        "SELECT statement FROM goals WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()
    return (row["statement"] if row else "") or ""


def compile_librarian_context(
    conn, *, problem: str, work_kind: str, attempts_dir,
    workspace, target_slug: str | None = None,
) -> "_Path":
    """Write attempts_dir/Context.md for a Librarian work spawn.

    `work_kind` ∈ {dedup, classify, migrate}. `target_slug` is required
    for migrate (the single decl to reshape)."""
    from ..quality.librarian import inventory as _inv

    lines: list[str] = [f"# Librarian — {work_kind} — {problem}", ""]

    if work_kind == "dedup":
        inv = _inv.build_inventory(conn, workspace, problem)
        lines.append(f"_{len(inv.decls)} proved declarations to audit._")
        lines.append("")
        if inv.defs_decls:
            lines.append("## Defs.lean declarations")
            for n in inv.defs_decls:
                lines.append(f"- `{n}`")
            lines.append("")
        lines.append("## Declarations (slug + statement)")
        lines.append("")
        for d in inv.decls:
            stmt = " ".join(_read_statement(conn, problem, d.slug).split())
            lines.append(f"### {d.slug}")
            lines.append(f"`{stmt}`" if stmt else "_(no statement)_")
            lines.append("")

    elif work_kind == "classify":
        kept = db.library_decls_for(conn, problem, lifecycle="deduped")
        lines.append(f"_{len(kept)} kept declarations to lay out._")
        lines.append("")
        inv = _inv.build_inventory(conn, workspace, problem)
        deps_by_slug = {d.slug: d.deps for d in inv.decls}
        lines.append("## Kept declarations (slug + deps + statement)")
        lines.append("")
        for r in kept:
            slug = r["slug"]
            deps = ", ".join(f"`{s}`" for s in deps_by_slug.get(slug, [])) \
                or "—"
            stmt = " ".join(_read_statement(conn, problem, slug).split())
            lines.append(f"### {slug}")
            lines.append(f"- deps: {deps}")
            lines.append(f"- `{stmt}`" if stmt else "- _(no statement)_")
            lines.append("")

    elif work_kind == "migrate":
        if not target_slug:
            raise ValueError("migrate work requires target_slug")
        row = conn.execute(
            "SELECT * FROM library_decls WHERE problem = ? AND slug = ?",
            (problem, target_slug),
        ).fetchone()
        lines.append(f"## Migrate `{target_slug}`")
        lines.append("")
        if row is not None:
            lines.append(f"- target file: `{row['target_file']}`")
            tn = row["target_name"]
            if tn:
                lines.append(f"- target name: `{tn}`")
            if row["verdict"] and row["verdict"] != "keep":
                lines.append(f"- dedup verdict: {row['verdict']} "
                             f"→ cite `{row['citation']}`")
            lines.append("")
        # Original source — the verbatim signature the agent must copy.
        src_path = None
        grow = conn.execute(
            "SELECT lean_path FROM goals WHERE problem = ? AND slug = ?",
            (problem, target_slug),
        ).fetchone()
        if grow and grow["lean_path"]:
            src_path = workspace / grow["lean_path"]
        lines.append("## Original source (copy the signature verbatim)")
        lines.append("")
        if src_path and src_path.exists():
            lines.append("```lean")
            lines.append(src_path.read_text(encoding="utf-8",
                                            errors="replace").rstrip())
            lines.append("```")
        else:
            lines.append("_(original source file not found)_")
        lines.append("")

    else:
        raise ValueError(f"unknown work_kind: {work_kind!r}")

    ctx = attempts_dir / "Context.md"
    ctx.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ctx


# ---------------------------------------------------------------------
# Stage D — run_librarian outer entry (work-kind dispatch)
# ---------------------------------------------------------------------
# dedup / classify: one-shot spawn -> parse -> verify -> commit (mirrors
#   strategist.run_strategist).
# migrate: LSP + session-retry loop (mirrors builder via
#   run_with_session_retries); commit gate = migrate_commit_gate.

WORK_KINDS: frozenset[str] = frozenset({"dedup", "classify", "migrate"})


def run_librarian(conn, *, problem: str, work_kind: str,
                  workspace, pipeline_id: str,
                  target_slug: str | None = None,
                  whitelist: "list[str] | None" = None):
    """Outer Librarian entry. Returns PipelineResult.

    `work_kind` selects the prompt (prompts/librarian/<kind>.md) and the
    commit path. `target_slug` is required for migrate. `whitelist` is the
    problem's authorized axiom set (Manifest `axioms_whitelist`, or the
    framework default) — threaded to the migrate commit gate's per-file
    axiom check; only the migrate kind uses it.

    `finish` is the terminal, agentless step (plan §4/§5): no prompt, no
    LLM — it records provenance into Library/INDEX.md and terminates the
    chain. Handled before the prompt-path so the missing-prompt guard
    doesn't reject it."""
    from . import PipelineResult, PROMPT_DIR
    from .. import agent

    if work_kind == "finish":
        return _run_finish(conn, problem=problem, workspace=workspace)

    if work_kind not in WORK_KINDS:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_bad_work_kind",
            failure_detail=f"unknown work_kind={work_kind!r}")

    prompt_path = PROMPT_DIR / "librarian" / f"{work_kind}.md"
    if not prompt_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="librarian_missing_prompt",
            failure_detail=str(prompt_path))

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)

    if work_kind == "migrate":
        return _run_migrate(
            conn, problem=problem, workspace=workspace,
            pipeline_id=pipeline_id, target_slug=target_slug,
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            prompt_path=prompt_path, whitelist=whitelist)
    return _run_structured(
        conn, problem=problem, work_kind=work_kind, workspace=workspace,
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        prompt_path=prompt_path)


def _run_structured(conn, *, problem, work_kind, workspace,
                    attempts_dir, problem_dir, prompt_path):
    """dedup / classify: one-shot spawn emitting plan.json, then parse +
    verify + commit (all-or-nothing). Mirrors run_strategist."""
    import uuid
    from . import PipelineResult
    from .. import agent
    from ..quality.librarian import inventory as _inv

    compile_librarian_context(
        conn, problem=problem, work_kind=work_kind,
        attempts_dir=attempts_dir, workspace=workspace)

    sid = str(uuid.uuid4())
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid)
    if rc != 0:
        return PipelineResult(
            outcome="failed", failure_reason="agent_error",
            failure_detail=f"agent rc={rc}")

    out_path = attempts_dir / "plan.json"
    if not out_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail="no plan.json")
    text = out_path.read_text(encoding="utf-8")

    if work_kind == "dedup":
        verdicts, err = parse_dedup(text)
        if err:
            return PipelineResult(outcome="failed",
                                  failure_reason="librarian_schema_invalid",
                                  failure_detail=err)
        inv = _inv.build_inventory(conn, workspace, problem)
        # Proved declarations AND Defs.lean decls — see dedup_slug_universe.
        slugs = dedup_slug_universe(inv)
        verr = verify_dedup(verdicts, slugs)
        if verr:
            return PipelineResult(outcome="failed",
                                  failure_reason="librarian_verify_failed",
                                  failure_detail=verr)
        for d in inv.decls:
            db.upsert_library_decl(conn, problem=problem, slug=d.slug,
                                   source_goal_id=d.goal_id)
        for name in inv.defs_decls:
            # Defs decls have no proof goal — source_goal_id is None.
            db.upsert_library_decl(conn, problem=problem, slug=name,
                                   source_goal_id=None)
        commit_dedup(conn, problem, verdicts)
        return PipelineResult(outcome="success")

    # classify
    plan, err = parse_classify(text)
    if err:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_schema_invalid",
                              failure_detail=err)
    kept = {r["slug"] for r in db.library_decls_for(conn, problem,
                                                    lifecycle="deduped")}
    verr = verify_classify(plan, kept)
    if verr:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_verify_failed",
                              failure_detail=verr)
    commit_classify(conn, problem, plan)
    return PipelineResult(outcome="success")


def _run_migrate(conn, *, problem, workspace, pipeline_id, target_slug,
                 attempts_dir, problem_dir, prompt_path, whitelist=None):
    """migrate: LSP + session-retry loop (mirrors builder). The agent
    writes patch.lean; on a clean spawn migrate_commit_gate decides, and
    on ok we copy to the target Library file + mark migrated."""
    import shutil
    from . import PipelineResult, _write_mcp_config
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import agent
    from ..core import dispatcher

    if not target_slug:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_bad_work_kind",
                              failure_detail="migrate requires target_slug")
    row = conn.execute(
        "SELECT * FROM library_decls WHERE problem = ? AND slug = ?",
        (problem, target_slug),
    ).fetchone()
    if row is None or row["lifecycle"] != "classified":
        return PipelineResult(
            outcome="failed", failure_reason="librarian_not_classified",
            failure_detail=f"{target_slug} not in 'classified' state")
    target_file = workspace / row["target_file"]
    patch_lean = attempts_dir / "patch.lean"

    def migrate_spawn(ctx: SpawnCtx) -> int:
        if ctx.cold:
            compile_librarian_context(
                conn, problem=problem, work_kind="migrate",
                attempts_dir=ctx.attempts_dir, workspace=workspace,
                target_slug=target_slug)
            patch_lean.write_text("", encoding="utf-8")
        mcp_config_path = _write_mcp_config(
            attempts_dir=ctx.attempts_dir, workspace=workspace,
            target=patch_lean, pipeline_id=pipeline_id, problem=problem)
        return agent.spawn_llm(
            kind="librarian", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=ctx.attempts_dir,
            session_id=ctx.sid, is_retry=not ctx.cold,
            retry_context=ctx.retry_context,
            mcp_config_path=mcp_config_path,
            inline_prompt=ctx.inline_prompt,
            timeout_sec_override=ctx.budget_override)

    def migrate_parse():
        # The migrate sandbox is exactly `patch.lean` (written on cold spawn,
        # edited in place via LSP). Read that one file — a glob + [0] would
        # pick a nondeterministic match if a stray patch*.lean lingered, and
        # could commit the wrong file into the Library.
        if not patch_lean.exists():
            return PipelineResult(outcome="failed",
                                  failure_reason="agent_no_output",
                                  failure_detail="no patch.lean")
        patch_text = patch_lean.read_text(encoding="utf-8")
        if "-- decline:" in patch_text:
            return PipelineResult(outcome="failed",
                                  failure_reason="agent_declined",
                                  failure_detail="migrate declined",
                                  proposal_md=patch_text)
        gate = migrate_commit_gate(patch_text, target_file,
                                   whitelist=whitelist, workspace=workspace)
        if not gate.ok:
            return PipelineResult(outcome="failed",
                                  failure_reason="librarian_gate_failed",
                                  failure_detail=gate.detail)
        # The Library decl's fully-qualified name — backfills target_name
        # (classify wrote it NULL) and is Gate D's rfl target.
        target_fq = extract_decl_fq_name(patch_text)
        from ..quality.librarian import inventory as _inv
        defs_names = _inv.defs_decls(workspace, problem)
        # Stage the file: Gate D's rfl probe imports the Library module,
        # so the target must be on disk. Roll back if Gate D rejects.
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(patch_lean, target_file)
        dgate = migrate_defeq_gate(
            patch_text, problem=problem, target_slug=target_slug,
            defs_decls=defs_names,
            target_module=_library_module_of(row["target_file"]),
            workspace=workspace)
        if not dgate.ok:
            try:
                target_file.unlink()
            except OSError:
                pass
            return PipelineResult(outcome="failed",
                                  failure_reason="librarian_gate_failed",
                                  failure_detail=dgate.detail,
                                  proposal_md=patch_text)
        db.mark_library_migrated(conn, problem=problem, slug=target_slug,
                                 target_name=target_fq)
        return PipelineResult(outcome="success")

    def migrate_postmortem(sid: str) -> None:
        pass  # librarian postmortem prompt optional; skip for now

    return run_with_session_retries(
        conn=conn, goal_id=None, pipeline_id=pipeline_id,
        budget_threshold=dispatcher.BUILDER_THRESHOLD,
        shelve_threshold=dispatcher.SHELVE_THRESHOLD,
        attempts_dir=attempts_dir,
        spawn_fn=migrate_spawn, parse_fn=migrate_parse,
        postmortem_fn=migrate_postmortem, workspace=workspace)


# ---------------------------------------------------------------------
# Stage E — finish (terminal, agentless): provenance + chain termination
# ---------------------------------------------------------------------

def _upsert_index_section(index_text: str, problem: str,
                          section_body: str) -> str:
    """Idempotently replace (or append) the `## <problem>` section in
    INDEX.md. A re-run of finish for the same problem rewrites its
    section in place rather than duplicating it. Sections are delimited
    by `## ` headers; the replaced span runs to the next `## ` (or EOF)."""
    header = f"## {problem}"
    lines = index_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == header:
            start = i
            break
    new_section = f"{header}\n\n{section_body.rstrip()}\n"
    if start is None:
        base = index_text.rstrip()
        prefix = (base + "\n\n") if base else _INDEX_PREAMBLE
        return prefix + new_section
    # Find end of this section (next top-level `## ` or EOF).
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    before = "\n".join(lines[:start]).rstrip()
    after = "\n".join(lines[end:]).strip()
    out = (before + "\n\n" if before else _INDEX_PREAMBLE) + new_section
    if after:
        out += "\n" + after + "\n"
    return out


_INDEX_PREAMBLE = (
    "# Library Index\n\n"
    "Provenance of declarations harvested from proved Problems, by "
    "source problem. Written by the Librarian `finish` step.\n\n"
)


def _run_finish(conn, *, problem: str, workspace):
    """Terminal Librarian step (plan §5): record migrated provenance into
    `Library/INDEX.md` and terminate the chain. Agentless, mechanical.

    INDEX presence is the idempotent 'finish done' marker the dispatcher's
    `_derive_librarian_work` reads — so this step MUST write INDEX even
    when the (deferred) live Gate B re-derivation is unavailable, else the
    `all-migrated → finish` derivation would re-enqueue forever.

    Live Gate B (`check_root_rederivation`) is deferred: it needs a
    Defs-free bridge `Root.lean` placed under the `Library/` lake source
    root (gateway `axiom_probe` compiles a dotted module), which is the
    same probe-file-staging design point logged as tech debt. Until that
    staging exists, the bridge is not built and Gate B is recorded as
    `deferred` rather than replicating the orphan-on-kill pattern."""
    from . import PipelineResult

    migrated = db.library_decls_for(conn, problem, lifecycle="migrated")
    if not migrated:
        # Nothing was harvested into the Library (e.g. dedup kept nothing,
        # everything cited/dropped). No provenance to record; clean no-op.
        return PipelineResult(outcome="success")

    lines = [f"_Harvested {db.now()} — {len(migrated)} declaration(s)._", ""]
    for r in migrated:
        name = r["target_name"] or r["slug"]
        target = r["target_file"] or "?"
        lines.append(f"- `{name}` → `{target}`")
    lines.append("")
    lines.append(
        "Gate B (root re-derivation): deferred — live `axiom_probe` "
        "needs a Defs-free bridge under the Library lake root "
        "(probe-file staging, see STATUS tech debt).")
    section = "\n".join(lines)

    index = workspace / "Library" / "INDEX.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    existing = (index.read_text(encoding="utf-8", errors="replace")
                if index.exists() else "")
    index.write_text(_upsert_index_section(existing, problem, section),
                     encoding="utf-8")
    return PipelineResult(outcome="success")
