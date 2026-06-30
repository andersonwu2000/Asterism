"""Step 0 — inventory (mechanical).

Reads a problem's proved declarations straight from the DB (same
read-path the TREE renderer uses: `goals` + `strategies` +
`strategy_subgoals`) and emits a structured inventory plus a
human/Strategist-facing annotated-TREE markdown view.

This is the *mechanical* base of the Librarian pipeline (see
docs/archive/design/librarian_plan.md §5 Step 0). It lists **what exists**;
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

# Lean comments — block `/- … -/` (incl. `/-! … -/` docstrings) and line `-- …`.
# Stripped BEFORE decl-name scanning so prose like "the one analytic lemma of the
# bridge" in a Defs docstring is not mis-read as a declaration named `of`
# (2026-06-30: a phantom `of` decl from a Defs docstring broke the mechanical
# migrate — `of` is a Lean soft keyword, so the relabelled `…PullbackBoundAux.of`
# failed to parse and STALLed the chain).
_COMMENT_RE = re.compile(r"/-.*?-/|--[^\n]*", re.DOTALL)


def defs_decls(workspace: Path, problem: str) -> list[str]:
    """Names of top-level declarations in Problems/<problem>/Defs.lean.
    Empty if Defs.lean is absent or declares nothing (e.g. SVD, whose
    Defs.lean is namespace + comment only)."""
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if not defs_path.exists():
        return []
    text = _COMMENT_RE.sub("", defs_path.read_text(encoding="utf-8"))
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

# A `Problems.<p>.Defs` import: the proof uses the problem's definitions. Defs
# decls are normal Library decls (classified + migrated like any lemma), but
# they are referenced by bare NAME (not via a `proofs/L_<x>` import), so a usage
# edge to a Defs decl is read by spotting this import + the decl's name in the
# body — NOT by the proofs-import walk. Without this the dependency graph misses
# every edge into a migrated Defs decl (mis-orders files, drops it from a hole's
# seed import closure).
_DEFS_IMPORT_RE = re.compile(
    r"^\s*import\s+Problems\.[\w.]+\.Defs\s*$",
    re.MULTILINE,
)


def resolve_ci(directory: Path, filename: str) -> "Path | None":
    """Resolve `directory/filename` case-INsensitively → the actual path, or
    None if no case-variant exists. proofs/ files are written `L_<slug>.lean`
    (uppercase) by the framework, but on a case-insensitive FS a pre-existing
    lowercase `l_<slug>.lean` is preserved — so the DB/code's uppercase name
    and the on-disk name can differ in case. Reads must not assume either: an
    exact hit wins; otherwise scan the dir for a case-fold match. (On a
    case-sensitive FS the framework's writes are uppercase-consistent, so the
    exact hit fires; the scan only matters for legacy/Windows-drifted files.)"""
    exact = directory / filename
    if exact.exists():
        return exact
    target = filename.lower()
    try:
        for p in directory.iterdir():
            if p.name.lower() == target:
                return p
    except OSError:
        pass
    return None


def usage_graph(
    workspace: Path, problem: str, slugs, *,
    alias_map: "dict[str, str] | None" = None,
    root_source: "tuple[str, str] | None" = None,
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
    # The root decl's proof lives in Root.lean, not proofs/L_<slug>.lean, so
    # its `L_<root>` module is read from there — else the root's sibling
    # citations (and therefore Main.lean's file dependencies) are invisible
    # and Main is mis-ordered before the files it imports.
    root_mod = f"L_{root_source[0]}" if root_source else None
    root_path = Path(root_source[1]) if root_source else None

    # Defs decls that landed in the layout: referenced by bare NAME (not a
    # `proofs/L_<x>` import), so their usage edges are read from the body, below.
    defs_names = {d for d in defs_decls(workspace, problem) if d in slug_set}

    def read_mod(mod: str) -> "str | None":
        if root_mod and mod == root_mod:
            p = root_path
        else:
            p = resolve_ci(proofs, f"{mod}.lean")   # L_/l_ case-insensitive
        return p.read_text(encoding="utf-8") if (p and p.exists()) else None

    # `sN` (a strategy proof-term) → the kept lemma slug whose proof IS that
    # strategy (`def <slug> := @sN`). A strategy body that cites another
    # strategy's RAW term (instead of that lemma's name) still depends on the
    # LEMMA — record the edge to it (below), so the lemma stays reachable
    # instead of being walked-through-and-dropped.
    _alias_re = re.compile(r"def\s+\w+\s*:=\s*@?Problems\.[\w.]+\.(s\d+)")
    strat_alias: dict[str, str] = {}
    for s in slug_set:
        t = read_mod(f"L_{s}")
        if t:
            m = _alias_re.search(t)
            if m:
                strat_alias[m.group(1)] = s

    out: dict[str, set[str]] = {s: set() for s in slug_set}
    for x in slug_set:
        seen_mods: set[str] = set()
        frontier = [f"L_{x}"]
        while frontier:
            mod = frontier.pop()
            if mod in seen_mods:
                continue
            seen_mods.add(mod)
            text = read_mod(mod)
            if text is None:
                continue
            for imp in _PROOFS_IMPORT_RE.findall(text):
                if imp[:2].lower() == "l_":   # L_<sub> / l_<sub> (case-insensitive)
                    raw_y = imp[2:]
                    y = alias_map.get(raw_y, raw_y)   # merged sibling → canonical
                    if y == x:
                        # `raw_y` was dedup-merged INTO x itself: it is dropped,
                        # so x's migrated body must INLINE raw_y's proof — and
                        # therefore transitively depends on whatever raw_y's
                        # proof cites. Walk into raw_y's proof (don't just drop
                        # the self-edge), else a cross-file dep that only appears
                        # through the inlined self-merged sibling is lost from
                        # the layout (real Jordan: block_jordan_basis_exists
                        # cites assemble_block_jordan_strong (merge→itself) whose
                        # proof uses extended_jordan_family_strong in another
                        # file). seen_mods bounds the recursion.
                        if raw_y != x:
                            frontier.append(f"L_{raw_y}")
                    elif y in slug_set:
                        out[x].add(y)
                elif imp.startswith("_strategy_"):
                    sib = strat_alias.get(imp[len("_strategy_"):])
                    if sib is not None and sib != x and sib in slug_set:
                        # The raw strategy term IS a kept sibling lemma's proof
                        # → depend on that LEMMA; it owns its own transitive deps
                        # (don't walk into the raw term).
                        out[x].add(sib)
                    else:
                        frontier.append(imp)   # x's own strategy / unknown → walk
            # Defs-symbol edges: this module imports the problem's Defs and
            # names a placed Defs decl → x depends on it, exactly like a
            # cross-file sibling (orders the file, joins the import closure).
            if defs_names and _DEFS_IMPORT_RE.search(text):
                for nm in defs_names:
                    if nm != x and re.search(rf"\b{re.escape(nm)}\b", text):
                        out[x].add(nm)
    return out


def referenced_slugs(
    workspace: Path, problem: str, slugs,
    root_source: "tuple[str, str] | None" = None,
) -> "dict[str, set[str]]":
    """Per slug, the RAW set of sibling slugs its proof imports — same
    alias→strategy→`L_<sub>` walk as `usage_graph` but UNfiltered and
    UNremapped (keeps non-keep / dropped / merged siblings). Used to surface
    the non-keep siblings a decl cites — with their dedup verdict→citation —
    to the migrate agent, so it knows what to redirect a `sorry`-hole's
    reference to (G3). `root_source` (slug, abs_path) reads the root decl's
    references from Root.lean, not the absent proofs/L_<root>.lean."""
    proofs = db.problem_dir(workspace, problem) / "proofs"
    root_mod = f"L_{root_source[0]}" if root_source else None
    root_path = Path(root_source[1]) if root_source else None

    defs_names = set(defs_decls(workspace, problem))

    def read_mod(mod: str) -> "str | None":
        if root_mod and mod == root_mod:
            p = root_path
        else:
            p = resolve_ci(proofs, f"{mod}.lean")   # L_/l_ case-insensitive
        return p.read_text(encoding="utf-8") if (p and p.exists()) else None

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
            text = read_mod(mod)
            if text is None:
                continue
            for imp in _PROOFS_IMPORT_RE.findall(text):
                if imp[:2].lower() == "l_":   # L_<sub> / l_<sub> (case-insensitive)
                    if imp[2:] != x:
                        refs.add(imp[2:])
                elif imp.startswith("_strategy_"):
                    frontier.append(imp)
            # Defs-symbol references: same bare-name detection as usage_graph,
            # so a Defs decl a proof depends on is surfaced like any sibling.
            if defs_names and _DEFS_IMPORT_RE.search(text):
                for nm in defs_names:
                    if nm != x and re.search(rf"\b{re.escape(nm)}\b", text):
                        refs.add(nm)
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
