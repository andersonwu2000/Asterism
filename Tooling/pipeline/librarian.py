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
  - commit_classify(conn, problem, plan, workspace)
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


def _toposort_intra_file(decls: list[str],
                         usage: "dict[str, set[str]]") -> list[str]:
    """Order one file's decls so each is emitted AFTER every same-file
    sibling it cites (Lean resolves names top-to-bottom). Stable Kahn: where
    usage doesn't force an order, the agent's original sequence is preserved
    (tie-break by original position). A cycle (shouldn't arise from a valid
    proof forest) leaves the offending decls in original order — the build
    gate then surfaces the unresolved reference honestly."""
    in_file = set(decls)
    pos = {s: i for i, s in enumerate(decls)}
    dep = {s: {u for u in usage.get(s, set()) if u in in_file and u != s}
           for s in decls}
    users: dict[str, list[str]] = {s: [] for s in decls}
    for s in decls:
        for u in dep[s]:
            users[u].append(s)
    indeg = {s: len(dep[s]) for s in decls}
    ready = sorted((s for s in decls if indeg[s] == 0), key=lambda s: pos[s])
    result: list[str] = []
    placed: set[str] = set()
    while ready:
        s = ready.pop(0)
        result.append(s)
        placed.add(s)
        newly = []
        for w in users[s]:
            indeg[w] -= 1
            if indeg[w] == 0:
                newly.append(w)
        if newly:
            ready = sorted(ready + newly, key=lambda s: pos[s])
    if len(result) != len(decls):           # cycle fallback
        result += [s for s in decls if s not in placed]
    return result


def commit_classify(conn, problem: str, plan: ClassifyPlan,
                    workspace) -> None:
    """Persist the layout plan: per decl, its target file + in-file order.
    Only `deduped` (kept) decls advance to `classified`. Each file's decls
    are topologically re-ordered by the USAGE DAG (proof-term citations,
    `inventory.usage_graph`) before `file_order` is assigned — the agent's
    layout is by meaning, but Lean needs a cited sibling to precede its user,
    so the persisted order must be a valid emission order."""
    from ..quality.librarian import inventory as _inv
    placed = [d for f in plan.files for d in f.decls]
    usage = _inv.usage_graph(workspace, problem, placed,
                             alias_map=_merge_alias_map(conn, problem))
    for f in plan.files:
        for order, slug in enumerate(_toposort_intra_file(f.decls, usage)):
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
            "class", "instance", "inductive")
_DECL_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(?:" + "|".join(_DECL_KW) + r")\s+([A-Za-z_][\w']*)")
_NS_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)")


# Decl-kind detector (Gate D must distinguish def/abbrev from nominal
# kinds, and per-file migrate maps each decl positionally). Reuses
# _DECL_KW; captures the keyword rather than the name.
_DECL_KW_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(def|abbrev|theorem|lemma|structure|class|inductive|instance)\b")

# Nominal kinds: two separate declarations are never definitionally equal
# even with identical fields, so `rfl` (Gate D) cannot equate them.
_NOMINAL_KINDS = ("structure", "class", "inductive")

# `end <ns>` closes a namespace opened by `namespace <ns>`.
_END_RE = re.compile(r"^\s*end\s+([A-Za-z_][\w.]*)")


@dataclass
class MigratedDecl:
    """A top-level declaration found in a migrate patch: its keyword
    (`def`/`theorem`/…), bare name, and namespace-qualified name."""
    kind: str | None
    name: str
    fq_name: str


def extract_decls(patch_text: str) -> "list[MigratedDecl]":
    """Every named top-level declaration in a patch, in source order.

    Per-file migrate pairs these positionally with the file's classified
    slugs (file_order) to backfill each `target_name`, run the per-decl
    axiom check, and drive Gate D. Tracks the open namespace(s) so each
    name is fully qualified; an `end <ns>` matching the innermost open
    namespace pops it, so multi-section files qualify correctly."""
    ns_stack: list[str] = []
    out: list[MigratedDecl] = []
    for line in patch_text.splitlines():
        m = _NS_RE.match(line)
        if m:
            ns_stack.append(m.group(1))
            continue
        me = _END_RE.match(line)
        if me and ns_stack and ns_stack[-1] == me.group(1):
            ns_stack.pop()
            continue
        m = _DECL_RE.match(line)
        if m:
            mk = _DECL_KW_RE.match(line)
            ns = ".".join(ns_stack)
            out.append(MigratedDecl(
                kind=mk.group(1) if mk else None, name=m.group(1),
                fq_name=f"{ns}.{m.group(1)}" if ns else m.group(1)))
    return out


def extract_decl_fq_name(patch_text: str) -> str | None:
    """The fully-qualified name of the FIRST named declaration in a patch
    (`<namespace>.<decl>`), or None when none is found. Convenience over
    `extract_decls` for single-decl callers (e.g. Gate D's fallback when
    no explicit name is supplied). The FQ name is namespace-derived, so it
    resolves under `#print axioms` regardless of the (temp) file name."""
    decls = extract_decls(patch_text)
    return decls[0].fq_name if decls else None


def extract_decl_kind(patch_text: str) -> str | None:
    """The keyword (`def` / `abbrev` / `theorem` / …) of the first named
    declaration in a patch, or None. Convenience over `extract_decls`."""
    decls = extract_decls(patch_text)
    return decls[0].kind if decls else None


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
    target_fq: "str | None" = None, kind: "str | None" = None,
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
    unit tests run gateway-free. `target_fq`/`kind` may be supplied
    explicitly (per-file migrate, where the patch holds several decls and
    the positional pairing already knows this slug's name and keyword); if
    omitted they fall back to the patch's first declaration (single-decl
    callers and tests)."""
    if target_slug not in defs_decls:
        return MigrateResult(True, "")
    if kind is None:
        kind = extract_decl_kind(patch_text)
    if kind in _NOMINAL_KINDS:
        return MigrateResult(
            False, f"Gate D: Defs decl `{target_slug}` is a {kind} "
                   "(nominal) — `rfl` cannot equate two separate "
                   "declarations; needs a verbatim special-case "
                   "(decline-and-flag).")
    if target_fq is None:
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
        # Per-file: every migrated declaration's transitive axioms must be
        # ⊆ whitelist — `build` alone accepts a file whose cited lemmas
        # carry a rogue axiom; only `#print axioms` walks the kernel graph.
        decls = extract_decls(patch_text)
        if not decls:
            return MigrateResult(
                False, "axiom check: no named declaration found "
                       "(anonymous or malformed patch)")
        if axiom_verifier is None:
            axiom_verifier = _warm_axiom_verifier(workspace)
        for d in decls:
            ok, detail = axiom_verifier(patch_text, d.fq_name, whitelist)
            if not ok:
                return MigrateResult(
                    False, f"axiom check failed for `{d.fq_name}`: {detail}")
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
# File-level dependency DAG (GAP 2 — reconstructed, no schema column)
# ---------------------------------------------------------------------
# classify computed the cross-file import DAG (ClassifyFile.imports,
# verify_classify checks acyclicity) but commit_classify drops it and
# library_decls has no imports column. migrate needs that DAG to (a) pick
# the next ready file in topological order and (b) tell the agent which
# sibling Library modules it may import. Rebuild it from per-decl deps
# (inventory / tree.py ground truth) + the slug→target_file mapping, so
# no schema migration is needed.


def _merge_alias_map(conn, problem: str) -> "dict[str, str]":
    """Each dedup-`merge` slug → its canonical placed slug, chains resolved
    to the final target. A proof that imports a merged-away sibling's
    `L_<Y>` resolves, in the migrated Library, to this canonical — so the
    usage DAG must remap Y→canonical or it loses the citation edge."""
    raw = {r["slug"]: r["citation"]
           for r in db.library_decls_for(conn, problem)
           if r["verdict"] == "merge" and r["citation"]}
    out: dict[str, str] = {}
    for s in raw:
        seen, cur = {s}, raw[s]
        while cur in raw and cur not in seen:
            seen.add(cur)
            cur = raw[cur]
        out[s] = cur
    return out


def file_dependency_graph(conn, *, problem: str,
                          workspace) -> "dict[str, set[str]]":
    """Map each placed Library file to the set of OTHER placed files it
    depends on. A file F depends on file G iff some decl in F uses (per the
    inventory dep graph) a decl placed in G. Only decls with a target_file
    (classified or migrated) participate; cited/dropped decls are terminal
    and never placed."""
    from ..quality.librarian import inventory as _inv
    rows = db.library_decls_for(conn, problem)
    file_of = {r["slug"]: r["target_file"] for r in rows
               if r["target_file"]
               and r["lifecycle"] in ("classified", "migrated")}
    # Cross-file edges follow the USAGE DAG (which lemma a proof term cites),
    # not the decomposition DAG (`InvDecl.deps`) — a file must migrate after
    # the files it actually references, else its imports don't resolve.
    usage = _inv.usage_graph(workspace, problem, file_of.keys(),
                             alias_map=_merge_alias_map(conn, problem))
    graph: "dict[str, set[str]]" = {f: set() for f in set(file_of.values())}
    for slug, f in file_of.items():
        for dep in usage.get(slug, set()):
            g = file_of.get(dep)
            if g and g != f:
                graph[f].add(g)
    return graph


def next_migrate_file(conn, *, problem: str, workspace) -> "str | None":
    """The next Library file ready to migrate: one with classified
    (not-yet-migrated) decls whose every dependency file is already
    migrated. Per-file migrate marks all of a file's decls 'migrated'
    together, so a file is either wholly classified or wholly migrated —
    'fully migrated' is just lifecycle=='migrated'. Ties broken by path so
    the chain is reproducible. Returns None when no classified decls
    remain. Falls back to the first classified file when none is ready —
    an acyclic DAG always has a ready file, so this only fires on a
    classify bug, and the build gate then surfaces the unresolved import
    honestly rather than the chain silently stalling."""
    rows = db.library_decls_for(conn, problem)
    classified = sorted({r["target_file"] for r in rows
                         if r["lifecycle"] == "classified"
                         and r["target_file"]})
    if not classified:
        return None
    migrated = {r["target_file"] for r in rows
                if r["lifecycle"] == "migrated" and r["target_file"]}
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    for f in classified:
        if all(dep in migrated for dep in graph.get(f, set())):
            return f
    return classified[0]


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
    workspace, target_file: str | None = None,
) -> "_Path":
    """Write attempts_dir/Context.md for a Librarian work spawn.

    `work_kind` ∈ {dedup, classify, migrate}. `target_file` is required
    for migrate (the Library file to write — its classified decls in
    file_order, plus the sibling modules it may import)."""
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
        if not target_file:
            raise ValueError("migrate work requires target_file")
        rows = [r for r in db.library_decls_for(conn, problem)
                if r["target_file"] == target_file
                and r["lifecycle"] == "classified"]
        rows.sort(key=lambda r: (r["file_order"]
                                 if r["file_order"] is not None else 0))
        target_module = _library_module_of(target_file)
        lines.append(f"## Migrate file `{target_file}`")
        lines.append("")
        lines.append(f"- module: `{target_module}`")
        # Derived sibling imports (GAP 2): the Library modules this file's
        # decls depend on — already migrated (topological order).
        graph = file_dependency_graph(conn, problem=problem,
                                      workspace=workspace)
        dep_files = sorted(graph.get(target_file, set()))
        if dep_files:
            lines.append("- sibling Library modules you may import:")
            for df in dep_files:
                lines.append(f"    - `{_library_module_of(df)}`")
        else:
            lines.append("- sibling Library modules you may import: "
                         "none (Mathlib only)")
        lines.append("")
        lines.append(f"_{len(rows)} declaration(s) to migrate, in this "
                     "exact order:_")
        lines.append("")
        defs_names = set(_inv.defs_decls(workspace, problem))
        # A Defs declaration's body is Gate-D-locked — show the verbatim
        # Defs.lean once so the agent reproduces it character for character.
        if any(r["slug"] in defs_names for r in rows):
            defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
            if defs_path.exists():
                lines.append("## Defs.lean (definitions are locked — "
                             "reproduce verbatim)")
                lines.append("")
                lines.append("```lean")
                lines.append(defs_path.read_text(
                    encoding="utf-8", errors="replace").rstrip())
                lines.append("```")
                lines.append("")
        lines.append("## Declarations")
        lines.append("")
        for i, r in enumerate(rows, 1):
            slug = r["slug"]
            lines.append(f"### {i}. `{slug}`")
            if r["verdict"] and r["verdict"] != "keep":
                lines.append(f"- dedup verdict: {r['verdict']} → cite "
                             f"`{r['citation']}`")
            if slug in defs_names:
                lines.append("- a Defs declaration — see the locked "
                             "Defs.lean above; reproduce its signature "
                             "and body.")
                lines.append("")
                continue
            stmt = " ".join(_read_statement(conn, problem, slug).split())
            lines.append("- statement (signature — copy verbatim):")
            lines.append(f"  `{stmt}`" if stmt else "  _(no statement)_")
            grow = conn.execute(
                "SELECT lean_path FROM goals WHERE problem = ? AND slug = ?",
                (problem, slug),
            ).fetchone()
            if grow and grow["lean_path"]:
                lines.append("- proof source (read for the body to port): "
                             f"`{grow['lean_path']}`")
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
                  target: str | None = None,
                  whitelist: "list[str] | None" = None):
    """Outer Librarian entry. Returns PipelineResult.

    `work_kind` selects the prompt (prompts/librarian/<kind>.md) and the
    commit path. `target` is required for migrate — the Library FILE to
    write (per-file is the parallel unit, plan §5 Step 3). `whitelist` is
    the problem's authorized axiom set (Manifest `axioms_whitelist`, or the
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
            pipeline_id=pipeline_id, target_file=target,
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
    commit_classify(conn, problem, plan, workspace)
    return PipelineResult(outcome="success")


def _normalize_stmt(s: "str | None") -> str:
    return " ".join((s or "").split())


# Decl head up to and including the name — its end is where the binders start.
_DECL_HEAD_RE = re.compile(
    r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(?:def|abbrev|theorem|lemma|instance)\s+[A-Za-z_][\w']*")


def _decl_signature(text: str) -> str:
    """The NAME-STRIPPED, whitespace-normalized signature (binders +
    conclusion type) of the first theorem/def in a proof file — everything
    from just after the decl name up to the proof body (`:= by`, or the last
    term-mode `:=`).

    Used to test whether a verbatim-merge pair is *callable-compatible*:
    `goals.statement` holds only the CONCLUSION, so two lemmas with the same
    conclusion but different binders (e.g. `..._of_sum_zero` taking an extra
    hypothesis) compare equal there yet have different argument lists — a
    citation rename then mis-positions call-site args (root cause 1). Comparing
    the full signature catches that and declines the rename to the LLM path."""
    m = _DECL_HEAD_RE.search(text)
    if not m:
        return ""
    region = text[m.end():]
    bym = re.search(r":=\s*by\b", region)
    cut = bym.start() if bym else None
    if cut is None:
        last = None
        for mm in re.finditer(r":=", region):
            last = mm
        cut = last.start() if last else len(region)
    return " ".join(region[:cut].split())


def _mechanical_migrate_file(
    conn, *, problem, workspace, target_file, target_module, rows,
) -> "str | None":
    """Try to relabel a whole classified file mechanically (librarian_plan
    §4 Phase 1) — no LLM. Returns the assembled file text on success, or
    None if any decl declines (caller falls through to the LLM path; the
    build gate downstream is still the final arbiter).

    Builds the three relabel inputs from DB state:
      - keep_slugs    : every `keep` decl (becomes a Library sibling)
      - defs_imports  : migrated Defs symbol → its Library module
      - citation_map  : verbatim-merge sibling → canonical (statement-equal
                        only; near-merge / drop / cite-mathlib are NOT here
                        and therefore decline → LLM path)
    """
    import re as _re
    from ..quality.librarian import inventory as _inv
    from ..quality.librarian import relabel as _relabel

    all_rows = db.library_decls_for(conn, problem)
    keep_slugs = {r["slug"] for r in all_rows if r["verdict"] == "keep"}
    all_defs = set(_inv.defs_decls(workspace, problem))

    # sibling_modules: keep-slug → its Library module. A cross-file sibling
    # reference needs `import <mod>` + `open <mod>` (different namespace).
    # Only slugs with a known target_file participate; a keep sibling not
    # yet classified has no module → relabel declines that file to LLM.
    sibling_modules: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "keep" and r["target_file"]:
            sibling_modules[r["slug"]] = _library_module_of(r["target_file"])

    # defs_imports: a Defs symbol that has been migrated → its Library module.
    defs_imports: dict[str, str] = {}
    for r in all_rows:
        if r["slug"] in all_defs and r["lifecycle"] == "migrated" \
                and r["target_file"]:
            defs_imports[r["slug"]] = _library_module_of(r["target_file"])

    pns = f"Problems.{problem}"
    problem_dir = db.problem_dir(workspace, problem)
    proofs = problem_dir / "proofs"

    # citation_map: verbatim-merge → canonical sibling. A merge is only safe
    # to rename mechanically when slug and canonical share the SAME callable
    # signature (binders + conclusion), not just the same conclusion: dedup's
    # verbatim compares `goals.statement` (conclusion only), so a `merge` whose
    # canonical takes a different binder list would mis-position call-site args
    # on rename (root cause 1). We re-check the full signature from the proof
    # files here; any mismatch / missing file declines that decl to the LLM.
    def _full_sig(slug):
        p = proofs / f"L_{slug}.lean"
        if not p.exists():
            return None
        return _decl_signature(p.read_text(encoding="utf-8"))
    citation_map: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "merge" and r["citation"]:
            sig1, sig2 = _full_sig(r["slug"]), _full_sig(r["citation"])
            if sig1 and sig2 and sig1 == sig2:
                citation_map[r["slug"]] = r["citation"]
    alias_re = _re.compile(
        r"def\s+\w+\s*:=\s*@?Problems\.[\w.]+\.(s\d+)")

    import_set: set[str] = set()
    open_set: set[str] = set()
    chunks: list[str] = []
    for r in rows:
        slug = r["slug"]
        src_path = proofs / f"L_{slug}.lean"
        if not src_path.exists():
            return None  # Defs decl / no proof file — not this path
        src = src_path.read_text(encoding="utf-8")
        kw = dict(problem_namespace=pns, target_namespace=target_module,
                  keep_slugs=keep_slugs, defs_imports=defs_imports,
                  all_defs_syms=all_defs, citation_map=citation_map,
                  sibling_modules=sibling_modules)
        m = alias_re.search(src)
        if m:
            strat_path = proofs / f"_strategy_{m.group(1)}.lean"
            if not strat_path.exists():
                return None
            res = _relabel.inline_alias(
                src, strat_path.read_text(encoding="utf-8"), slug=slug, **kw)
        else:
            res = _relabel.relabel_self_contained(src, **kw)
        if not res.ok:
            return None  # any decline → whole file goes to the LLM path
        # Split into imports + open lines + the namespace body, to merge
        # all decls into one file (imports + opens hoisted, dedup'd).
        inside = False
        body: list[str] = []
        for ln in res.text.splitlines():
            if ln.startswith("import "):
                import_set.add(ln)
                continue
            if ln.startswith("open "):
                open_set.add(ln)
                continue
            if ln.startswith(f"namespace {target_module}"):
                inside = True
                continue
            if ln.startswith(f"end {target_module}"):
                inside = False
                continue
            if inside:
                body.append(ln)
        chunks.append("\n".join(body).strip("\n"))

    header = "\n".join(sorted(import_set))
    if open_set:
        header += "\n\n" + "\n".join(sorted(open_set))
    return (header
            + f"\n\nnamespace {target_module}\n\n"
            + "\n\n".join(chunks)
            + f"\n\nend {target_module}\n")


def _commit_migrated_file(
    patch_text, *, conn, problem, workspace, target_path, target_module,
    ordered_slugs, defs_names, whitelist,
    build_verifier=None, axiom_verifier=None, defeq_verifier=None):
    """Validate a whole-file migrate candidate and, on success, commit it
    (write the file + mark every decl migrated). Shared by both the LLM
    path (migrate_parse) and the mechanical relabel pre-pass, so the
    commit contract is single-sourced — no two-implementation drift.

    Returns a PipelineResult. The verifier args are injectable for offline
    tests; production passes None → real warm-gateway probes.
    """
    from . import PipelineResult

    # Gate A import-closure + whole-file build + per-decl axiom check.
    gate = migrate_commit_gate(patch_text, target_path, whitelist=whitelist,
                               workspace=workspace,
                               build_verifier=build_verifier,
                               axiom_verifier=axiom_verifier)
    if not gate.ok:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_gate_failed",
                              failure_detail=gate.detail,
                              proposal_md=patch_text)
    # Positional slug ↔ declaration pairing (migrate.md mandates exactly
    # the listed decls, in order). A mismatch breaks target_name backfill
    # and Gate D — fail with a clear, retryable message.
    decls = extract_decls(patch_text)
    if len(decls) != len(ordered_slugs):
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=(
                f"file declares {len(decls)} top-level declaration(s) "
                f"but {len(ordered_slugs)} were classified into it "
                f"({ordered_slugs}); emit exactly the listed "
                "declarations, in order"),
            proposal_md=patch_text)
    # Stage the whole file: Gate D's rfl probe imports the module, so the
    # target must be on disk. Roll back if any decl's Gate D rejects.
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(patch_text)
    for slug, decl in zip(ordered_slugs, decls):
        dgate = migrate_defeq_gate(
            patch_text, problem=problem, target_slug=slug,
            defs_decls=defs_names, target_module=target_module,
            target_fq=decl.fq_name, kind=decl.kind, workspace=workspace,
            defeq_verifier=defeq_verifier)
        if not dgate.ok:
            try:
                target_path.unlink()
            except OSError:
                pass
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail=f"{slug}: {dgate.detail}",
                proposal_md=patch_text)
    # All gates passed — advance every decl to 'migrated', backfilling each
    # one's fully-qualified Library name (classify wrote it NULL).
    for slug, decl in zip(ordered_slugs, decls):
        db.mark_library_migrated(conn, problem=problem, slug=slug,
                                 target_name=decl.fq_name)
    return PipelineResult(outcome="success")


def _run_migrate(conn, *, problem, workspace, pipeline_id, target_file,
                 attempts_dir, problem_dir, prompt_path, whitelist=None):
    """migrate (per-file, plan §5 Step 3): one agent writes the whole
    Library file holding that file's classified decls (in file_order). The
    commit gate builds the whole file once + checks every decl's axioms,
    Gate D rfl-checks each migrated `def`, and all the file's decls advance
    to 'migrated' together. LSP + session-retry loop mirrors Builder."""
    from . import PipelineResult, _write_mcp_config
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import agent
    from ..core import dispatcher
    from ..quality.librarian import inventory as _inv

    if not target_file:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_bad_work_kind",
                              failure_detail="migrate requires target_file")
    rows = [r for r in db.library_decls_for(conn, problem)
            if r["target_file"] == target_file
            and r["lifecycle"] == "classified"]
    if not rows:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_not_classified",
            failure_detail=f"{target_file}: no classified decls")
    rows.sort(key=lambda r: (r["file_order"]
                             if r["file_order"] is not None else 0))
    ordered_slugs = [r["slug"] for r in rows]
    target_path = workspace / target_file
    target_module = _library_module_of(target_file)
    defs_names = _inv.defs_decls(workspace, problem)
    patch_lean = attempts_dir / "patch.lean"

    # Phase 1 — mechanical relabel pre-pass (librarian_plan §4). Try to
    # build the whole file by pure relabel (no LLM); if it assembles AND
    # passes the same commit gate, we're done with zero spawn. Any decline
    # or gate failure falls through to the LLM path below unchanged.
    mech_text = _mechanical_migrate_file(
        conn, problem=problem, workspace=workspace, target_file=target_file,
        target_module=target_module, rows=rows)
    if mech_text is not None:
        mech_res = _commit_migrated_file(
            mech_text, conn=conn, problem=problem, workspace=workspace,
            target_path=target_path, target_module=target_module,
            ordered_slugs=ordered_slugs, defs_names=defs_names,
            whitelist=whitelist)
        if mech_res.outcome == "success":
            print(f"[librarian] {target_file}: migrated mechanically "
                  f"(Phase 1, {len(ordered_slugs)} decls, no LLM)",
                  flush=True)
            return mech_res
        # Sanitize before print: Lean diagnostics carry unicode (e.g. `✝`,
        # `⊢`) that a cp950/legacy console can't encode — an unsanitized
        # print raises UnicodeEncodeError and aborts the pipeline. Keep the
        # framework's own logging ASCII-safe.
        _detail = (mech_res.failure_detail or "")[:120].encode(
            "ascii", "replace").decode("ascii")
        print(f"[librarian] {target_file}: mechanical relabel assembled but "
              f"gate failed ({_detail}); falling through to LLM", flush=True)

    def migrate_spawn(ctx: SpawnCtx) -> int:
        if ctx.cold:
            compile_librarian_context(
                conn, problem=problem, work_kind="migrate",
                attempts_dir=ctx.attempts_dir, workspace=workspace,
                target_file=target_file)
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
        return _commit_migrated_file(
            patch_text, conn=conn, problem=problem, workspace=workspace,
            target_path=target_path, target_module=target_module,
            ordered_slugs=ordered_slugs, defs_names=defs_names,
            whitelist=whitelist)

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
