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
