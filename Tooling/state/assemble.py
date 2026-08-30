"""Shared Lean-file assembly vocabulary — the SINGLE source of truth for the
text transforms and line-scan regexes that both sides of the validate/commit
boundary apply to an agent's Lean output.

WHY THIS EXISTS — the validate≠commit drift class. An agent's file is
"normalized" before elaboration (framework imports prepended, Defs opens
injected, sibling stubs resolved) in TWO places: the LSP gateway's
`validate_file` (the agent's pre-submit check) and each pipeline's commit
path (what actually lands on disk). Historically each side hand-mirrored the
other's regexes and injection rules — the gateway kept `_GW_*` copies with a
"mirror of pipeline.X" comment — and every divergence was a class of
false-green ("validate passed, lake build died") or false-red ("validate
complained, commit would have auto-fixed it"), each costing an agent a full
retry round. This module makes the shared pieces structural: one constant,
one function, imported by both sides.

Layering: this is a `state`-layer LEAF (re + pathlib + state.db only). The
gateway process deliberately never imports the heavy `pipeline` package —
importing `state.assemble` keeps that rule intact. Pipeline modules re-export
these names under their historical local names so call sites and tests keep
working.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import db

# ── shared line-scan regexes (formerly duplicated as gateway `_GW_*`) ──

# `import Problems.<p>.proofs.L_<slug>` — the citation line the cite gate
# classifies (SoT for the VERDICT is `db.classify_cited_slug`; this is the
# line scan both sides run).
PROBLEM_IMPORT_RE = re.compile(
    r"^\s*import\s+Problems\.([A-Za-z_][\w.]*)\.proofs\.L_([a-z][a-z0-9_]*)\s*$",
    re.MULTILINE,
)

# Sub-goal / Forward slug shape (lake module names must survive the file
# path; camelCase builds break — see forward slug memories).
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SLUG_MAX_LEN = 60

# Bare decl-kind prefix (no anchors/modifiers) — the historical
# `_skeleton._DECL_HEAD_RE` building block for name-targeted searches
# (`signature_prefix`, skeleton construction). Distinct from DECL_HEAD_RE
# below, which is the full anchored head matcher.
DECL_KIND_RE_SRC = r"\b(theorem|def|structure|class|inductive|instance)\s+"

# Declaration head with leading attributes / keyword modifiers. The kind and
# name groups feed the commit parser AND the gateway's submission mirror.
DECL_MODIFIERS = r"(?:noncomputable|private|protected|partial|unsafe)"
# Name group is `\w` (unicode) + Lean's trailing `'`/`!`/`?`: an ASCII-only
# class truncated `td_gen_maps_to_sigma_ι` at the ι, so the gateway mirror
# validated the ASCII PREFIX (which passes SLUG_RE) while commit rejected
# the real name only after a full build (2026-07-05 audit). Capturing the
# full identifier lets SLUG_RE fail it in the mirror, pre-commit.
DECL_HEAD_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:" + DECL_MODIFIERS + r"[ \t]+)*"
    r"(theorem|def|structure|class|inductive|instance)[ \t]+([A-Za-z_][\w'!?]*)",
    re.MULTILINE,
)

# `:= by sorry` at end-of-line — the fresh-stub detector (MULTILINE anchor
# protects structured patches from false hits).
SORRY_STUB_RE = re.compile(r":=[ \t]*by[ \t]+sorry[ \t]*$", re.MULTILINE)


# ── one brick, one declaration (owner ruling 2026-08-30, task #231) ──
#
# A sub-goal stub carries the parent's preamble (imports / opens /
# variables) so its statement elaborates standalone — deliberate. Helper
# `def`s and `instance`s the agent wrote to STATE the sub-goal rode along
# the same way, and the promotion to `def <slug> := @s<N>` keeps only the
# imports: the helper vanished and every strategy that cited it broke
# (seven consumers at one promotion, 2026-08-28: `fin5_weight`; `Fintype
# fin4_family`; `six_point_row_zero_encode`). Anonymous instances count
# as `<instance>`.

_ANON_INSTANCE_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:" + DECL_MODIFIERS + r"[ \t]+)*"
    r"instance[ \t]*(?::|\[|\{|\()", re.MULTILINE)

# Every named declaration form, not just the commit parser's subset:
# experiment 6 (2026-08-30, 1,132 local stubs) found the helpers agents
# write include `abbrev` and `opaque`, which DECL_HEAD_RE does not know.
_ANY_DECL_HEAD_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:" + DECL_MODIFIERS + r"[ \t]+)*"
    r"(theorem|lemma|def|abbrev|opaque|axiom|structure|class|inductive|instance)"
    r"[ \t]+([A-Za-z_][\w'!?]*)",
    re.MULTILINE,
)


def extra_decls(stub_text: str, slug: str) -> list[str]:
    """Names of every top-level declaration in `stub_text` other than
    the stub's own `slug`, in file order; anonymous instances appear as
    `<instance>`. Comments are stripped first. Empty = a clean stub."""
    text = strip_comments(stub_text)
    found: list[tuple[int, str]] = []
    for m in _ANY_DECL_HEAD_RE.finditer(text):
        name = m.group(2)
        if name != slug:
            found.append((m.start(), name))
    for m in _ANON_INSTANCE_RE.finditer(text):
        found.append((m.start(), "<instance>"))
    return [name for _, name in sorted(found)]


def extra_decls_message(slug: str, extras: list[str]) -> str:
    names = ", ".join(f"`{n}`" for n in extras)
    return (f"sub-goal `{slug}` declares more than itself ({names}). One "
            f"brick, one declaration: when `{slug}` is proved its file becomes "
            f"a one-line alias and everything else in it disappears — any "
            f"strategy that cited those names breaks. Make each helper its own "
            f"brick (a `def` sub-goal of its own, cited by import) or put a "
            f"shared definition in Defs.lean, then restate `{slug}` against it.")

# The strategy skeleton's annotation placeholder (2026-08-24, the
# annotation-autopsy fix): seeded above the theorem so writing the
# annotation is a FILL, not an instruction remembered from the prompt's
# far end. Shared SoT — the skeleton writes it, the commit gate and the
# gateway's submission mirror both refuse it as an annotation (an
# unreplaced placeholder is missing metadata, not documentation).
ANNOTATION_PLACEHOLDER = "-- STRATEGY: replace me"
ANNOTATION_PLACEHOLDER_LINE = (
    ANNOTATION_PLACEHOLDER
    + " — one-line summary, then why it closes the goal")


def strip_annotation_placeholder(leading: str) -> str:
    """Comment block minus placeholder lines — what the AGENT wrote."""
    return "\n".join(
        ln for ln in leading.splitlines()
        if not ln.strip().startswith(ANNOTATION_PLACEHOLDER))

THEOREM_LINE_RE = re.compile(r"(?m)^\s*theorem\s+\S+")


# ── framework import injection (formerly backward._ensure_imports_subgoal
#    + its gateway mirror _needed_imports/_ensure_imports) ──

def needed_framework_imports(content: str, *, problem: str,
                             workspace: Path) -> list[str]:
    """The framework imports (`import Mathlib`, `import Problems.<p>.Defs`)
    missing from `content`. `Defs` only when the problem ships one."""
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if defs_path.exists():
        defs_module = f"Problems.{problem}.Defs"
        if not re.search(rf"(?m)^import\s+{re.escape(defs_module)}\b",
                         content):
            needed.append(f"import {defs_module}")
    return needed


def ensure_framework_imports(content: str, *, problem: str,
                             workspace: Path) -> str:
    """Prepend the missing framework imports. Idempotent.

    Without `Defs`, problem-level custom symbols (e.g. SG's `Collinear`)
    are unresolved; a strict agent following the prompt's "framework
    auto-injects imports" instruction writes none, and Lean falls back to
    whatever `import Mathlib` exposes, breaking elaboration."""
    needed = needed_framework_imports(content, problem=problem,
                                      workspace=workspace)
    if not needed:
        return content
    return "\n".join(needed) + "\n\n" + content


# ── locked-signature vocabulary (formerly pipeline/_skeleton.py-only;
#    moved here so the gateway's submission mirror can run the SAME
#    comparison the Backward commit gate runs — task #5 D-lite) ──

_LET_LIKE_RE = re.compile(r"(?:let|letI|have|haveI)\b")


def body_assign_index(text: str, pos: int) -> int:
    """Index of the `:=` that separates a declaration's signature from
    its body, scanning from `pos`; -1 when absent.

    Depth-walks paren/brace/bracket nesting, AND counts top-level
    `let`/`letI`/`have`/`haveI` binders in the type: each owns the next
    top-level `:=` (`… : let α := liminf …, r ≤ (α-1)/α²  := by sorry`
    — the first `:=` is the let's, the second is the body's; splitting
    at the first truncated the seeded skeleton mid-goal, PutnamCmp b6_1
    `gap_bounds_growth_ratio` 2026-07-19)."""
    n = len(text)
    depth = 0
    pending = 0  # top-level let/have binders awaiting their `:=`
    while pos < n - 1:
        ch = text[pos]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0:
            if ch == ":" and text[pos + 1] == "=":
                if pending:
                    pending -= 1
                    pos += 2
                    continue
                return pos
            if ch in "lh" and (pos == 0 or not (
                    text[pos - 1].isalnum() or text[pos - 1] in "_.")):
                mm = _LET_LIKE_RE.match(text, pos)
                if mm:
                    pending += 1
                    pos = mm.end()
                    continue
        pos += 1
    return -1


def signature_prefix(text: str, name: str) -> str:
    """Return the substring `<kind> <name> <binders> : <type>` (up to
    but not including the body's `:=`). `<kind>` ∈ {theorem, def,
    structure, class, inductive, instance}. Returns "" if no matching
    declaration head found.

    Body-`:=` detection is `body_assign_index`: balanced-depth walk
    plus let/have binder counting, so a `let x := …` inside the type
    does not truncate the signature."""
    m = re.search(DECL_KIND_RE_SRC + re.escape(name) + r"\b", text)
    if not m:
        return ""
    idx = body_assign_index(text, m.end())
    if idx < 0:
        return text[m.start():]
    return text[m.start():idx]


def normalize_signature(s: str) -> str:
    """Collapse all whitespace runs to single spaces. Lets agents reformat
    indentation freely without tripping the diff check; only meaningful
    edits (binder names, types, theorem name) remain detectable."""
    return re.sub(r"\s+", " ", s).strip()


# ── comment stripping + split-visibility prediction (task #5 D-lite) ──

_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/-.*?-/", re.DOTALL)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub(" ", _BLOCK_COMMENT_RE.sub(" ", text))


def referenced_batch_slugs(
    text: str, batch_slugs: "list[str] | dict[str, str]",
    *, exclude: "str | None" = None,
) -> "list[str]":
    """The batch slugs `text` references — comment-stripped, whole-token
    match against the KNOWN batch decl names (a finite exact list, not
    open-ended name guessing). Single-text primitive under
    `batch_reference_edges`; the gateway's commit-header mirror runs the
    SAME scan so validate predicts exactly the imports commit injects."""
    body = strip_comments(text)
    return sorted(
        b for b in batch_slugs
        if b != exclude and re.search(rf"\b{re.escape(b)}\b", body))


def batch_reference_edges(
    stub_texts: "dict[str, str]",
) -> "dict[str, list[str]]":
    """slug → sorted batch siblings its comment-stripped text references
    (see `referenced_batch_slugs`). This is the intra-batch import DAG
    the commit side injects mechanically (task #84): the validate unit
    inlines all stubs so cross-references always resolve there; at
    commit each stub is its own module and needs the edge as an `import`
    line. A false positive only over-imports (harmless unless it closes
    a cycle — see `batch_reference_cycles`)."""
    edges: "dict[str, list[str]]" = {}
    for a_slug, a_text in stub_texts.items():
        refs = referenced_batch_slugs(a_text, stub_texts, exclude=a_slug)
        if refs:
            edges[a_slug] = refs
    return edges


def batch_reference_cycles(
    edges: "dict[str, list[str]]",
) -> "list[list[str]]":
    """Cycles in the batch reference graph (iterative DFS, one witness
    path per cycle found). A cycle admits NO import order — Lean modules
    cannot mutually import — so it must be rejected/restructured, never
    injected."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in edges}
    cycles: "list[list[str]]" = []
    for root in sorted(edges):
        if color.get(root, WHITE) != WHITE:
            continue
        stack: "list[tuple[str, int]]" = [(root, 0)]
        path: "list[str]" = []
        while stack:
            node, idx = stack.pop()
            if idx == 0:
                color[node] = GRAY
                path.append(node)
            nbrs = edges.get(node, [])
            advanced = False
            for j in range(idx, len(nbrs)):
                nxt = nbrs[j]
                c = color.get(nxt, WHITE)
                if c == GRAY:
                    cycles.append(path[path.index(nxt):] + [nxt])
                elif c == WHITE:
                    stack.append((node, j + 1))
                    stack.append((nxt, 0))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                path.pop()
    return cycles


def split_visibility_issues(
    stub_texts: "dict[str, str]", *, problem: str,
) -> "list[dict]":
    """Predict the post-commit SPLIT failures the single-unit probe cannot
    see. 2026-07-10 (task #84): the framework now INJECTS the acyclic
    intra-batch import edges at commit (`assemble_for_commit
    extra_imports` via `batch_reference_edges`), so a plain
    cross-reference is no longer the agent's problem — the historical
    "hand-write the import" hand-back (and its whole-spawn burns:
    sphere `sphere_equator_equiv_forward_cont`, MV `mv_delta`) is gone.
    What no injection can fix is a CYCLE: mutually-referencing stubs
    admit no module import order. Only cycles are reported now."""
    issues: "list[dict]" = []
    for cyc in batch_reference_cycles(batch_reference_edges(stub_texts)):
        chain = " → ".join(cyc)
        issues.append({
            "file": f"new_{cyc[0]}.lean",
            "cycle": cyc,
            "severity": "error",
            "hint": (f"batch stubs reference each other in a cycle "
                     f"({chain}) — Lean modules cannot mutually import, "
                     f"so no placement order exists. Merge the statements "
                     f"into one sub-goal, or restate one side so it does "
                     f"not mention the other."),
        })
    return issues


# ── open-line carry (formerly gateway-only `_harvest_open_lines`) ──

def harvest_open_lines(text: str) -> list[str]:
    """Every file-scope `open ...` line in `text`, verbatim (excludes the
    scope-limited `open X in <decl>` form). validate_file has always carried
    the working patch's opens into the probed sub-goal stubs; the commit
    side historically did NOT — the `open scoped ∂`-class false-greens —
    so `assemble_for_commit` now carries them via `carry_opens`."""
    out: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("open ") and not re.search(r"\bin\b\s*$", s):
            out.append(s)
    return out


def inject_open_lines(content: str, opens: "list[str]") -> str:
    """Insert verbatim `open ...` lines missing from `content` — same
    insertion point as `intent.inject_defs_opens` (after the last import,
    before the first `namespace`; file head as fallback). Idempotent by
    exact-line match."""
    missing = [o for o in opens
               if not re.search(rf"(?m)^\s*{re.escape(o)}\s*$", content)]
    if not missing:
        return content
    lines = content.splitlines()
    last_imp = max((i for i, ln in enumerate(lines)
                    if ln.startswith("import ")), default=-1)
    if last_imp >= 0:
        at = last_imp + 1
    else:
        at = next((i for i, ln in enumerate(lines)
                   if ln.lstrip().startswith("namespace ")), 0)
    lines[at:at] = list(missing)
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


# ── proved-sibling import injection (formerly pipeline._cite_gate only) ──

def inject_sibling_imports(
    conn: sqlite3.Connection, content: str, *, problem: str,
    declared_slugs: "set[str]" = frozenset(),
) -> "tuple[str, list[str]]":
    """Forgiving auto-fix for the common `unknown identifier` death: the
    text references a PROVED same-problem sibling's decl name but lacks its
    `import Problems.<problem>.proofs.L_<slug>` line. Add the import for
    every such sibling. Same-problem only — cross-problem nodes are not
    citable, so this never widens the whitelist. Returns
    (new_text, added_slugs)."""
    proved = {
        r["slug"] for r in conn.execute(
            "SELECT slug FROM goals WHERE problem = ? AND status = 'proved'"
            " AND alias_target_id IS NULL", (problem,))
    } - set(declared_slugs)
    if not proved:
        return content, []
    already = set(re.findall(
        r"(?m)^\s*import\s+Problems\." + re.escape(problem)
        + r"\.proofs\.L_([a-z][a-z0-9_]*)\s*$", content))
    add = sorted(
        s for s in proved
        if s not in already
        and re.search(r"\b" + re.escape(s) + r"\b", content))
    if not add:
        return content, []
    lines = content.splitlines()
    last_imp = max((i for i, ln in enumerate(lines)
                    if ln.startswith("import ")), default=-1)
    lines[last_imp + 1:last_imp + 1] = [
        f"import Problems.{problem}.proofs.L_{s}" for s in add]
    new_text = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
    return new_text, add


# ── the unified commit-side normalization (task #5 Step B) ──

@dataclass
class AssembledFile:
    """Result of `assemble_for_commit`: the to-be-committed text plus what
    was injected (for the caller's logging / forensics)."""
    text: str
    injected_sibling_imports: "list[str]" = field(default_factory=list)
    injected_opens: "list[str]" = field(default_factory=list)
    injected_extra_imports: "list[str]" = field(default_factory=list)


def assemble_for_commit(
    content: str, *, problem: str, workspace: Path,
    conn: "sqlite3.Connection | None" = None,
    declared_slugs: "set[str]" = frozenset(),
    carry_opens: "list[str] | tuple[str, ...]" = (),
    extra_imports: "list[str] | tuple[str, ...]" = (),
) -> AssembledFile:
    """ONE normalization rule for every file the framework commits — the
    same transforms in the same order, regardless of which pipeline is
    committing (Builder patch, Backward strategy scratch, Backward sub-goal
    stub, Forward candidate). Every transform is idempotent, so re-running
    on already-normalized text is a no-op.

      1. framework imports  (`import Mathlib` / `Problems.<p>.Defs`)
      2. `extra_imports` — caller-derived import lines, verbatim (task #84:
         the intra-batch reference edges from `batch_reference_edges`;
         exact-line idempotent)
      3. Defs.lean file-scope opens (notation surface replay)
      4. `carry_opens` — the parent working patch's own opens, for sub-goal
         stubs (validate's unit always gave them these; commit now does too)
      5. proved-sibling imports (when `conn` given) — referenced-but-not-
         imported proved siblings, `declared_slugs` excluded

    validate_file's compilation unit is derived from the same primitives,
    which is what keeps the two sides isomorphic (task #5)."""
    from . import intent as intent_mod
    text = ensure_framework_imports(content, problem=problem,
                                    workspace=workspace)
    injected_extra: list[str] = []
    if extra_imports:
        missing = [imp for imp in extra_imports
                   if not re.search(rf"(?m)^\s*{re.escape(imp)}\s*$", text)]
        if missing:
            lines = text.splitlines()
            last_imp = max((i for i, ln in enumerate(lines)
                            if ln.startswith("import ")), default=-1)
            lines[last_imp + 1:last_imp + 1] = missing
            text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            injected_extra = missing
    text = intent_mod.inject_defs_opens(text, problem=problem,
                                      workspace=workspace)
    injected_opens: list[str] = []
    if carry_opens:
        before = text
        text = inject_open_lines(text, list(carry_opens))
        if text != before:
            injected_opens = [o for o in carry_opens if o not in before]
    added: list[str] = []
    if conn is not None:
        text, added = inject_sibling_imports(
            conn, text, problem=problem, declared_slugs=declared_slugs)
    return AssembledFile(text, injected_sibling_imports=added,
                         injected_opens=injected_opens,
                         injected_extra_imports=injected_extra)
