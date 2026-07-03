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

# Declaration head with leading attributes / keyword modifiers. The kind and
# name groups feed the commit parser AND the gateway's submission mirror.
DECL_MODIFIERS = r"(?:noncomputable|private|protected|partial|unsafe)"
DECL_HEAD_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:" + DECL_MODIFIERS + r"[ \t]+)*"
    r"(theorem|def|structure|class)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)

# `:= by sorry` at end-of-line — the fresh-stub detector (MULTILINE anchor
# protects structured patches from false hits).
SORRY_STUB_RE = re.compile(r":=[ \t]*by[ \t]+sorry[ \t]*$", re.MULTILINE)

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
    insertion point as `manifest.inject_defs_opens` (after the last import,
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


def assemble_for_commit(
    content: str, *, problem: str, workspace: Path,
    conn: "sqlite3.Connection | None" = None,
    declared_slugs: "set[str]" = frozenset(),
    carry_opens: "list[str] | tuple[str, ...]" = (),
) -> AssembledFile:
    """ONE normalization rule for every file the framework commits — the
    same transforms in the same order, regardless of which pipeline is
    committing (Builder patch, Backward strategy scratch, Backward sub-goal
    stub, Forward candidate). Every transform is idempotent, so re-running
    on already-normalized text is a no-op.

      1. framework imports  (`import Mathlib` / `Problems.<p>.Defs`)
      2. Defs.lean file-scope opens (notation surface replay)
      3. `carry_opens` — the parent working patch's own opens, for sub-goal
         stubs (validate's unit always gave them these; commit now does too)
      4. proved-sibling imports (when `conn` given) — referenced-but-not-
         imported proved siblings, `declared_slugs` excluded

    validate_file's compilation unit is derived from the same primitives,
    which is what keeps the two sides isomorphic (task #5)."""
    from . import manifest
    text = ensure_framework_imports(content, problem=problem,
                                    workspace=workspace)
    text = manifest.inject_defs_opens(text, problem=problem,
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
                         injected_opens=injected_opens)
