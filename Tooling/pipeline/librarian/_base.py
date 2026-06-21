"""librarian._base — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Verify (semantic checks before commit)
# ---------------------------------------------------------------------

# mathlib's `linter.style.longFile` warns at 1500 lines — oversize files are
# a PR blocker, and a cleanup-time file-split would be the hairiest possible
# stage (move decls + rewire imports + consumers). Root-cause instead: cap the
# file size at CLASSIFY time so the giant file is never born. The budget is on
# the SOURCE-line estimate (sum of the decls' proof-file line counts, which
# overcounts a little — each L_ file carries its own import header); polish
# later adds docstrings/variables (~15%), so 1100 estimated lands well under
# 1500 final. Born from BT's Equidecomp.lean: 147 decls / 3568 lines in one
# classify-planned file (2026-06-11).
CLASSIFY_FILE_LINE_BUDGET = 1100


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
# build+axiom step is injectable (`probe_verifier`) so it is unit-
# testable without a live gateway, same pattern as gates.check_root_
# rederivation's `prober`.



@dataclass
class MigrateResult:
    ok: bool
    detail: str = ""


@dataclass
class MigratedDecl:
    """A top-level declaration found in a migrate patch: its keyword
    (`def`/`theorem`/…), bare name, and namespace-qualified name."""
    kind: str | None
    name: str
    fq_name: str


# ---------------------------------------------------------------------
# Stage D — run_librarian outer entry (work-kind dispatch)
# ---------------------------------------------------------------------
# dedup / classify: one-shot spawn -> parse -> verify -> commit (mirrors
#   strategist.run_strategist).
# migrate: LSP + session-retry loop (mirrors builder via
#   run_with_session_retries); commit gate = migrate_commit_gate.

WORK_KINDS: frozenset[str] = frozenset(
    {"dedup", "classify", "migrate", "cleanup", "bridge"})


def _import_sort_key(module: str) -> "tuple[int, str]":
    """Sort key placing Mathlib (and any other external dep) BEFORE the project's
    own `Library.*` modules. Lean instance resolution is import-ORDER-sensitive:
    with `import Mathlib` listed AFTER a `Library.*` sibling, some instances fail
    to synthesize (`ContinuousSMul ℝ ℂ`, `IsScalarTower ℝ ℝ ℂ`) and the module
    stops building (residue ResiduePathIntegral, 2026-06-21); Mathlib first fixes
    it. Alphabetical within each group. `module` is the bare module name (strip
    the leading `import ` first)."""
    return (module.startswith("Library."), module)


def _sorted_import_lines(lines: "set[str] | list[str]") -> "list[str]":
    """`import …` lines ordered Mathlib-first (see `_import_sort_key`)."""
    return sorted(lines, key=lambda l: _import_sort_key(l.split()[-1]))


class _MechIntegrityError(Exception):
    """A decl's source can't be located where the DB says it should be —
    file↔DB drift (CLAUDE.md rule 10), not a 'needs the LLM' case. Surfaced
    as a loud, distinct migrate failure rather than masked by a cold
    from-scratch spawn (which would hide the corruption)."""


def _code_normalized(s: str) -> str:
    """Whitespace-normalized CODE of a Lean snippet: block comments and
    docstrings (`/- … -/`, `/-- … -/`) and line comments (`-- …`) stripped
    first. Two decls equal here produce the same kernel object."""
    s = re.sub(r"/-.*?-/", " ", s, flags=re.DOTALL)
    s = re.sub(r"--[^\n]*", " ", s)
    return " ".join(s.split())
