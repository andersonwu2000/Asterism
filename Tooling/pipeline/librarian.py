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
from typing import NamedTuple

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


def _merge_file_sccs(fgraph: dict, decls_in: dict) -> dict:
    """Collapse each strongly-connected component of the file-usage graph to
    one canonical file. A set of files that (transitively) import each other
    is physically un-splittable across Lean modules — leaving them apart is a
    circular import that can't be topologically ordered or built. The SCC's
    decls all belong in ONE file. Returns {file_path: canonical_path}; a file
    not in a multi-file SCC maps to itself. Canonical = the member with the
    most decls (lexicographic tie-break), for a deterministic choice."""
    nodes = list(fgraph)
    reach: dict = {n: set() for n in nodes}
    for n in nodes:
        stack = list(fgraph.get(n, ()))
        while stack:
            m = stack.pop()
            if m not in reach[n]:
                reach[n].add(m)
                stack.extend(fgraph.get(m, ()))
    canon: dict = {}
    seen: set = set()
    for n in nodes:
        if n in seen:
            continue
        comp = {n} | {m for m in nodes if m in reach[n] and n in reach[m]}
        seen |= comp
        if len(comp) > 1:
            rep = sorted(comp, key=lambda p: (-len(decls_in.get(p, [])), p))[0]
            for m in comp:
                canon[m] = rep
    return canon


def commit_classify(conn, problem: str, plan: ClassifyPlan,
                    workspace) -> None:
    """Persist the layout plan: per decl, its target file + in-file order.
    Only `deduped` (kept) decls advance to `classified`.

    Two corrections to the agent's layout, both driven by the ground-truth
    USAGE DAG (proof-term citations, `inventory.usage_graph`), since the
    agent lays out by meaning but Lean is import-/order-sensitive:
      - files whose decls form a usage cycle are merged into one file (an SCC
        is an un-splittable circular import — `_merge_file_sccs`);
      - within each (possibly merged) file, decls are topologically reordered
        so a cited sibling precedes its user.
    """
    from ..quality.librarian import inventory as _inv
    placed = [d for f in plan.files for d in f.decls]
    usage = _inv.usage_graph(workspace, problem, placed,
                             alias_map=_merge_alias_map(conn, problem),
                             root_source=_root_source(conn, problem, workspace))
    # File-level usage graph: file F depends on file G iff a decl in F cites a
    # decl placed in G. Merge cyclic file groups (circular imports) into one.
    decl_file = {d: f.path for f in plan.files for d in f.decls}
    decls_in = {f.path: list(f.decls) for f in plan.files}
    fgraph: dict = {f.path: set() for f in plan.files}
    for d, deps in usage.items():
        fa = decl_file.get(d)
        for dep in deps:
            fb = decl_file.get(dep)
            if fa and fb and fa != fb:
                fgraph[fa].add(fb)
    canon = _merge_file_sccs(fgraph, decls_in)
    if canon:
        for orig, rep in sorted(canon.items()):
            if orig != rep:
                print(f"[librarian] classify: merging cyclic file {orig} -> "
                      f"{rep} (un-splittable usage SCC)", flush=True)
    # Regroup decls under their canonical file (SCC members merged), keeping
    # the agent's intra-group order before the usage toposort.
    merged: dict = {}
    for f in plan.files:
        merged.setdefault(canon.get(f.path, f.path), []).extend(f.decls)
    for cf, decls in merged.items():
        for order, slug in enumerate(_toposort_intra_file(decls, usage)):
            db.set_library_classification(
                conn, problem=problem, slug=slug,
                target_file=cf, target_name=None, file_order=order)


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


def _uses_sorry(text: str) -> bool:
    """True iff `text` actually USES the `sorry` term/tactic — ignoring
    comments. A `--` line comment or `/- … -/` (incl. `/-- … -/` doc) comment
    may legitimately contain the word 'sorry' (e.g. a note 'Builds sorry-free'),
    which a naive `"sorry" in text` substring check wrongly flags. The kernel
    axiom probe (sorryAx ∉ whitelist) is the authoritative detector; this is a
    fast, clear pre-check, so a comment-stripped word-boundary scan suffices.
    `sorry` as an identifier prefix (`sorry_free`) is safe — `_` is a word char,
    so `\\bsorry\\b` won't match it."""
    import re as _r
    no_block = _r.sub(r"/-.*?-/", " ", text, flags=_r.DOTALL)  # /- … -/, /-- -/
    no_line = _r.sub(r"--[^\n]*", " ", no_block)               # -- line comments
    return bool(_r.search(r"\bsorry\b", no_line))


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

    if _uses_sorry(patch_text):
        # Cheap pre-check (comment-aware; the kernel axiom probe below is the
        # authoritative sorryAx detector). A clear message here beats a generic
        # "declaration uses sorry" diagnostic.
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


def _warm_olean_writer(workspace):
    """Default olean_writer: build the committed Library file and persist its
    `.olean` (write_olean=True), so a later-dispatched importer builds against
    a FRESH dependency olean — proof-time does the same per proved lemma
    (builder.py). The gateway's `lake serve` imports deps from on-disk oleans
    and does NOT rebuild stale ones, so without this every cross-file build
    (migrate / cleanup re-gate / bridge) risks a stale dependency (R1b)."""
    def _write(target_path) -> tuple[bool, str]:
        from ..lsp import lifecycle as gateway_lifecycle
        ws = workspace or _Path(".")
        r = gateway_lifecycle.verify_file(
            target_path, write_olean=True, workspace=ws)
        if r.get("error"):
            return False, f"olean write infra error: {r['error']}"
        if not r.get("ok"):
            errs = "; ".join(
                d.get("message", "")[:120]
                for d in (r.get("diagnostics") or [])
                if d.get("severity") == "error")[:300]
            return False, errs or "(build failed on olean write)"
        if not r.get("olean_written"):
            return False, "olean not written"
        return True, ""
    return _write


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


def _root_source(conn, problem, workspace) -> "tuple[str, str] | None":
    """(root_slug, abs_path) for the problem's proved root decl, whose proof
    lives in Root.lean (its lean_path), not proofs/L_<slug>.lean — so the
    usage / reference scanners read the root's sibling citations from the
    right file instead of seeing it as dependency-free."""
    r = conn.execute(
        "SELECT slug, lean_path FROM goals WHERE problem = ? "
        "AND origin = 'root' AND status = 'proved' ORDER BY id LIMIT 1",
        (problem,)).fetchone()
    if r and r["lean_path"]:
        return (r["slug"], str(workspace / r["lean_path"]))
    return None


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
                             alias_map=_merge_alias_map(conn, problem),
                             root_source=_root_source(conn, problem, workspace))
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


def next_cleanup_file(conn, *, problem: str) -> "str | None":
    """The next Library file to clean (Step 4): one with 'migrated' (not yet
    'cleaned') decls. Cleanup re-gates touched files itself, so order only
    needs to be stable — ties broken by path. Returns None when every
    migrated decl is cleaned (the chain moves on to bridge)."""
    rows = db.library_decls_for(conn, problem)
    migrated = sorted({r["target_file"] for r in rows
                       if r["lifecycle"] == "migrated" and r["target_file"]})
    return migrated[0] if migrated else None


def file_work_kind(conn, *, problem: str, target_file: str) -> "str | None":
    """The current step for ONE Library file (#92 per-file unit dispatch).
    v0.3 (plan §3): 'migrate' if the file still has `classified` decls, else
    None — a wholly `migrated` file is done (cleanup removed; the whole-problem
    bridge follows once every file is migrated)."""
    ls = {r["lifecycle"] for r in db.library_decls_for(conn, problem)
          if r["target_file"] == target_file}
    if "classified" in ls:
        return "migrate"
    return None


def ready_file_work(conn, *, problem: str, workspace,
                    in_flight: "set[str] | tuple" = ()) -> "list[tuple[str, str]]":
    """The set of Library FILES dispatchable RIGHT NOW as independent migrate
    units (#92 dynamic file pipeline), each as `('migrate', target_file)`:

      - f's decls are still `classified` AND every file f depends on is already
        `migrated` (importable). A file migrates against its deps' migrated
        (original-signature) form — consistent with the original proofs.

    v0.3 (plan §3): cleanup is removed, so migrate is the only per-file work;
    a wholly `migrated` file is done (the whole-problem bridge follows once all
    files are migrated). `done = migrated` is the readiness currency. Files in
    `in_flight` are excluded; order-stable by path so independent files run
    concurrently in the pool.
    """
    from collections import defaultdict
    in_flight = set(in_flight)
    rows = db.library_decls_for(conn, problem)
    by_file: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["target_file"] and r["lifecycle"] in ("classified", "migrated"):
            by_file[r["target_file"]].append(r)

    def _phase(rs) -> str:
        # Least-advanced lifecycle present — defensive against a half-moved
        # file (treat as the earlier stage; never double-dispatch).
        ls = {r["lifecycle"] for r in rs}
        return "classified" if "classified" in ls else "migrated"

    phase = {f: _phase(rs) for f, rs in by_file.items()}
    migrated = {f for f, ph in phase.items() if ph == "migrated"}
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    work: list[tuple[str, str]] = []
    for f in sorted(phase):
        if f in in_flight:
            continue
        if phase[f] == "classified" and all(
                dep in migrated for dep in graph.get(f, set())):
            work.append(("migrate", f))
    return work


def _harvested_decls(conn, problem: str) -> list:
    """Decls actually placed in the Library — 'migrated' (pre-cleanup) plus
    'cleaned' (Step 4 done). The set bridge re-derives against and INDEX
    records, robust to whether cleanup has run."""
    return [r for r in db.library_decls_for(conn, problem)
            if r["lifecycle"] in ("migrated", "cleaned")]


def _problem_library_files(conn, problem: str) -> "set[str]":
    """Every Library file holding a placed (migrated/cleaned) decl of this
    problem — the set the cleanup re-gate snapshots and re-verifies."""
    return {r["target_file"] for r in db.library_decls_for(conn, problem)
            if r["target_file"]
            and r["lifecycle"] in ("migrated", "cleaned")}


def _importers_of(conn, *, problem, workspace, files: "set[str]") -> "set[str]":
    """Files that import any file in `files` (reverse of the usage DAG) —
    cleanup must re-build these too: a signature change in F breaks any G
    that calls into F."""
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    out: set[str] = set()
    for g, deps in graph.items():
        if deps & files:
            out.add(g)
    return out


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


def _strategy_proofs_of(workspace, lean_path_rel: str) -> "list[str]":
    """Workspace-relative paths of the `_strategy_s<N>.lean` files that a goal's
    `L_<slug>.lean` (at `lean_path_rel`) imports — the files holding the ACTUAL
    tactic proof (the `def := @…sN` alias / thin `theorem … := by exact sN`
    wrapper just points there). Lets a hole's context point past the one-line
    alias to the real proof to port. Best-effort: empty if missing / no strategy
    import."""
    import re as _re
    from pathlib import Path as _Path
    p = workspace / lean_path_rel
    if not p.exists():
        return []
    proofs_rel = _Path(lean_path_rel).parent
    rx = _re.compile(r"import\s+Problems\.[\w.]+\.proofs\.(_strategy_s\d+)\b")
    out: list[str] = []
    for m in rx.finditer(p.read_text(encoding="utf-8", errors="replace")):
        sp = (proofs_rel / f"{m.group(1)}.lean").as_posix()
        if (workspace / sp).exists() and sp not in out:
            out.append(sp)
    return out


def compile_librarian_context(
    conn, *, problem: str, work_kind: str, attempts_dir,
    workspace, target_file: str | None = None,
    holes: "list[str] | None" = None,
    solo_hole: "str | None" = None,
) -> "_Path":
    """Write attempts_dir/Context.md for a Librarian work spawn.

    `work_kind` ∈ {dedup, classify, migrate}. `target_file` is required
    for migrate (the Library file to write — its classified decls in
    file_order, plus the sibling modules it may import).

    `holes` (migrate only, seed mode): when non-None, `patch.lean` is
    pre-seeded with a mechanically-relabelled draft and the agent's job is
    to finish it, not write it. A non-empty list names the decls left as
    `sorry` holes to fill; an empty list means the draft is complete but
    build-failed (fix it). When None, the agent writes the file from
    scratch (cold)."""
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
        hole_set = set(holes or [])
        if solo_hole is not None:
            # Incremental per-decl mode (#87): patch.lean is a ONE-declaration
            # seed that imports the decls migrated into this file so far + the
            # sibling modules. The agent finishes just that one declaration.
            lines.append("## Finish one declaration")
            lines.append("")
            lines.append(
                f"`patch.lean` imports the declarations already migrated into "
                f"this file plus the sibling modules, then holds the single "
                f"declaration `{solo_hole}` (marked ⛏ FILL THIS below) with a "
                f"`sorry` body. **Finish exactly that one declaration** — refer "
                f"to the imported siblings by name, don't restate them. Keep "
                f"its signature verbatim unless it is flagged a signature hole "
                f"below (then restate it Defs-free).")
            lines.append("")
        elif holes is not None:
            # Whole-file seed (no live caller after the #87 incremental
            # rework; kept for the agentless / manual fallback): finish a
            # mechanically-relabelled draft in place, don't rewrite it.
            lines.append("## You are given a seed — finish it, don't rewrite")
            lines.append("")
            lines.append(
                "`patch.lean` is pre-filled with a mechanically-relabelled "
                "draft of this whole file: namespaces, imports and every "
                "non-hole declaration are already correct. **Do not rewrite "
                "the working declarations or change their signatures.**")
            lines.append("")
            if hole_set:
                lines.append(
                    f"Fill the **{len(hole_set)} `sorry` hole(s)** below "
                    "(marked ⛏), keeping each signature exactly as seeded:")
                for h in holes:
                    lines.append(f"  - `{h}`")
            else:
                lines.append(
                    "The draft is complete but does not build — fix the "
                    "build error(s) without weakening any signature.")
            lines.append("")
        lines.append("## Declarations")
        lines.append("")
        # Precompute proof-term references (raw, per slug), dedup verdicts, and
        # goal proof paths once: a hole gets handed (a) its real proof source
        # (alias resolved to the `_strategy_s<N>.lean` holding the tactic body)
        # and (b) the proofs of any sibling dedup'd INTO it, which it must
        # inline — not just a name to rediscover. Reused by the redirect table.
        ref = _inv.referenced_slugs(
            workspace, problem, [r["slug"] for r in rows],
            root_source=_root_source(conn, problem, workspace))
        by_slug = {r["slug"]: r for r in db.library_decls_for(conn, problem)}
        lean_paths = {
            row["slug"]: row["lean_path"]
            for row in conn.execute(
                "SELECT slug, lean_path FROM goals WHERE problem = ?",
                (problem,)).fetchall()}
        for i, r in enumerate(rows, 1):
            slug = r["slug"]
            is_hole = (slug == solo_hole
                       or (solo_hole is None and slug in hole_set))
            if slug == solo_hole:
                tag = " ⛏ FILL THIS"
            elif solo_hole is None and slug in hole_set:
                tag = " ⛏ HOLE — fill this"
            else:
                tag = ""
            lines.append(f"### {i}. `{slug}`{tag}")
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
            lp = lean_paths.get(slug)
            if lp:
                lines.append("- proof source (read for the body to port): "
                             f"`{lp}`")
                # The L_<slug>.lean is a thin alias/wrapper; the real tactic
                # proof lives in the `_strategy_s<N>.lean` it imports.
                for sp in _strategy_proofs_of(workspace, lp):
                    lines.append(f"    - actual proof body: `{sp}`")
            # Holes only: surface the proofs of siblings dedup'd INTO this decl
            # (merge / drop, no Library home). The hole exists to ABSORB them,
            # so the agent must INLINE their proofs — hand over the sources
            # instead of making it discover the drop and hunt the files.
            if is_hole:
                absorbed = []
                for dep in sorted(ref.get(slug, set())):
                    drow = by_slug.get(dep)
                    if (drow and drow["verdict"] in ("merge", "drop")
                            and not drow["target_file"]):
                        absorbed.append((dep, drow["verdict"]))
                if absorbed:
                    lines.append(
                        "- absorbed siblings (dedup'd into this decl — they have "
                        "no Library home, so inline their proofs):")
                    for dep, verdict in absorbed:
                        dlp = lean_paths.get(dep)
                        loc = f" — proof: `{dlp}`" if dlp else ""
                        for sp in (_strategy_proofs_of(workspace, dlp)
                                   if dlp else []):
                            loc += f", body: `{sp}`"
                        lines.append(f"    - `{dep}` ({verdict}){loc}")
            lines.append("")
        # Redirect table (G3): non-keep siblings these decls cite + what to
        # replace each with (reuses `ref` / `by_slug` precomputed above). A
        # `sorry`-hole body that referenced a merged / dropped / cited sibling
        # must use the canonical / mathlib / Library name instead.
        all_refs: set[str] = set().union(*ref.values()) if ref else set()
        redirects = [
            (s, by_slug[s]["verdict"], by_slug[s]["citation"])
            for s in sorted(all_refs)
            if s in by_slug and by_slug[s]["citation"]
            and by_slug[s]["verdict"] in (
                "merge", "drop", "cite-mathlib", "cite-library")]
        if redirects:
            lines.append("## Sibling redirects (a referenced sibling was not "
                         "kept — use the replacement)")
            lines.append("")
            for s, verdict, cit in redirects:
                lines.append(f"- `{s}` → `{cit}`  ({verdict})")
            lines.append("")

    elif work_kind == "cleanup":
        if not target_file:
            raise ValueError("cleanup work requires target_file")
        target_module = _library_module_of(target_file)
        decls = [r for r in db.library_decls_for(conn, problem)
                 if r["target_file"] == target_file
                 and r["lifecycle"] == "migrated"]
        lines.append(f"## Clean up `{target_file}` for mathlib PR")
        lines.append("")
        lines.append(f"- module: `{target_module}`")
        lines.append("- edit this file **in place** (LSP holds it); follow "
                     "`docs/internal/mathlib_conventions.md`.")
        lines.append("- goals: remove every **unused hypothesis** "
                     "(`linter.unusedVariables`), factor shared binders into "
                     "`variable`, add a `/-! … -/` module docstring. Keep each "
                     "`/-- … -/` decl docstring.")
        lines.append("- **do NOT weaken any statement's meaning** — only drop "
                     "genuinely unused binders. The root re-derivation (Gate "
                     "B) re-checks the whole Library afterwards.")
        lines.append("")
        # Call sites: files importing this one must be updated if a signature
        # changes (removing a hyp). List them so the agent edits them too.
        graph = file_dependency_graph(conn, problem=problem,
                                      workspace=workspace)
        importers = sorted(g for g, deps in graph.items()
                           if target_file in deps)
        if importers:
            lines.append("- **call sites to update if you change a signature** "
                         "(edit these files too, via Edit):")
            for g in importers:
                lines.append(f"    - `{g}`")
            lines.append("")
        # Re-open constraints: if a decl here was reopened because a downstream
        # needed it reshaped, surface what was needed so this re-cleanup
        # produces a DIFFERENT result than the one that was rejected.
        reopened = [r for r in decls if r["reopen_note"]]
        if reopened:
            lines.append("## ⚠️ Reshape constraints (a downstream needs these)")
            lines.append("")
            for r in reopened:
                lines.append(f"- `{r['target_name'] or r['slug']}`: "
                             f"{r['reopen_note']}")
            lines.append("")
        lines.append(f"## Declarations in this file ({len(decls)})")
        lines.append("")
        for r in decls:
            lines.append(f"- `{r['target_name'] or r['slug']}`")
        lines.append("")
        lines.append("If the file genuinely cannot be cleaned (e.g. a "
                     "hypothesis looks unused but removing it breaks a proof), "
                     "write `-- decline: <reason>` to `patch.lean`.")

    elif work_kind == "bridge":
        # Gate B: re-derive the original root `theorem main` from the Library.
        root = conn.execute(
            "SELECT slug, statement FROM goals WHERE problem = ? AND "
            "origin = 'root' AND status = 'proved' ORDER BY id LIMIT 1",
            (problem,)).fetchone()
        stmt = " ".join((root["statement"] if root else "").split())
        lines.append("## Re-derive the original root from the Library")
        lines.append("")
        lines.append("- original statement (prove this **verbatim** as "
                     "`theorem main : <statement>`):")
        lines.append(f"  `{stmt}`" if stmt else "  _(no root statement)_")
        lines.append("")
        # Keystone candidates: the placed forms of the decls the root's
        # winning strategy used directly — the most likely one-liner.
        migrated = {r["slug"]: r for r in _harvested_decls(conn, problem)}
        inv = _inv.build_inventory(conn, workspace, problem)
        root_deps = next((d.deps for d in inv.decls
                          if d.origin == "root"), [])
        keystones = [migrated[s] for s in root_deps if s in migrated]
        if keystones:
            lines.append("- likely keystone(s) (migrated form of what the "
                         "original proof used):")
            for r in keystones:
                lines.append(f"    - `{r['target_name'] or r['slug']}` "
                             f"(`{r['target_file']}`)")
            lines.append("")
        lines.append(f"## Library declarations from this problem "
                     f"({len(migrated)})")
        lines.append("")
        for r in migrated.values():
            lines.append(f"- `{r['target_name'] or r['slug']}` "
                         f"→ `{r['target_file']}`")

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

WORK_KINDS: frozenset[str] = frozenset(
    {"dedup", "classify", "migrate", "cleanup", "bridge"})


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

    # v0.3 (plan §0/§3): dedup is no longer an agentic keep/drop judgment —
    # it is a mechanical "inventory + keep everything" step (no spawn, no
    # prompt). Keeping all decls is precisely what lets migrate be mechanical
    # (every proof-term reference resolves to a kept sibling → no holes → no
    # LLM). Routed before the prompt-path guard, like `finish`.
    if work_kind == "dedup":
        return _run_keepall(conn, problem=problem, workspace=workspace)

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
    if work_kind == "cleanup":
        return _run_cleanup(
            conn, problem=problem, workspace=workspace,
            pipeline_id=pipeline_id, target_file=target,
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            prompt_path=prompt_path, whitelist=whitelist)
    if work_kind == "bridge":
        return _run_bridge(
            conn, problem=problem, workspace=workspace,
            pipeline_id=pipeline_id, attempts_dir=attempts_dir,
            problem_dir=problem_dir, prompt_path=prompt_path,
            whitelist=whitelist)
    return _run_structured(
        conn, problem=problem, work_kind=work_kind, workspace=workspace,
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        prompt_path=prompt_path)


def _reachable_from_root(conn, problem, workspace, slugs) -> "set[str]":
    """The slugs in the proved root's LIVE dependency closure — `main` plus
    every decl it transitively cites through the proof-term usage DAG
    (`inventory.usage_graph`, root edges read from Root.lean via `_root_source`,
    fix db00977). A proved goal NOT reachable from `main` is proving DEBRIS:
    an abandoned re-derivation / duplicate the daemon marked `proved` but the
    final root proof does not use (Jordan: 54 of 143). Returns the reachable
    set (always includes the root slug)."""
    from ..quality.librarian import inventory as _inv
    rs = _root_source(conn, problem, workspace)
    root_slug = rs[0] if rs else "main"
    usage = _inv.usage_graph(workspace, problem, set(slugs), root_source=rs)
    reachable: set[str] = set()
    stack = [root_slug]
    while stack:
        s = stack.pop()
        if s in reachable:
            continue
        reachable.add(s)
        for dep in usage.get(s, set()):
            if dep not in reachable:
                stack.append(dep)
    return reachable


def _run_keepall(conn, *, problem, workspace):
    """v0.3 mechanical replacement for the agentic `dedup` step (plan §0/§3).

    Inventory the proved-goal decls, restrict to the proved root's LIVE
    dependency closure (`_reachable_from_root`), and mark every survivor `keep`
    — no keep/drop/cite/merge judgment, no spawn.

    Two reasons for the reachability filter (vs naive keep-ALL):
      1. North-star (plan §1): the Library should be exactly what `main` needs.
         Proving leaves ORPHAN DEBRIS — abandoned re-derivations / duplicate
         lemmas marked `proved` but unreachable from `main` (Jordan: 54/143).
         Library-izing them pollutes the Library with proof-thrash.
      2. Debris is often un-migratable anyway: an orphan decl can cite a DEAD
         sibling (e.g. `gaps_from_boundaries_2` → dead `gap_terms_sum`), which
         no mechanical relabel can resolve — it would hard-fail the file and
         block the chain. Filtering removes the junk before it can.

    Keeping everything in the LIVE closure is what makes migrate mechanical
    (every reference resolves to a kept sibling → no holes → no LLM) and
    deterministic (the high-variance agentic dedup — Jordan 81↔22 — is gone).
    Gate B (bridge) is the safety net if the filter ever drops a needed decl:
    `main` would fail to re-derive, loudly. Advances survivors to `deduped` so
    the existing classify step ingests them.

    Trade-off (accepted, plan §0): the kept closure still has reconstructed
    mathlib wrappers + scaffolding — verbose but self-contained; mathlib-PR
    curation (goal #2) is a future opt-in pass, not the main chain."""
    from . import PipelineResult
    from ..quality.librarian import inventory as _inv

    inv = _inv.build_inventory(conn, workspace, problem)
    proved_slugs = {d.slug for d in inv.decls}
    reachable = _reachable_from_root(conn, problem, workspace, proved_slugs)
    kept = [d for d in inv.decls if d.slug in reachable]
    n_orphan = len(inv.decls) - len(kept)
    if n_orphan:
        print(f"[librarian] {problem}: keep over root's live closure — "
              f"{len(kept)} reachable kept, {n_orphan} orphan proved decl(s) "
              f"skipped (debris)", flush=True)
    for d in kept:
        db.upsert_library_decl(conn, problem=problem, slug=d.slug,
                               source_goal_id=d.goal_id)
    for name in inv.defs_decls:
        # Defs decls have no proof goal — source_goal_id is None. Kept whole
        # (foundational + few); the statement / closure references them.
        db.upsert_library_decl(conn, problem=problem, slug=name,
                               source_goal_id=None)
    for r in db.library_decls_for(conn, problem):
        if r["lifecycle"] == "candidate":
            db.set_library_verdict(conn, problem=problem, slug=r["slug"],
                                   verdict="keep")
    return PipelineResult(outcome="success")


def _run_structured(conn, *, problem, work_kind, workspace,
                    attempts_dir, problem_dir, prompt_path):
    """classify: one-shot spawn emitting plan.json, then parse + verify +
    commit (all-or-nothing). Mirrors run_strategist. (v0.3: `dedup` no longer
    routes here — it is the mechanical `_run_keepall`.)"""
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


class _MechAssembly(NamedTuple):
    """Structured form of a mechanically-assembled migrate file, so per-hole
    fills can swap a single decl's chunk and reassemble WITHOUT re-parsing
    Lean decl boundaries (the chunks are already split per decl). `chunks`
    maps slug → that decl's namespace-body text; `slugs` is the emission order;
    `header` is the hoisted imports (+ opens) block."""
    header: str
    target_module: str
    slugs: list
    chunks: dict


def _reassemble(asm: "_MechAssembly", overrides: "dict | None" = None) -> str:
    """Rebuild the whole-file text from an assembly, optionally replacing some
    slugs' chunks (per-hole fills). `_reassemble(asm)` reproduces the original
    mechanical text exactly — the migrate text and the merge path share this
    one formatter so they can never drift."""
    chunks = dict(asm.chunks)
    if overrides:
        chunks.update(overrides)
    body = "\n\n".join(chunks[s] for s in asm.slugs)
    return (asm.header
            + f"\n\nnamespace {asm.target_module}\n\n"
            + body
            + f"\n\nend {asm.target_module}\n")


def _extract_single_decl(text: str, target_module: str) -> "tuple[str, list]":
    """Split a per-decl staging file (the incremental migrate seed:
    `import … + namespace target + ONE decl + end`) into `(decl_chunk,
    extra_imports)`. The decl is alone in the namespace body, so extraction
    is exact — no anchor heuristics. `extra_imports` are the `import` lines
    the agent added (e.g. a Mathlib lemma's module), to fold into the final
    file's header; the self-import of the partial target module is dropped
    by the caller."""
    body: list[str] = []
    imports: list[str] = []
    inside = False
    for ln in text.splitlines():
        if ln.startswith("import "):
            imports.append(ln)
            continue
        if ln.startswith(f"namespace {target_module}"):
            inside = True
            continue
        if ln.startswith(f"end {target_module}"):
            inside = False
            continue
        if inside:
            body.append(ln)
    return "\n".join(body).strip("\n"), imports


def _demote_to_hole(chunk: str, target_module: str) -> "str | None":
    """Turn a mechanically-relabelled decl chunk into a `sorry` hole seed —
    keep its (relabelled, build-clean) signature, drop the body. Used to
    demote a mechanical relabel that breaks the build to a per-decl LLM fill
    instead of an opaque whole-file failure. Returns None if the body
    boundary can't be found (then the caller fails loud)."""
    from ..quality.librarian.relabel import _replace_body_with_sorry
    wrapped = f"namespace {target_module}\n{chunk}\nend {target_module}\n"
    seeded = _replace_body_with_sorry(wrapped, target_module)
    if seeded is None:
        return None
    body, _imports = _extract_single_decl(seeded, target_module)
    return body or None


def _merge_header(header: str, extra_imports: "set[str]") -> str:
    """Fold `extra_imports` into a `_MechAssembly.header` (sorted imports,
    then a blank line, then `open`s), de-duplicating."""
    lines = header.splitlines()
    imports = {l for l in lines if l.startswith("import ")}
    opens = [l for l in lines if l.startswith("open ")]
    for e in extra_imports:
        if e.startswith("import "):
            imports.add(e)
        elif e.startswith("open ") and e not in opens:
            opens.append(e)
    out = "\n".join(sorted(imports))
    if opens:
        out += "\n\n" + "\n".join(sorted(set(opens)))
    return out


def _hole_still_unfilled(chunk: str, seed_chunk: str) -> bool:
    """True when an extracted hole chunk was not actually filled — still
    carries a `sorry`, or is byte-identical to the seed stub. A distinct,
    no-sorry failure is the Strategist-escalation hook; a `sorry` must
    never reach the commit gate."""
    if chunk.strip() == seed_chunk.strip():
        return True
    return re.search(r"(^|\W)sorry(\W|$)", chunk) is not None


class _MechIntegrityError(Exception):
    """A decl's source can't be located where the DB says it should be —
    file↔DB drift (CLAUDE.md rule 10), not a 'needs the LLM' case. Surfaced
    as a loud, distinct migrate failure rather than masked by a cold
    from-scratch spawn (which would hide the corruption)."""


def _defs_decl_source(defs_text: str, name: str) -> "str | None":
    """The verbatim slice of `Defs.lean` declaring `name` — its keyword head
    through to the next top-level declaration (or EOF). Defs decls have no
    `proofs/L_<slug>.lean`; this gives them the same per-decl source every
    other migratable decl has, so they relabel through the one mechanical
    path instead of forcing the whole file to a cold from-scratch spawn."""
    from ..quality.librarian.inventory import _DEFS_DECL_RE
    matches = list(_DEFS_DECL_RE.finditer(defs_text))
    for i, m in enumerate(matches):
        if m.group(2) == name:
            start = m.start()
            end = (matches[i + 1].start()
                   if i + 1 < len(matches) else len(defs_text))
            return defs_text[start:end].rstrip()
    return None


def _mechanical_migrate_file(
    conn, *, problem, workspace, target_file, target_module, rows,
) -> "tuple[str | None, list[str], _MechAssembly | None]":
    """Best-effort relabel of a whole classified file (librarian_plan §4
    Phase 1) — no LLM. Returns `(assembled_text, holes)`:

      - Every decl relabels cleanly → `(text, [])`: a fully mechanical file
        the caller commits with zero spawn.
      - Some decls decline (body cites a non-keep sibling that can't be
        mechanically redirected) → they are emitted as `<relabelled-sig> :=
        sorry` and their slugs returned in `holes`. The text is then a SEED:
        a real Lean file (sorry only warns) the LLM finishes by filling the
        holes, instead of writing the whole file from scratch (the prior
        ChainAssembly-timeout root cause). All N decls are present and in
        order, so positional pairing still holds.
      - A decl can't even be seeded (no proof file, or its SIGNATURE itself
        cites a non-keep symbol so `body_to_sorry` also declines) → `(None,
        [])`: the caller cold-spawns the whole file. Per the §4 data all
        Jordan holes have clean signatures, so this is the rare path.

    Builds the relabel inputs from DB state:
      - keep_slugs    : every `keep` decl (becomes a Library sibling)
      - defs_imports  : migrated Defs symbol → its Library module
      - citation_map  : verbatim-merge sibling → canonical (full-signature
                        equal only; near-merge / drop / cite-mathlib are NOT
                        here → those decls become holes)
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

    # local_defs: Defs symbols classify placed in THIS file — they migrate
    # together with their users, so they land in the same module namespace
    # (bare name visible, no import, no "not yet migrated" decline). Without
    # this, a file holding both a Defs decl and a lemma that uses it can't
    # migrate (classify is free to co-locate them; layout is nondeterministic).
    local_defs = {r["slug"] for r in all_rows
                  if r["slug"] in all_defs and r["target_file"] == target_file}

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
        p = _inv.resolve_ci(proofs, f"L_{slug}.lean")   # L_/l_ case-insensitive
        if p is None:
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

    # strategy_aliases: `sN` → the kept sibling slug whose proof IS that
    # strategy term (the lemma is `def <slug> := @sN`). Lets relabel redirect a
    # NESTED strategy reference (a strategy body that cites another strategy's
    # raw proof-term instead of the lemma name) to the kept sibling lemma.
    strategy_aliases: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "keep" and r["target_file"]:
            ap = _inv.resolve_ci(proofs, f"L_{r['slug']}.lean")
            if ap is not None:
                am = alias_re.search(ap.read_text(encoding="utf-8",
                                                  errors="replace"))
                if am:
                    strategy_aliases[am.group(1)] = r["slug"]

    defs_text = ""
    defs_lean = problem_dir / "Defs.lean"
    if defs_lean.exists():
        defs_text = defs_lean.read_text(encoding="utf-8")

    import_set: set[str] = set()
    open_set: set[str] = set()
    chunk_by_slug: dict[str, str] = {}
    holes: list[str] = []
    for r in rows:
        slug = r["slug"]
        # Resolve this decl's per-decl source uniformly by kind, so Defs
        # decls and the root theorem migrate through the SAME mechanical
        # path as ordinary lemmas — no special cold from-scratch spawn:
        #   - Defs decl (no source goal)  → its slice of Defs.lean
        #   - any goal (lemma OR root)    → its `lean_path` file
        #                                   (root → Root.lean; lemma →
        #                                    proofs/L_<slug>.lean)
        # A source the DB points at but that is missing is file↔DB drift —
        # raised loud, never masked by from-scratch (CLAUDE.md rule 10).
        strat_text = None
        if r["source_goal_id"] is None:
            defs_slice = _defs_decl_source(defs_text, slug)
            if defs_slice is None:
                raise _MechIntegrityError(
                    f"Defs decl `{slug}` not found in Defs.lean")
            # Preserve Defs.lean's import/open header so any notation the
            # decl relies on still resolves after migration (relabel drops
            # the Problems imports as usual); ensure the Mathlib umbrella.
            hdr = "\n".join(ln for ln in defs_text.splitlines()
                            if ln.startswith(("import ", "open ")))
            if "import Mathlib" not in hdr:
                hdr = ("import Mathlib\n" + hdr) if hdr else "import Mathlib"
            src = f"{hdr}\nnamespace {pns}\n{defs_slice}\nend {pns}\n"
        else:
            g = db.get_goal(conn, r["source_goal_id"])
            # L_/l_ case-insensitive: resolve the proof file's basename within
            # its dir (DB lean_path is uppercase L_; disk may be lowercase l_).
            src_path = None
            if g:
                _lp = workspace / g["lean_path"]
                src_path = _inv.resolve_ci(_lp.parent, _lp.name)
            if src_path is None:
                raise _MechIntegrityError(
                    f"`{slug}`: proof source "
                    f"{g['lean_path'] if g else '?'} missing (file↔DB drift)")
            src = src_path.read_text(encoding="utf-8")
            m = alias_re.search(src)
            if m:
                strat_name = f"_strategy_{m.group(1)}.lean"
                strat_path = _inv.resolve_ci(proofs, strat_name)
                if strat_path is None:
                    raise _MechIntegrityError(
                        f"`{slug}`: alias → missing {strat_name} "
                        "(file↔DB drift)")
                strat_text = strat_path.read_text(encoding="utf-8")
        kw = dict(problem_namespace=pns, target_namespace=target_module,
                  keep_slugs=keep_slugs, defs_imports=defs_imports,
                  # Exclude this decl's own name: a Defs decl's source contains
                  # its own name (`def <slug>`), which must not be mistaken for
                  # a dependency on an unmigrated Defs symbol. No-op for lemmas
                  # / root (their slug isn't a Defs decl).
                  all_defs_syms=all_defs - {slug}, local_defs=local_defs,
                  citation_map=citation_map,
                  sibling_modules=sibling_modules,
                  strategy_aliases=strategy_aliases)

        def _relabel_one(body_to_sorry: bool, best_effort: bool = False):
            if strat_text is not None:
                return _relabel.inline_alias(
                    src, strat_text, slug=slug, body_to_sorry=body_to_sorry,
                    best_effort=best_effort, **kw)
            return _relabel.relabel_self_contained(
                src, body_to_sorry=body_to_sorry, best_effort=best_effort,
                **kw)

        res = _relabel_one(body_to_sorry=False)
        if not res.ok:
            # Body cites a non-keep sibling → seed a body hole (sig clean).
            res = _relabel_one(body_to_sorry=True)
            if res.ok:
                holes.append(slug)
            else:
                # The SIGNATURE itself isn't Defs-free → seed a SIGNATURE
                # hole (best-effort: leave the unresolved ref, body = sorry)
                # for the per-hole LLM to restate Defs-free. Only a
                # structural fault (no namespace / broken alias) fails even
                # this — that is drift, raised loud.
                res = _relabel_one(body_to_sorry=True, best_effort=True)
                if not res.ok:
                    raise _MechIntegrityError(
                        f"`{slug}`: cannot relabel even best-effort "
                        f"({res.reason})")
                holes.append(slug)
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
        chunk_by_slug[slug] = "\n".join(body).strip("\n")

    # Fold in the file-level cross-file dependency imports from the
    # authoritative file_dependency_graph. relabel only emits a sibling
    # `import` when the source carried an explicit `import …proofs.L_<sub>`;
    # a citation that reaches a sibling transitively (or bundled inside a
    # `_strategy_*` file) is missed, so its full-qualified reference relabels
    # cleanly but lands in a header with no import for that module → Unknown
    # identifier. The dependency graph knows the edge regardless (it drives
    # the migrate order), so the header must carry it. This covers all three
    # consumers of `header` — the 0-hole mechanical commit, the incremental
    # per-decl staging (`_stage`), and the final assembled file. The graph is
    # a DAG over already-classified files and we only import upstream deps, so
    # no cycle; a redundant import is build-harmless.
    dep_imports = {
        f"import {_library_module_of(df)}"
        for df in file_dependency_graph(
            conn, problem=problem, workspace=workspace).get(target_file, set())}
    import_set |= dep_imports
    header = "\n".join(sorted(import_set))
    if open_set:
        header += "\n\n" + "\n".join(sorted(open_set))
    asm = _MechAssembly(header=header, target_module=target_module,
                        slugs=[r["slug"] for r in rows], chunks=chunk_by_slug)
    return _reassemble(asm), holes, asm


def _commit_migrated_file(
    patch_text, *, conn, problem, workspace, target_path, target_module,
    ordered_slugs, defs_names, whitelist,
    build_verifier=None, axiom_verifier=None, defeq_verifier=None,
    olean_writer=None):
    """Validate a whole-file migrate candidate and, on success, commit it
    (write the file + mark every decl migrated). Shared by the 0-hole
    mechanical fast path and the incremental per-decl assembly, so the commit
    contract (Gate A + pairing + Gate D + olean) is single-sourced.

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
    # Persist the committed file's .olean so its importers (dispatched later
    # in topological order) build against a fresh dependency, not a stale one
    # (R1b). Mirrors proof-time's per-lemma write_olean=True.
    ok, detail = (olean_writer or _warm_olean_writer(workspace))(target_path)
    if not ok:
        try:
            target_path.unlink()
        except OSError:
            pass
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=f"olean write: {detail}", proposal_md=patch_text)
    # All gates passed — advance every decl to 'migrated', backfilling each
    # one's fully-qualified Library name (classify wrote it NULL).
    for slug, decl in zip(ordered_slugs, decls):
        db.mark_library_migrated(conn, problem=problem, slug=slug,
                                 target_name=decl.fq_name)
    return PipelineResult(outcome="success")


def _release_session(attempts_dir) -> None:
    """Release the gateway session registered in `attempts_dir` (best-effort).
    Each incremental per-decl spawn registers its own session in its
    `decl-<slug>/` dir; nothing else releases it, so without this every
    per-decl spawn leaks a gateway worker slot and the Nth register 500s on
    slot exhaustion."""
    from ..lsp import lifecycle as _gw
    tok = attempts_dir / "_gateway_session.token"
    if tok.exists():
        t = tok.read_text(encoding="utf-8").strip()
        if t:
            try:
                _gw.release_session(t)
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass


def _migrate_file_incremental(
        conn, *, problem, workspace, pipeline_id, target_file,
        target_path, target_module, ordered_slugs, defs_names, whitelist,
        attempts_dir, problem_dir, prompt_path, holes, mech_asm,
        fill_fn=None, olean_writer=None, localize=False):
    """migrate Phase 2 (#87) — incremental, per-declaration. Build the target
    file declaration-by-declaration in file_order: a mechanically-relabelled
    decl is appended directly; a decl that needs the LLM is staged ALONE —
    `import <the target module built so far> + the one decl seed` — filled by
    its own small spawn and BUILT against the prior decls before it joins the
    file. So every decl is build-verified the moment it lands (mirroring the
    proof phase's per-lemma topological build), the LLM never synthesises more
    than one declaration (no whole-file over-think), and there is no
    from-scratch path.

    Sequential within the file (each spawn is tiny → no over-think); files
    migrate in parallel at the dispatcher level (`dispatch.pool`), so no nested
    pool is needed. A decl that can't be filled → distinct no-`sorry` failure
    (`librarian_migrate_hole_unfilled`, the Strategist-escalation hook); a
    `-- decline: needs-upstream` routes through the shared cascade. `fill_fn` /
    `olean_writer` are injectable for offline tests.
    """
    from . import PipelineResult, PROMPT_DIR, _write_mcp_config
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import agent
    from ..core import dispatcher

    holes_set = set(holes)
    olw = olean_writer or _warm_olean_writer(workspace)
    # migrate.md is the per-decl prompt (rewritten for this scope; there is no
    # separate migrate_hole.md).
    hole_prompt = prompt_path
    target_existed = target_path.exists()
    # mech is rebound when a mechanical relabel is demoted to a hole, so the
    # nested helpers read the latest chunks.
    mech = mech_asm

    def _drop_partial():
        # The target file is CREATED by this migrate; remove a partial staging
        # write on failure (don't touch a pre-existing file — there shouldn't
        # be one).
        if not target_existed and target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    def _stage(subset) -> "tuple[bool, str]":
        # Write the decls done so far (a slug subset, from `done`) to the real
        # target + build its olean, so a following decl can `import` them
        # (R1b per-file olean).
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            _reassemble(mech._replace(slugs=list(subset)), overrides=done),
            encoding="utf-8")
        return olw(target_path)

    def _default_fill_decl(slug):
        """Stage `import <partial target> + the one decl seed`, spawn one
        agent to finish that single declaration, build-verify, and return
        `((chunk, extra_imports), None)`. Returns `(None, decline_text)` on a
        `-- decline:`, `(None, None)` on exhaustion."""
        dattempts = attempts_dir / f"decl-{slug}"
        dattempts.mkdir(parents=True, exist_ok=True)
        patch = dattempts / "patch.lean"
        dpid = f"{pipeline_id}:decl-{slug}"
        # Seed the LLM with the SAME header the assembled file will have
        # (`mech.header`: every cross-file sibling + Defs import AND its `open`,
        # added by relabel) plus a self-`import` of the partial target so prior
        # decls are in scope. This way the fill's compile environment == the
        # final file's: bare sibling / Defs names resolve exactly as they will
        # after assembly (no `?m` autobind from a missing Defs `open`).
        seed_header = _merge_header(mech.header, {f"import {target_module}"})
        seed = (seed_header
                + f"\n\nnamespace {target_module}\n\n"
                + mech.chunks[slug]
                + f"\n\nend {target_module}\n")
        cap: dict = {}

        def spawn(ctx: SpawnCtx) -> int:
            if ctx.cold:
                compile_librarian_context(
                    conn, problem=problem, work_kind="migrate",
                    attempts_dir=ctx.attempts_dir, workspace=workspace,
                    target_file=target_file, holes=holes, solo_hole=slug)
                patch.write_text(seed, encoding="utf-8")
            mcp_config_path = _write_mcp_config(
                attempts_dir=ctx.attempts_dir, workspace=workspace,
                target=patch, pipeline_id=dpid, problem=problem)
            return agent.spawn_llm(
                kind="librarian", prompt_path=hole_prompt,
                problem_dir=problem_dir, attempts_dir=ctx.attempts_dir,
                session_id=ctx.sid, is_retry=not ctx.cold,
                retry_context=ctx.retry_context,
                mcp_config_path=mcp_config_path,
                inline_prompt=ctx.inline_prompt,
                timeout_sec_override=ctx.budget_override)

        def parse() -> PipelineResult:
            if not patch.exists():
                return PipelineResult(
                    outcome="failed", failure_reason="agent_no_output",
                    failure_detail=f"decl {slug}: no patch.lean")
            text = patch.read_text(encoding="utf-8")
            if "-- decline:" in text:
                cap["decline"] = text
                return PipelineResult(
                    outcome="agent_declined", failure_reason="agent_declined",
                    failure_detail=f"decl {slug} declined", proposal_md=text)
            chunk, imports = _extract_single_decl(text, target_module)
            if not chunk:
                return PipelineResult(
                    outcome="failed", failure_reason="librarian_gate_failed",
                    failure_detail=f"decl {slug}: no declaration in the "
                                   f"`{target_module}` namespace",
                    proposal_md=text)
            if _hole_still_unfilled(chunk, mech.chunks[slug]):
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_migrate_hole_unfilled",
                    failure_detail=f"decl {slug}: still `sorry` after fill",
                    proposal_md=text)
            # Keep only genuinely new imports the agent added; drop the seed's
            # own (mech.header's siblings/Defs + Mathlib + the partial-target
            # self-import, which must never appear in the committed file —
            # mech.header already carries the real ones).
            seed_imports = {l for l in seed_header.splitlines()
                            if l.startswith("import ")}
            cap["chunk"] = chunk
            cap["imports"] = [im for im in imports if im not in seed_imports]
            return PipelineResult(outcome="success")

        try:
            res = run_with_session_retries(
                conn=conn, goal_id=None, pipeline_id=dpid,
                budget_threshold=dispatcher.BUILDER_THRESHOLD,
                shelve_threshold=dispatcher.SHELVE_THRESHOLD,
                attempts_dir=dattempts, spawn_fn=spawn, parse_fn=parse,
                postmortem_fn=lambda sid: None, workspace=workspace)
        finally:
            # Free this decl's gateway worker slot before the next decl
            # registers — sequential per-decl spawns would otherwise exhaust
            # the pool (each leaks a slot).
            _release_session(dattempts)
        if res.outcome == "success":
            return (cap["chunk"], cap["imports"]), None
        return None, cap.get("decline")

    fill = fill_fn or _default_fill_decl
    done: dict[str, str] = {}        # slug -> final namespace-body chunk
    extra_imports: set[str] = set()

    def _d(detail) -> str:
        return (detail or "")[:120].encode("ascii", "replace").decode("ascii")

    for i, slug in enumerate(ordered_slugs):
        needs_llm = slug in holes_set
        if not needs_llm:
            done[slug] = mech.chunks[slug]
            if not localize:
                continue                         # trust the final whole build
            # localize mode (entered when the 0-hole whole-file build failed):
            # build through THIS decl; if its mechanical relabel breaks the
            # build, demote it to a hole and fill it per-decl below.
            ok, detail = _stage(ordered_slugs[:i + 1])
            if ok:
                continue
            seed = _demote_to_hole(mech.chunks[slug], target_module)
            if seed is None:
                _drop_partial()
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_integrity_error",
                    failure_detail=f"{slug}: relabel breaks the build and "
                                   f"cannot be demoted ({_d(detail)})")
            mech = mech._replace(chunks={**mech.chunks, slug: seed})
            del done[slug]
            print(f"[librarian] {target_file}: mechanical `{slug}` broke the "
                  "build; demoting to a per-decl LLM fill", flush=True)
            needs_llm = True
        # LLM decl (an original hole or a just-demoted mechanical one): expose
        # the prior decls via a compiled partial target, then fill + build it.
        ok, detail = _stage(ordered_slugs[:i])
        if not ok:
            _drop_partial()
            return PipelineResult(
                outcome="failed", failure_reason="librarian_integrity_error",
                failure_detail=f"{slug}: prior decls do not build ({_d(detail)})")
        filled, decline = fill(slug)
        if decline:
            _drop_partial()
            return _decline_or_reopen(
                conn, problem=problem, workspace=workspace,
                patch_text=decline, stage="migrate")
        if filled is None:
            _drop_partial()
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_migrate_hole_unfilled",
                failure_detail=(
                    f"{target_path.name}: decl `{slug}` could not be filled — "
                    "the proof obligation exceeds migration; escalate to the "
                    "Strategist. No `sorry` is committed."))
        done[slug] = filled[0]
        extra_imports.update(filled[1])

    header = (_merge_header(mech.header, extra_imports)
              if extra_imports else mech.header)
    merged = _reassemble(mech._replace(header=header), overrides=done)
    res = _commit_migrated_file(
        merged, conn=conn, problem=problem, workspace=workspace,
        target_path=target_path, target_module=target_module,
        ordered_slugs=ordered_slugs, defs_names=defs_names,
        whitelist=whitelist, olean_writer=olean_writer)
    if res.outcome != "success":
        _drop_partial()
    return res


def _run_migrate(conn, *, problem, workspace, pipeline_id, target_file,
                 attempts_dir, problem_dir, prompt_path, whitelist=None):
    """migrate (per-file, plan §5 Step 3): build one Library file holding
    that file's classified decls (in file_order). Phase 1 mechanically
    relabels every decl; a 0-hole assembly that builds commits with no spawn.
    Otherwise Phase 2 (`_migrate_file_incremental`) builds the file
    declaration-by-declaration — mechanical decls appended directly, each decl
    that needs the LLM filled by its own small spawn and build-verified before
    it joins. No whole-file from-scratch / over-think path. Gate D rfl-checks
    each migrated `def`; all decls advance to 'migrated' together."""
    from . import PipelineResult
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

    # Phase 1 — mechanical relabel pre-pass (librarian_plan §4): best-effort
    # assemble the whole file by pure relabel (no LLM). file↔DB drift raises
    # _MechIntegrityError — surfaced loud, never masked by a from-scratch spawn
    # (CLAUDE.md rule 9 + 10).
    try:
        mech_text, holes, mech_asm = _mechanical_migrate_file(
            conn, problem=problem, workspace=workspace,
            target_file=target_file, target_module=target_module, rows=rows)
    except _MechIntegrityError as e:
        _detail = str(e)[:200].encode("ascii", "replace").decode("ascii")
        return PipelineResult(
            outcome="failed", failure_reason="librarian_integrity_error",
            failure_detail=_detail)

    # v0.3 (plan §3): migrate is MECHANICAL-ONLY — no Phase-2 LLM. With every
    # decl kept (no dedup), every proof-term reference resolves to a kept
    # sibling, so a clean relabel has no holes. A hole — or a 0-hole assembly
    # that does not build — is therefore a mechanical-relabel limitation (e.g.
    # an alias→strategy body that doesn't inline syntactically, or a dropped
    # Defs import a tactic relied on), surfaced as a HARD FAIL for the operator,
    # NOT silently patched by an LLM (which would reintroduce the variance/risk
    # v0.3 removed). `attempts_dir` / `problem_dir` / `prompt_path` are now
    # unused here (kept in the signature for the dormant incremental path).
    if holes:
        return PipelineResult(
            outcome="failed",
            failure_reason="librarian_migrate_not_mechanical",
            failure_detail=(
                f"{target_file}: {len(holes)} decl(s) not mechanically "
                f"relabelable: {holes}. v0.3 migrate is mechanical-only — "
                "needs operator (fix relabel.py, or decide per-decl). "
                "No LLM fallback, no sorry committed."))

    mech_res = _commit_migrated_file(
        mech_text, conn=conn, problem=problem, workspace=workspace,
        target_path=target_path, target_module=target_module,
        ordered_slugs=ordered_slugs, defs_names=defs_names,
        whitelist=whitelist)
    if mech_res.outcome == "success":
        print(f"[librarian] {target_file}: migrated mechanically "
              f"({len(ordered_slugs)} decls, no LLM)", flush=True)
        return mech_res
    # Clean relabel that does not build = subtle mechanical bug; commit gate
    # already removed the partial file. Hard-fail + flag (sanitize unicode).
    _detail = (mech_res.failure_detail or "")[:200].encode(
        "ascii", "replace").decode("ascii")
    return PipelineResult(
        outcome="failed", failure_reason="librarian_migrate_build_failed",
        failure_detail=(
            f"{target_file}: mechanical relabel does not build: {_detail}. "
            "v0.3 mechanical-only — needs operator."))


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


def _snapshot_problem_library(conn, problem, workspace) -> dict:
    """{rel_path: content|None} for every problem-Library file — captured
    before an agent edits files in place, for touched-diff + rollback."""
    return {f: ((workspace / f).read_text(encoding="utf-8")
                if (workspace / f).exists() else None)
            for f in _problem_library_files(conn, problem)}


def _restore_snapshot(workspace, snap, files) -> None:
    """Restore `files` to their `snap` content (None → delete)."""
    for f in files:
        p = workspace / f
        content = snap.get(f)
        if content is None:
            if p.exists():
                p.unlink()
        else:
            p.write_text(content, encoding="utf-8")


def _affected_cone(graph: dict, touched: set) -> set:
    """`touched` ∪ every file transitively importing one — a signature change
    in F invalidates every G that (transitively) imports F."""
    rev: dict = {}
    for f, deps in graph.items():
        for d in deps:
            rev.setdefault(d, set()).add(f)
    cone, frontier = set(touched), list(touched)
    while frontier:
        x = frontier.pop()
        for imp in rev.get(x, ()):
            if imp not in cone:
                cone.add(imp)
                frontier.append(imp)
    return cone


def _topo_files(graph: dict, files: set) -> list:
    """Topologically order `files` deps-first (a file after every dep that is
    also in the set) so a write_olean rebuild publishes fresh dependency
    oleans before their importers build. Stable; cycle → leftovers appended."""
    files = set(files)
    indeg = {f: len([d for d in graph.get(f, ()) if d in files]) for f in files}
    users: dict = {f: [] for f in files}
    for f in files:
        for d in graph.get(f, ()):
            if d in files:
                users[d].append(f)
    ready = sorted(f for f in files if indeg[f] == 0)
    out: list = []
    while ready:
        f = ready.pop(0)
        out.append(f)
        for u in users[f]:
            indeg[u] -= 1
            if indeg[u] == 0:
                ready = sorted(ready + [u])
    out += [f for f in files if f not in out]   # cycle fallback
    return out


def _default_regate_build(whitelist, workspace):
    """Per-file re-gate build: Gate A import-closure (text) + build the REAL
    file with write_olean=True (persist a fresh olean for downstream importers,
    R1b). No per-decl axiom check — cleanup removes hyps / adds docstrings,
    which can't introduce axioms, and the bridge Gate B axiom-checks the
    main cone afterwards."""
    from ..quality.librarian import gates as _gates

    def _build(path, text) -> tuple[bool, str]:
        clo = _gates.check_import_closure_text(text, label=path.name)
        if not clo.ok:
            return False, "; ".join(clo.issues)[:200]
        return _warm_olean_writer(workspace)(path)
    return _build


def _regate_touched(conn, *, problem, workspace, snap_before, whitelist,
                    regate=None) -> "tuple[bool, str, list[str]]":
    """Re-gate the Library files an agent edited in place. Diffs `snap_before`
    vs disk → touched files, expands to the affected cone (touched + every
    transitive importer), and rebuilds the cone **in dependency (topological)
    order with write_olean=True** — so each importer builds against its
    dependency's freshly-written olean, not a stale one (R1b). Returns
    `(ok, detail, touched)`; does NOT roll back (caller decides).

    Shared by cleanup (Step 4) and bridge (Gate B): both let an agent edit
    committed Library files, so both must re-verify the cone rather than
    trust the agent. `regate` (path, text) -> (ok, detail) is injectable for
    offline tests (replaces the per-file build; cone + order still apply)."""
    def _read(rel):
        p = workspace / rel
        return p.read_text(encoding="utf-8") if p.exists() else None
    touched = sorted(f for f in snap_before if _read(f) != snap_before[f])
    if not touched:
        return True, "", []
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    cone = _affected_cone(graph, set(touched))
    order = _topo_files(graph, cone)
    _build = regate or _default_regate_build(whitelist, workspace)
    for rel in order:
        p = workspace / rel
        if not p.exists():
            return False, f"{rel}: vanished during edit", touched
        ok, detail = _build(p, p.read_text(encoding="utf-8"))
        if not ok:
            return False, f"re-gate {rel}: {detail}"[:400], touched
    return True, "", touched


_NEEDS_UPSTREAM_RE = re.compile(
    r"--\s*decline\s*:\s*needs-upstream\s+([A-Za-z_]\w*)\s*(.*)")


def _parse_needs_upstream(text: str) -> "tuple[str, str] | None":
    """Parse a `-- decline: needs-upstream <slug> [reason]` directive →
    (upstream_slug, reason). The Librarian analog of proof-time
    `return_to_parent`: a downstream node signals that a finalized upstream
    Library decl must be reshaped before it can proceed."""
    m = _NEEDS_UPSTREAM_RE.search(text)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _reopen_upstream_cascade(conn, *, problem, workspace, upstream_slug,
                             note) -> list:
    """Re-open a finalized upstream decl + its consumer cone (the Librarian
    analog of proof-time `return_to_parent`, but it RESHAPES nodes rather
    than re-decomposing — the dependency topology is kept).

    The named upstream's file and every file transitively importing it
    (`_affected_cone`) revert migrated/cleaned → 'classified'; their on-disk
    Library files + oleans are deleted (file↔DB paired, CLAUDE rule 10) so
    the next derive re-migrates the faithful baseline and then re-cleans —
    this time with `note` (what the downstream needed) recorded on the
    upstream so its re-cleanup can reshape DIFFERENTLY (else a faithful
    re-migrate would loop to the same result). Bounding is the dispatcher's
    per-problem fail cap. Returns the reopened target_files."""
    rows = db.library_decls_for(conn, problem)
    up = next((r for r in rows if r["slug"] == upstream_slug
               and r["target_file"]), None)
    if up is None:
        return []
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    reopened: list = []
    for f in sorted(_affected_cone(graph, {up["target_file"]})):
        n = conn.execute(
            "UPDATE library_decls SET lifecycle='classified', updated_at=? "
            "WHERE problem=? AND target_file=? AND lifecycle IN "
            "('migrated','cleaned')", (db.now(), problem, f)).rowcount
        if not n:
            continue
        reopened.append(f)
        p = workspace / f
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
        mod = _library_module_of(f)
        olean = (workspace / ".lake" / "build" / "lib" / "lean"
                 / (mod.replace(".", "/") + ".olean"))
        if olean.exists():
            try:
                olean.unlink()
            except OSError:
                pass
    if note:
        conn.execute(
            "UPDATE library_decls SET reopen_note=? WHERE problem=? AND slug=?",
            (note, problem, upstream_slug))
    conn.commit()
    return reopened


def _decline_or_reopen(conn, *, problem, workspace, patch_text, stage):
    """Map a Librarian agent decline to a PipelineResult. A
    `needs-upstream <slug>` directive triggers the re-open cascade (reshape
    a finalized upstream + its cone); anything else is a plain decline. The
    dispatcher re-enqueues the failure (bounded), so after a cascade the next
    derive re-migrates the reopened cone."""
    from . import PipelineResult
    nu = _parse_needs_upstream(patch_text)
    if nu:
        slug, reason = nu
        # Only a finalized (placed → has target_file) upstream can be reshaped.
        # A slug that is unknown, or dropped/cited/merged (no target_file, i.e.
        # it already has a REPLACEMENT and is not a Library decl), can't be
        # reshaped — fail LOUD with the verdict→replacement, instead of letting
        # the cascade silently no-op and the chain stall at the fail cap.
        row = next((r for r in db.library_decls_for(conn, problem)
                    if r["slug"] == slug), None)
        if row is None or not row["target_file"]:
            if row is None:
                why = (f"`{slug}` is not a declaration in this problem "
                       f"(check the slug)")
            else:
                why = (f"`{slug}` is {row['verdict']}→`{row['citation'] or '(none)'}`"
                       f", not a Library decl to reshape — cite the replacement, "
                       f"or this is a wrong dedup verdict (revive `{slug}`)")
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_needs_upstream_unresolvable",
                failure_detail=f"{stage}: needs-upstream {why}",
                proposal_md=patch_text)
        reopened = _reopen_upstream_cascade(
            conn, problem=problem, workspace=workspace, upstream_slug=slug,
            note=reason or f"reshape needed by {stage}")
        if not reopened:
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_needs_upstream_unresolvable",
                failure_detail=f"{stage}: needs-upstream `{slug}` matched no "
                               f"finalized (migrated/cleaned) decl to reshape "
                               f"(already classified / in-flight?)",
                proposal_md=patch_text)
        return PipelineResult(
            outcome="failed", failure_reason="librarian_reopened_upstream",
            failure_detail=f"{stage}: reopened upstream `{slug}` + cone "
                           f"{reopened}", proposal_md=patch_text)
    return PipelineResult(
        outcome="failed", failure_reason="agent_declined",
        failure_detail=f"{stage} declined", proposal_md=patch_text)


def _commit_cleanup(conn, *, problem, workspace, target_file, slugs,
                    snap_before, whitelist, regate=None, lint=None):
    """Validate a cleanup edit (Step 4) and commit or roll back. Re-gates the
    touched files + importers (`_regate_touched`) and requires the target to
    have NO `unusedVariables` warnings left (the cleanup objective). All pass
    → the file's decls advance to 'cleaned'. Any fail → restore the touched
    files (retry starts clean). `lint` (path) -> list[str] is injectable."""
    from . import PipelineResult

    ok, detail, touched = _regate_touched(
        conn, problem=problem, workspace=workspace, snap_before=snap_before,
        whitelist=whitelist, regate=regate)
    if target_file not in touched:
        _restore_snapshot(workspace, snap_before, touched)
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=f"{target_file}: agent made no edit to the target")
    if not ok:
        _restore_snapshot(workspace, snap_before, touched)
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=detail)

    warns = (lint or _unused_var_warnings)(workspace / target_file)
    if warns:
        _restore_snapshot(workspace, snap_before, touched)
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=f"{target_file}: {len(warns)} unused-variable "
                           f"warning(s) remain: {warns[:3]}")

    for slug in slugs:
        db.mark_library_cleaned(conn, problem=problem, slug=slug)
    return PipelineResult(outcome="success")


def _unused_var_warnings(target_path) -> "list[str]":
    """Warm-gateway verify of `target_path`; return the `unusedVariables`
    linter warning messages (the cleanup objective is to leave none)."""
    from ..lsp import lifecycle as gw
    r = gw.verify_file(target_path, write_olean=False)
    out = []
    for d in (r.get("diagnostics") or []):
        msg = d.get("message", "")
        if "unused" in msg.lower():
            out.append(msg[:120])
    return out


def _run_cleanup(conn, *, problem, workspace, pipeline_id, target_file,
                 attempts_dir, problem_dir, prompt_path, whitelist=None):
    """Step 4 cleanup (plan §5): an agent reshapes one migrated Library file
    to PR-ready form (remove unused hyps + update call sites, factor
    `variable`, add a module docstring) per mathlib_conventions.md, editing
    the committed Library files in place (LSP holds the target file; siblings
    via Edit). The commit re-gates touched files + importers and rolls back on
    failure; Gate D no longer applies (signatures intentionally change) — the
    meaning net is the later bridge Gate B. On pass the file's decls →
    'cleaned'. Same warm-gateway / session-retry machinery as migrate."""
    from . import PipelineResult, _write_mcp_config
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import agent
    from ..core import dispatcher

    target_path = workspace / target_file
    slugs = [r["slug"] for r in db.library_decls_for(conn, problem)
             if r["target_file"] == target_file
             and r["lifecycle"] == "migrated"]
    if not slugs or not target_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="librarian_not_migrated",
            failure_detail=f"{target_file}: no migrated decls on disk")

    snap_before = _snapshot_problem_library(conn, problem, workspace)
    patch_lean = attempts_dir / "patch.lean"   # decline channel only

    def cleanup_spawn(ctx: SpawnCtx) -> int:
        if ctx.cold:
            compile_librarian_context(
                conn, problem=problem, work_kind="cleanup",
                attempts_dir=ctx.attempts_dir, workspace=workspace,
                target_file=target_file)
            patch_lean.write_text("", encoding="utf-8")
        # The LSP server holds the REAL target Library file — apply_edit
        # write-through edits it in place (siblings go via Edit/Bash).
        mcp_config_path = _write_mcp_config(
            attempts_dir=ctx.attempts_dir, workspace=workspace,
            target=target_path, pipeline_id=pipeline_id, problem=problem)
        return agent.spawn_llm(
            kind="librarian", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=ctx.attempts_dir,
            session_id=ctx.sid, is_retry=not ctx.cold,
            retry_context=ctx.retry_context,
            mcp_config_path=mcp_config_path,
            inline_prompt=ctx.inline_prompt,
            timeout_sec_override=ctx.budget_override)

    def cleanup_parse():
        if patch_lean.exists() and "-- decline:" in patch_lean.read_text(
                encoding="utf-8"):
            return _decline_or_reopen(
                conn, problem=problem, workspace=workspace,
                patch_text=patch_lean.read_text(encoding="utf-8"),
                stage="cleanup")
        return _commit_cleanup(
            conn, problem=problem, workspace=workspace,
            target_file=target_file, slugs=slugs, snap_before=snap_before,
            whitelist=whitelist or [])

    def cleanup_postmortem(sid: str) -> None:
        pass

    return run_with_session_retries(
        conn=conn, goal_id=None, pipeline_id=pipeline_id,
        budget_threshold=dispatcher.BUILDER_THRESHOLD,
        shelve_threshold=dispatcher.SHELVE_THRESHOLD,
        attempts_dir=attempts_dir,
        spawn_fn=cleanup_spawn, parse_fn=cleanup_parse,
        postmortem_fn=cleanup_postmortem, workspace=workspace)


def _write_library_index(conn, *, problem, workspace, gate_b_line: str):
    """Write/refresh the `## <problem>` section of `Library/INDEX.md`:
    migrated-decl provenance + the Gate B status line. INDEX presence is the
    chain's idempotent done-marker (`_derive_librarian_work`). Shared by the
    bridge step (Gate B PASSED) and the agentless finish no-op."""
    migrated = _harvested_decls(conn, problem)
    lines = [f"_Harvested {db.now()} — {len(migrated)} declaration(s)._", ""]
    for r in migrated:
        name = r["target_name"] or r["slug"]
        lines.append(f"- `{name}` → `{r['target_file'] or '?'}`")
    lines.append("")
    lines.append(gate_b_line)
    index = workspace / "Library" / "INDEX.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    existing = (index.read_text(encoding="utf-8", errors="replace")
                if index.exists() else "")
    index.write_text(
        _upsert_index_section(existing, problem, "\n".join(lines)),
        encoding="utf-8")


def _rederivation_prober(bridge_path):
    """A `check_root_rederivation` prober bound to an already-staged bridge
    file: build it via the warm gateway and report whether `fq_name`'s axiom
    set ⊆ whitelist. Used instead of the default `axiom_probe` (which
    resolves a module to a committed source path) because the bridge is a
    THROWAWAY probe — verify_file compiles the staged temp file directly,
    the same staging `_warm_axiom_verifier` uses for migrate candidates."""
    def _probe(ws, *, fq_name, module, whitelist):
        from ..lsp import lifecycle as gw
        r = gw.verify_file(bridge_path, write_olean=False,
                           axioms_for=fq_name, workspace=ws)
        if r.get("error"):
            return False, f"verify infra error: {r['error']}"
        if not r.get("ok"):
            errs = "; ".join(
                d.get("message", "")[:120]
                for d in (r.get("diagnostics") or [])
                if d.get("severity") == "error")[:300]
            return False, errs or "(no error diagnostics)"
        if r.get("axiom_error"):
            return False, f"axiom probe error: {r['axiom_error']}"
        rogue = set(r.get("axioms") or []) - set(whitelist)
        if rogue:
            return False, f"rogue axioms: {sorted(rogue)}"
        return True, ""
    return _probe


def _commit_bridge(patch_text, *, conn, problem, workspace, statement,
                   whitelist, prober=None):
    """Gate B commit (plan §2): stage the agent's bridge as a throwaway probe
    under `Library/`, run `check_root_rederivation` (statement-pin + import-
    closure + build + axiom-whitelist), then delete the probe. On pass, write
    INDEX (Gate B PASSED) — the chain done-marker. The bridge file is NEVER
    committed (it is framework-shaped, not mathlib content); any Library lemma
    the agent fixed en route already persists as a real file. `prober` is
    injectable for offline tests."""
    from . import PipelineResult
    from ..quality.librarian import gates
    import os
    import tempfile

    libdir = workspace / "Library"
    libdir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_bridge_probe_",
                               dir=str(libdir))
    tmp_path = _Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(patch_text)
        module = _library_module_of(f"Library/{tmp_path.name}")
        gate = gates.check_root_rederivation(
            tmp_path, statement=statement, fq_name="main", module=module,
            whitelist=whitelist, workspace=workspace,
            prober=prober or _rederivation_prober(tmp_path))
        if not gate.ok:
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail="; ".join(gate.issues)[:400],
                proposal_md=patch_text)
        _write_library_index(
            conn, problem=problem, workspace=workspace,
            gate_b_line="Gate B (root re-derivation): PASSED — original "
                        "`main` re-derived from the Library alone; axioms "
                        "within whitelist.")
        return PipelineResult(outcome="success", proposal_md=patch_text)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _bridge_probe_text(conn, *, problem, statement, migrated) -> "str | None":
    """v0.3 mechanical Gate B probe (plan §2/§3). Build a throwaway Root that
    imports every migrated Library module, opens every migrated namespace (so
    the original statement's bare symbols — e.g. a `Defs` predicate now living
    in the Library — resolve), and re-derives the original `main` by citing its
    migrated form: `theorem main : <statement> := by exact <main_fq>`. Returns
    None when the migrated root decl has no Library name (cannot build a probe).

    No agent: the migrated `main` IS the original theorem relabelled, so a
    direct citation is the whole derivation. If it does not typecheck, the
    statement needs a non-mechanical bridge (load-bearing Defs / RequestUserAmend)
    — surfaced as a hard fail upstream, not patched by an LLM."""
    root_slug = conn.execute(
        "SELECT slug FROM goals WHERE problem = ? AND origin = 'root' "
        "AND status = 'proved' ORDER BY id LIMIT 1", (problem,)).fetchone()
    root_slug = root_slug["slug"] if root_slug else "main"
    main_row = next((r for r in migrated if r["slug"] == root_slug), None)
    if main_row is None or not main_row["target_name"]:
        return None
    main_fq = main_row["target_name"]
    modules, namespaces = set(), set()
    for r in migrated:
        if r["target_file"]:
            modules.add(_library_module_of(r["target_file"]))
        if r["target_name"] and "." in r["target_name"]:
            namespaces.add(r["target_name"].rsplit(".", 1)[0])
    lines = [f"import {m}" for m in sorted(modules)]
    lines += [f"open {ns}" for ns in sorted(namespaces)]
    lines += ["", f"theorem main : {statement} := by exact {main_fq}", ""]
    return "\n".join(lines)


def _run_bridge(conn, *, problem, workspace, pipeline_id,
                attempts_dir=None, problem_dir=None, prompt_path=None,
                whitelist=None):
    """Gate B step (plan §2 定海神針) — v0.3 MECHANICAL probe, no agent, no LLM.

    Re-derive the original root `theorem main` from the Library alone by citing
    `main`'s migrated form (`_bridge_probe_text`), then `_commit_bridge` stages
    it as a throwaway probe and runs `check_root_rederivation` (statement-pin +
    import-closure + build + axiom-whitelist). On pass writes INDEX (the chain
    done-marker). If the mechanical citation does not typecheck, the
    Library/statement needs a non-mechanical bridge (load-bearing Defs that
    mathlib can't express → RequestUserAmend) — HARD FAIL + flag operator, not a
    silent LLM patch. `attempts_dir`/`problem_dir`/`prompt_path` are unused
    (kept for signature parity with the dispatcher's run_librarian call)."""
    from . import PipelineResult

    migrated = _harvested_decls(conn, problem)
    if not migrated:
        return PipelineResult(outcome="success")  # nothing harvested

    root = conn.execute(
        "SELECT statement FROM goals WHERE problem = ? AND origin = 'root' "
        "AND status = 'proved' ORDER BY id LIMIT 1", (problem,)).fetchone()
    if not root or not (root["statement"] or "").strip():
        return PipelineResult(
            outcome="failed", failure_reason="librarian_no_root",
            failure_detail="no proved root statement for the bridge")
    statement = " ".join(root["statement"].split())

    probe = _bridge_probe_text(
        conn, problem=problem, statement=statement, migrated=migrated)
    if probe is None:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_no_root",
            failure_detail="migrated root decl has no Library name; "
                           "cannot build the Gate B probe")

    res = _commit_bridge(
        probe, conn=conn, problem=problem, workspace=workspace,
        statement=statement, whitelist=whitelist or [])
    if res.outcome != "success":
        # Mechanical re-derivation failed → the Library/statement needs a
        # non-mechanical bridge. Re-frame as the v0.3 operator-flag outcome.
        return PipelineResult(
            outcome="failed", failure_reason="librarian_bridge_not_mechanical",
            failure_detail=(
                "Gate B mechanical re-derivation failed (needs operator / "
                "RequestUserAmend — load-bearing Defs mathlib can't express): "
                + (res.failure_detail or "")[:300]))
    return res


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

    if not _harvested_decls(conn, problem):
        # Nothing was harvested into the Library (e.g. dedup kept nothing,
        # everything cited/dropped). No provenance to record; clean no-op.
        return PipelineResult(outcome="success")

    # Normal harvested chains reach INDEX via the bridge step (Gate B PASSED).
    # This agentless path is a fallback that records provenance without a live
    # Gate B verdict — kept for manual/edge invocation.
    _write_library_index(
        conn, problem=problem, workspace=workspace,
        gate_b_line="Gate B (root re-derivation): not run on this path.")
    return PipelineResult(outcome="success")
