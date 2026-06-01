"""Step 0 — inventory (mechanical).

Reads a problem's proved declarations straight from the DB (same
read-path the TREE renderer uses: `goals` + `strategies` +
`strategy_subgoals`) and emits a structured inventory plus a
human/Strategist-facing annotated-TREE markdown view.

This is the *mechanical* base of the Librarian pipeline (see
docs/internal/librarian_plan.md §5 Step 0). It lists **what exists**;
it makes no judgement (dedup / classify / reshape are later, judging
steps that annotate the same structure).

What it captures per declaration:
  - slug / status / kind / origin
  - reference: goal_id + proofs/L_<slug>.lean path (statement stays
    by-reference — never inlined; full statements are fetched on demand
    at reshape time, see plan §7)
  - deps: child slugs via the goal's winning (succeeded) strategy — the
    *decomposition* DAG

Deliberately NOT captured yet (best-effort / TODO, plan §5 note):
  - raw_conclusion: the `⊢`-conclusion type, extracted from Lean.
  - usage DAG: which lemmas a proof term actually cites (≠ decomposition
    DAG). Library file layout (Step 2) needs this; left for later.

Defs.lean declarations are inventoried separately: they are not goals
(absent from the TREE) but per plan §3 they flow through the same
pipeline as lemmas, so the Librarian must see them.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ...state import db


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------

@dataclass
class InvDecl:
    """One proved declaration in a problem's proof forest."""
    goal_id: int
    slug: str
    status: str
    kind: str           # 'thm' (root) | 'sub'
    origin: str         # 'root' | 'backward' | 'forward'
    lean_path: str | None       # reference into proofs/ — statement by-ref
    deps: list[str] = field(default_factory=list)   # decomposition children
    # Best-effort / later steps (plan §5 Step 0 note); None until filled.
    raw_conclusion: str | None = None


@dataclass
class Inventory:
    problem: str
    decls: list[InvDecl]
    defs_decls: list[str]       # declaration names found in Defs.lean

    @property
    def root(self) -> InvDecl | None:
        for d in self.decls:
            if d.origin == "root":
                return d
        return None


# ---------------------------------------------------------------------
# DB read (mirrors tree.py's read-path; proved-only)
# ---------------------------------------------------------------------

def _proved_goals(
    conn: sqlite3.Connection, problem: str,
) -> list[sqlite3.Row]:
    """Proved goals for a problem, ordered by id. Mirrors tree._load_goals
    but filters to status='proved' — empty/dead/shelved nodes are not
    Library candidates."""
    return list(conn.execute(
        "SELECT id, slug, status, kind, origin, lean_path "
        "FROM goals WHERE problem = ? AND status = 'proved' "
        "ORDER BY id",
        (problem,),
    ))


def _winning_strategy_subgoals(
    conn: sqlite3.Connection, problem: str,
) -> dict[int, list[int]]:
    """Map goal_id -> ordered child_goal_id list via its winning
    (status='succeeded') strategy. This is the *decomposition* DAG edge
    set. A goal with no succeeded strategy (leaf / Builder-proved) maps
    to an empty list."""
    rows = list(conn.execute(
        "SELECT s.goal_id AS goal_id, sg.subgoal_id AS subgoal_id "
        "FROM strategies s "
        "JOIN goals g ON s.goal_id = g.id "
        "JOIN strategy_subgoals sg ON sg.strategy_id = s.id "
        "WHERE g.problem = ? AND s.status = 'succeeded' "
        "ORDER BY s.goal_id, sg.position",
        (problem,),
    ))
    out: dict[int, list[int]] = {}
    for r in rows:
        out.setdefault(r["goal_id"], []).append(r["subgoal_id"])
    return out


# ---------------------------------------------------------------------
# Defs.lean declaration scan
# ---------------------------------------------------------------------

# Top-level declarations in Defs.lean. Matches the keyword + name; good
# enough to list what the Librarian must consider migrating (plan §3:
# Defs decls flow through the same pipeline as lemmas).
_DEFS_DECL_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|@\[[^\]]*\]\s*)*"
    r"(def|theorem|lemma|abbrev|structure|class|instance|inductive)\s+"
    r"([A-Za-z_][A-Za-z0-9_'.]*)",
    re.MULTILINE,
)


def defs_decls(workspace: Path, problem: str) -> list[str]:
    """Names of top-level declarations in Problems/<problem>/Defs.lean.
    Empty if Defs.lean is absent or declares nothing (e.g. SVD, whose
    Defs.lean is namespace + comment only)."""
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if not defs_path.exists():
        return []
    text = defs_path.read_text(encoding="utf-8")
    out: list[str] = []
    for m in _DEFS_DECL_RE.finditer(text):
        name = m.group(2)
        if name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------------
# Usage DAG (proof-term citation edges, ≠ decomposition deps)
# ---------------------------------------------------------------------

# A `proofs/`-local import: `import Problems.<p>.proofs.<MOD>` → captures
# MOD (an `L_<slug>` alias or a `_strategy_s<NNNN>` proof module).
_PROOFS_IMPORT_RE = re.compile(
    r"^\s*import\s+Problems\.[\w.]+\.proofs\.([A-Za-z_]\w*)\s*$",
    re.MULTILINE,
)


def usage_graph(
    workspace: Path, problem: str, slugs, *,
    alias_map: "dict[str, str] | None" = None,
) -> "dict[str, set[str]]":
    """Map each slug to the set of sibling slugs its proof ACTUALLY cites —
    the *usage* DAG, distinct from `InvDecl.deps` (the *decomposition* DAG).

    Asterism proofs are layered: `proofs/L_<X>.lean` is an alias
    `def X := @…s<N>` importing `_strategy_s<N>.lean`, and the strategy file
    imports `proofs/L_<Y>.lean` for each sibling lemma Y its proof term uses.
    So a usage edge X→Y is read by walking X's alias into its strategy
    file(s) — recursing through any nested `_strategy_*` imports — and
    collecting the `L_<Y>` imports found there. A direct (non-alias) proof
    that imports `L_<Y>` yields the edge directly.

    `alias_map` remaps an imported sibling slug to its canonical placed slug
    (e.g. a dedup `merge`: the proof imports `L_<Y>` but Y was merged into a
    kept canonical Z, and the migrated reference resolves to Z). Without it a
    proof that cites a merged-away sibling would record no edge and the
    user/dep pair would mis-order. Only edges whose (remapped) target is in
    `slugs` are kept — cited-mathlib / external siblings are never placed, so
    they can't order a file. Missing files are skipped: the edge set is
    best-effort and the build gate stays the final arbiter.

    Why this matters: Lean is order-sensitive, so within one Library file a
    decl must be emitted AFTER every same-file sibling it cites, and a file
    must migrate AFTER the files it cites. `InvDecl.deps` (winning-strategy
    subgoals) is the decomposition structure, NOT the proof-term reference
    structure — ordering by it leaves forward references that fail to build.
    """
    slug_set = set(slugs)
    alias_map = alias_map or {}
    proofs = db.problem_dir(workspace, problem) / "proofs"

    def imports_of(mod: str) -> list[str]:
        p = proofs / f"{mod}.lean"
        if not p.exists():
            return []
        return _PROOFS_IMPORT_RE.findall(p.read_text(encoding="utf-8"))

    out: dict[str, set[str]] = {s: set() for s in slug_set}
    for x in slug_set:
        seen_mods: set[str] = set()
        frontier = [f"L_{x}"]
        while frontier:
            mod = frontier.pop()
            if mod in seen_mods:
                continue
            seen_mods.add(mod)
            for imp in imports_of(mod):
                if imp.startswith("L_"):
                    y = imp[2:]
                    y = alias_map.get(y, y)   # merged sibling → canonical
                    if y in slug_set and y != x:
                        out[x].add(y)
                elif imp.startswith("_strategy_"):
                    frontier.append(imp)   # walk the strategy chain
    return out


def referenced_slugs(
    workspace: Path, problem: str, slugs,
) -> "dict[str, set[str]]":
    """Per slug, the RAW set of sibling slugs its proof imports — same
    alias→strategy→`L_<sub>` walk as `usage_graph` but UNfiltered and
    UNremapped (keeps non-keep / dropped / merged siblings). Used to surface
    the non-keep siblings a decl cites — with their dedup verdict→citation —
    to the migrate agent, so it knows what to redirect a `sorry`-hole's
    reference to (G3)."""
    proofs = db.problem_dir(workspace, problem) / "proofs"

    def imports_of(mod: str) -> list[str]:
        p = proofs / f"{mod}.lean"
        if not p.exists():
            return []
        return _PROOFS_IMPORT_RE.findall(p.read_text(encoding="utf-8"))

    out: dict[str, set[str]] = {}
    for x in slugs:
        refs: set[str] = set()
        seen_mods: set[str] = set()
        frontier = [f"L_{x}"]
        while frontier:
            mod = frontier.pop()
            if mod in seen_mods:
                continue
            seen_mods.add(mod)
            for imp in imports_of(mod):
                if imp.startswith("L_"):
                    if imp[2:] != x:
                        refs.add(imp[2:])
                elif imp.startswith("_strategy_"):
                    frontier.append(imp)
        out[x] = refs
    return out


# ---------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------

def build_inventory(
    conn: sqlite3.Connection, workspace: Path, problem: str,
) -> Inventory:
    """Assemble the Step-0 inventory for a problem from the DB."""
    goals = _proved_goals(conn, problem)
    by_id = {g["id"]: g for g in goals}
    proved_ids = set(by_id)
    edges = _winning_strategy_subgoals(conn, problem)

    decls: list[InvDecl] = []
    for g in goals:
        # deps = winning-strategy children that are themselves proved
        # (drop dead/shelved branches — they aren't part of the proof).
        child_slugs = [
            by_id[cid]["slug"]
            for cid in edges.get(g["id"], [])
            if cid in proved_ids
        ]
        decls.append(InvDecl(
            goal_id=g["id"],
            slug=g["slug"],
            status=g["status"],
            kind=g["kind"],
            origin=g["origin"],
            lean_path=g["lean_path"],
            deps=child_slugs,
        ))

    return Inventory(
        problem=problem,
        decls=decls,
        defs_decls=defs_decls(workspace, problem),
    )


# ---------------------------------------------------------------------
# Annotated-TREE markdown view (plan §7)
# ---------------------------------------------------------------------

def render_view(inv: Inventory) -> str:
    """Human / Strategist-facing markdown. Shows slug + status (+ later
    verdict/target columns once Steps 1-2 annotate). Full statements are
    NOT shown — by-reference only (plan §7)."""
    lines: list[str] = []
    lines.append(f"# {inv.problem} — Librarian inventory (Step 0)")
    lines.append("")
    lines.append(f"_Mechanical inventory: {len(inv.decls)} proved "
                 f"declaration(s), {len(inv.defs_decls)} Defs decl(s)._")
    lines.append("")

    root = inv.root
    if root is not None:
        lines.append(f"**root**: `{root.slug}` (goal {root.goal_id})")
        lines.append("")

    lines.append("## Declarations")
    lines.append("")
    lines.append("| slug | origin | goal | deps |")
    lines.append("|---|---|---|---|")
    for d in inv.decls:
        deps = ", ".join(f"`{s}`" for s in d.deps) if d.deps else "—"
        lines.append(
            f"| `{d.slug}` | {d.origin} | {d.goal_id} | {deps} |"
        )
    lines.append("")

    lines.append("## Defs.lean declarations")
    lines.append("")
    if inv.defs_decls:
        for name in inv.defs_decls:
            lines.append(f"- `{name}`")
    else:
        lines.append("_(none — Defs-free; root re-derivation is trivially "
                     "Defs-free, plan §2 Gate B)_")
    lines.append("")
    return "\n".join(lines)
