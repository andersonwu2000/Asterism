"""dedupe library: signature parser + ancestor scoping + alias body.

The Lean-kernel batch (`_batch_provable_via_apply`) is monkeypatched in tests so
suites stay fast and lake-independent. An optional integration test
(skipped if `lake` is missing) exercises the real subprocess on simple
inputs.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.quality import dedupe


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) VALUES (?, ?, ?, 1)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_root(conn: sqlite3.Connection, *, problem: str = "p",
               slug: str = "main", statement: str = "T",
               status: str = "open",
               lean_path: str | None = None) -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=lean_path or f"Problems/{problem}/Root.lean",
        statement=statement, origin="root",
    )
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


def _seed_sub(conn: sqlite3.Connection, *, problem: str = "p",
              slug: str, statement: str, depth: int = 1,
              status: str = "open") -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement=statement, origin="backward", depth=depth,
    )
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


def _link(conn: sqlite3.Connection, parent_id: int, sub_ids: list[int],
          *, problem: str = "p", status: str = "proposed") -> int:
    sid = db.insert_strategy(
        conn, goal_id=parent_id,
        lean_path=f"Problems/{problem}/Root.lean",
        scratch_path=f"Problems/{problem}/proofs/_strategy_s{parent_id}.lean",
        created_by="pid",
    )
    if status != "proposed":
        db.update_strategy_status(conn, sid, status)
    for pos, gid in enumerate(sub_ids):
        db.link_subgoal(conn, strategy_id=sid, subgoal_id=gid, position=pos)
    return sid


def _write_lean(workspace: Path, problem: str, slug: str,
                content: str, *, root: bool = False) -> Path:
    pdir = workspace / "Problems" / problem
    if root:
        path = pdir / "Root.lean"
    else:
        path = pdir / "proofs" / f"L_{slug}.lean"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# _signature_binder_count
# ---------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("theorem foo : T := by sorry", 0),
    ("theorem foo (x : Nat) : T := by sorry", 1),
    ("theorem foo (M) (hM) (hMax) : Sat M := by sorry", 3),
    ("theorem foo {α : Type} (x : α) : x = x := by rfl", 2),
    ("theorem foo {α} [Inhabited α] (x : α) : True := by trivial", 3),
    ("theorem foo (h : x ≥ 0) (hy : y > 0) : x + y > 0 := by sorry", 2),
])
def test_signature_binder_count(text: str, expected: int) -> None:
    assert dedupe._signature_binder_count(text) == expected


def test_signature_binder_count_no_theorem() -> None:
    assert dedupe._signature_binder_count("def foo := 1") == 0


# ---------------------------------------------------------------------
# _extract_full_signature
# ---------------------------------------------------------------------

def test_extract_full_signature_simple() -> None:
    text = "theorem foo : True := by trivial"
    assert dedupe._extract_full_signature(text) == ": True"


def test_extract_full_signature_with_binders() -> None:
    text = "theorem foo (x : Nat) (h : x ≥ 0) : x = x := by rfl"
    assert dedupe._extract_full_signature(text) == "(x : Nat) (h : x ≥ 0) : x = x"


def test_extract_full_signature_no_theorem() -> None:
    assert dedupe._extract_full_signature("def foo := 1") is None


# ---------------------------------------------------------------------
# _to_forall_form
# ---------------------------------------------------------------------

def test_to_forall_form_simple() -> None:
    assert dedupe._to_forall_form(": True") == "True"


def test_to_forall_form_with_binders() -> None:
    sig = "(x : Nat) (h : x ≥ 0) : x = x"
    assert dedupe._to_forall_form(sig) == "∀ (x : Nat) (h : x ≥ 0), x = x"


def test_to_forall_form_implicit_binder() -> None:
    sig = "{α : Type} (x : α) : x = x"
    assert dedupe._to_forall_form(sig) == "∀ {α : Type} (x : α), x = x"


def test_to_forall_form_skips_colons_inside_groups() -> None:
    """Colons inside (x : T) shouldn't be confused with the type colon."""
    sig = "(x : Nat) (y : Nat) : x = y"
    assert dedupe._to_forall_form(sig) == "∀ (x : Nat) (y : Nat), x = y"


# ---------------------------------------------------------------------
# _eligible_ancestors (DB-driven, no subprocess)
# ---------------------------------------------------------------------

def test_eligible_ancestors_excludes_immediate_parent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """parent_goal_id itself is excluded from ancestors (anti-cycle).
    Need a depth-3 chain so parent has a strict ancestor we can verify
    is INCLUDED (and parent itself is EXCLUDED)."""
    _seed_problem(conn)
    root = _seed_root(conn)
    grand = _seed_sub(conn, slug="grand", statement="X")
    _link(conn, root, [grand])
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, grand, [parent])
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "grand",
        "import Mathlib\ntheorem grand : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")

    ancestors = dedupe._eligible_ancestors(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
    )
    ids = [r[0]["id"] for r in ancestors]
    assert parent not in ids
    assert grand in ids
    assert root in ids


def test_eligible_ancestors_filters_by_binder_count(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Ancestors with more binders than candidate are excluded."""
    _seed_problem(conn)
    root = _seed_root(conn)
    grand = _seed_sub(conn, slug="grand", statement="Sat M")
    _link(conn, root, [grand])
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, grand, [parent])
    _write_lean(tmp_path, "p", "grand",
        "import Mathlib\nnamespace P\n"
        "theorem grand (M : T) (h1 : T) (h2 : T) (h3 : T) (h4 : T) : Sat M := by sorry\n"
        "end P\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # Candidate has 3 binders → grand (5) excluded
    a3 = dedupe._eligible_ancestors(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=3,
    )
    assert grand not in [r[0]["id"] for r in a3]

    # Candidate has 6 binders → grand (5) eligible
    a6 = dedupe._eligible_ancestors(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=6,
    )
    assert grand in [r[0]["id"] for r in a6]


def test_eligible_ancestors_skips_orphan_chain(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Ancestor on a 'superseded' chain is unreachable; alive set excludes."""
    _seed_problem(conn)
    root = _seed_root(conn)
    grand = _seed_sub(conn, slug="grand", statement="X")
    s_dead = db.insert_strategy(
        conn, goal_id=root,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_dead.lean",
        created_by="pid")
    db.update_strategy_status(conn, s_dead, "superseded")
    db.link_subgoal(conn, strategy_id=s_dead, subgoal_id=grand, position=0)
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, grand, [parent])
    _write_lean(tmp_path, "p", "grand",
        "import Mathlib\ntheorem grand : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    ancestors = dedupe._eligible_ancestors(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
    )
    assert grand not in [r[0]["id"] for r in ancestors]


# ---------------------------------------------------------------------
# _eligible_problem_proved (cross-branch dedup pool, item 11)
# ---------------------------------------------------------------------

def test_eligible_problem_proved_finds_cross_branch_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A proved goal on a sibling sub-tree (not in candidate's strict
    ancestor chain, not an orphan-sibling) should appear in the
    cross-branch pool."""
    _seed_problem(conn)
    root = _seed_root(conn)
    branch_a = _seed_sub(conn, slug="branch_a", statement="A")
    branch_b = _seed_sub(conn, slug="branch_b", statement="B")
    _link(conn, root, [branch_a, branch_b])
    cousin_proved = _seed_sub(conn, slug="cousin", statement="X",
                              depth=2, status="proved")
    _link(conn, branch_a, [cousin_proved])
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, branch_b, [parent])
    _write_lean(tmp_path, "p", "cousin",
        "import Mathlib\ntheorem cousin : X := by trivial\n")
    _write_lean(tmp_path, "p", "branch_a",
        "import Mathlib\ntheorem branch_a : A := by sorry\n")
    _write_lean(tmp_path, "p", "branch_b",
        "import Mathlib\ntheorem branch_b : B := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    pool = dedupe._eligible_problem_proved(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
        exclude_ids=set(),
    )
    ids = [r[0]["id"] for r in pool]
    assert cousin_proved in ids, (
        "cross-branch proved cousin should be in pool when exclude_ids is empty "
        "(B1 regression: NOT IN (NULL) silently filtered everything)"
    )


def test_eligible_problem_proved_excludes_parent_and_aliases(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Parent itself (anti-cycle) and existing aliases are excluded."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    parent = _seed_sub(conn, slug="parent", statement="P",
                       depth=1, status="proved")
    _link(conn, root, [parent])
    aliased = _seed_sub(conn, slug="aliased", statement="A",
                        depth=1, status="proved")
    db.set_alias_target(conn, aliased, root)
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by trivial\n", root=True)
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : P := by trivial\n")
    _write_lean(tmp_path, "p", "aliased",
        "import Mathlib\ntheorem aliased : A := by trivial\n")

    pool = dedupe._eligible_problem_proved(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
        exclude_ids=set(),
    )
    ids = [r[0]["id"] for r in pool]
    assert parent not in ids
    assert aliased not in ids
    assert root in ids


def test_eligible_problem_proved_skips_excluded_ids(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Caller passes exclude_ids to dedup with ancestor / orphan pools."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    parent = _seed_sub(conn, slug="parent", statement="P", depth=1)
    _link(conn, root, [parent])
    other = _seed_sub(conn, slug="other", statement="O",
                      depth=1, status="proved")
    _link(conn, root, [other])
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by trivial\n", root=True)
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : P := by sorry\n")
    _write_lean(tmp_path, "p", "other",
        "import Mathlib\ntheorem other : O := by trivial\n")

    pool = dedupe._eligible_problem_proved(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
        exclude_ids={root},
    )
    ids = [r[0]["id"] for r in pool]
    assert root not in ids  # excluded by caller
    assert other in ids


# ---------------------------------------------------------------------
# find_canonicals_batch (with monkeypatched _batch_provable_via_apply)
# ---------------------------------------------------------------------

def test_find_canonicals_batch_picks_proved_over_open(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If two ancestors match isDefEq, prefer 'proved' over 'open'."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT")
    proved_anc = _seed_sub(conn, slug="proved_anc",
                            statement="X", status="proved")
    open_anc = _seed_sub(conn, slug="open_anc", statement="X")
    _link(conn, root, [proved_anc, open_anc])
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, proved_anc, [parent])
    for slug in ("proved_anc", "open_anc", "parent"):
        _write_lean(tmp_path, "p", slug,
            f"import Mathlib\ntheorem {slug} (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # Only proved_anc is a strict ancestor of parent (proved_anc is parent's
    # parent). open_anc is a sibling. Pre-filter via SQL handles that.
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))

    candidate_text = ("import Mathlib\nnamespace P\n"
                      "theorem cand (a : T) (b : T) : X := by sorry\n"
                      "end P\n")
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("cand", candidate_text)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=proved_anc, kind="alias"),
    ]


def test_find_canonicals_batch_no_match_returns_none(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """isDefEq returns all False → all canonicals None."""
    _seed_problem(conn)
    root = _seed_root(conn)
    grand = _seed_sub(conn, slug="grand", statement="X")
    _link(conn, root, [grand])
    parent = _seed_sub(conn, slug="parent", statement="OTHER", depth=2)
    _link(conn, grand, [parent])
    _write_lean(tmp_path, "p", "grand",
        "import Mathlib\ntheorem grand (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [False] * len(pairs))

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [None]


def test_find_canonicals_batch_empty_candidates(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    assert dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=1, candidates=[],
    ) == []


def test_extract_theorem_name_matches_def_form() -> None:
    """#112(c) — framework's promote_to_alias rewrites proved sub-goal
    files into `def <slug> := @s<sid>` shape. The earlier regex only
    matched `theorem`, so canonical_thm came back empty and
    _batch_provable_via_apply emitted a deliberately-failing stub for
    every alive-ancestor pair. Observed on imo_1990_p3 g1480 vs
    byte-identical alive ancestor g1453, where the alias never landed."""
    assert dedupe._extract_theorem_name(
        "def two_sq_eq_one_given_no_seven := @Problems.X.s9833"
    ) == "two_sq_eq_one_given_no_seven"
    assert dedupe._extract_theorem_name(
        "lemma foo (a : T) : X := by sorry"
    ) == "foo"
    assert dedupe._extract_theorem_name(
        "theorem bar : True := trivial"
    ) == "bar"


def test_find_canonicals_batch_disproved_match_returns_disproved_kind(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#112(a) — when no alive canonical matches but a disproved goal
    in the same problem does, dedupe emits
    CanonicalMatch(kind='disproved') so the caller can decline the
    candidate rather than alias to a known-false statement.

    Phase 2 — Tier 4 dedupe semantic shifted from 'shelved' to
    'disproved' (agent counterexample only). Soft-terminal 'shelved'
    goals no longer match this tier."""
    _seed_problem(conn)
    root = _seed_root(conn)
    disproved_g = _seed_sub(conn, slug="dead_approach",
                            statement="X", status="disproved")
    _link(conn, root, [disproved_g])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "dead_approach",
        "import Mathlib\ntheorem dead_approach (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # Only the disproved canonical's name unifies with the candidate.
    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "dead_approach" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=disproved_g, kind="disproved"),
    ]


def test_find_canonicals_batch_shelved_does_not_block(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 2 — soft-terminal 'shelved' goals (cascade descendants /
    parent_needs_fix) do NOT block future proposals. Only 'disproved'
    (counterexample) blocks via dedupe.

    Setup: candidate would unify with the 'soft_dead' shelved goal's
    statement (fake returns True only for its theorem name). Pre-Phase 2
    this would emit kind='shelved'; post-Phase 2 the shelved goal is
    excluded from the dedupe pool → result is None."""
    _seed_problem(conn)
    root = _seed_root(conn)
    shelved_g = _seed_sub(conn, slug="soft_dead",
                          statement="X", status="shelved")
    _link(conn, root, [shelved_g])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "soft_dead",
        "import Mathlib\ntheorem soft_dead (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # Only the shelved canonical's name would unify with the candidate.
    # Since shelved is excluded from the dedupe pool, pairs list won't
    # include it, fake never sees it, and no other canonical matches.
    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "soft_dead" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [None]


def test_find_canonicals_batch_alive_shadows_disproved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#112(a) — alive/proved canonical takes priority over disproved
    match. Caller should always prefer aliasing to a usable proof over
    declining on a known-false precedent."""
    _seed_problem(conn)
    root = _seed_root(conn)
    proved_anc = _seed_sub(conn, slug="proved_anc",
                            statement="X", status="proved")
    disproved_g = _seed_sub(conn, slug="dead_approach",
                            statement="X", status="disproved")
    _link(conn, root, [proved_anc, disproved_g])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, proved_anc, [parent])
    for slug in ("proved_anc", "dead_approach", "parent"):
        _write_lean(tmp_path, "p", slug,
            f"import Mathlib\ntheorem {slug} (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=proved_anc, kind="alias"),
    ]


def test_find_canonicals_batch_def_form_ancestor_resolves(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#112(c) — when an alive ancestor's lean file is in the framework-
    promoted `def <slug> := @s<sid>` shape, name extraction still
    succeeds and the candidate-canonical pair flows into the lake
    batch. Pre-fix the regex missed `def`, yielding canonical_thm=''
    and a force-fail stub — alias never landed."""
    _seed_problem(conn)
    root = _seed_root(conn)
    proved_anc = _seed_sub(conn, slug="promoted_anc",
                            statement="X", status="proved")
    _link(conn, root, [proved_anc])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, proved_anc, [parent])
    # Promoted form: `def` instead of `theorem`.
    _write_lean(tmp_path, "p", "promoted_anc",
        "import Mathlib\nnamespace Problems.p\n"
        "def promoted_anc := @Problems.p.s9999\n"
        "end Problems.p\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    captured: dict = {}

    def fake(ws: Path, prob: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        captured["pairs"] = pairs
        return [True] * len(pairs)

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    # canonical_thm must NOT be empty — the regex picks up the def.
    assert captured["pairs"], "no pair produced — regex still misses def"
    _cand_sig, _mod, canonical_thm = captured["pairs"][0]
    assert canonical_thm == "promoted_anc"
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=proved_anc, kind="alias"),
    ]


def test_find_canonicals_batch_mixed_hits(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One candidate matches its ancestor, another doesn't. Verify
    per-candidate alignment of canonical_for return list."""
    _seed_problem(conn)
    root = _seed_root(conn)
    g_anc1 = _seed_sub(conn, slug="ga1", statement="X")
    _link(conn, root, [g_anc1])
    p1 = _seed_sub(conn, slug="p1", statement="OT1", depth=2)
    _link(conn, g_anc1, [p1])
    _write_lean(tmp_path, "p", "ga1",
        "import Mathlib\ntheorem ga1 (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "p1",
        "import Mathlib\ntheorem p1 : OT1 := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # Fake provability check: cand provable from canonical iff
    # conclusion matches AND canonical thm is the one with that
    # conclusion (ga1 has conclusion X; main has conclusion T).
    def fake(ws: Path, prob: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [(": X" in cand_sig and thm == "ga1")
                for cand_sig, _mod, thm in pairs]

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    # cand1 has the same signature as ga1 → match
    # cand2 has a different conclusion → no match
    cand1 = "import Mathlib\ntheorem c1 (a : T) : X := by sorry\n"
    cand2 = "import Mathlib\ntheorem c2 (a : T) : Z := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=p1,
        candidates=[("c1", cand1), ("c2", cand2)],
    )
    assert canonicals[0] == dedupe.CanonicalMatch(
        goal_id=g_anc1, kind="alias")
    assert canonicals[1] is None


# ---------------------------------------------------------------------
# build_alias_content
# ---------------------------------------------------------------------

def test_build_alias_replaces_sorry_with_apply_assumption() -> None:
    original = (
        "import Mathlib\n"
        "import Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "theorem cand (M : T) (h : T) : Sat M := by sorry\n\n"
        "end Problems.p\n"
    )
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_canonical",
        canonical_slug="canonical",
    )
    assert "import Problems.p.proofs.L_canonical" in out
    assert ":= by apply canonical <;> assumption" in out
    assert ":= by sorry" not in out
    assert "theorem cand (M : T) (h : T) : Sat M" in out
    assert "import Mathlib" in out
    assert "import Problems.p.Defs" in out


def test_build_alias_does_not_duplicate_existing_import() -> None:
    original = (
        "import Mathlib\n"
        "import Problems.p.proofs.L_canonical\n\n"
        "theorem cand : T := by sorry\n"
    )
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_canonical",
        canonical_slug="canonical",
    )
    assert out.count("import Problems.p.proofs.L_canonical") == 1


def test_build_alias_handles_no_imports() -> None:
    original = "theorem cand : T := by sorry\n"
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_c",
        canonical_slug="c",
    )
    assert out.startswith("import Problems.p.proofs.L_c")
    assert ":= by apply c <;> assumption" in out


# ---------------------------------------------------------------------
# _batch_provable_via_apply integration (skipped when lake unavailable)
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# _batch_provable_via_apply global-error handling (F14)
# ---------------------------------------------------------------------

def _patch_subprocess(monkeypatch: pytest.MonkeyPatch, *,
                      stdout: str, stderr: str, rc: int) -> None:
    """Stub subprocess.run inside dedupe with a fixed result."""
    class FakeResult:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = rc

    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return FakeResult()

    monkeypatch.setattr(openai_api_dedupe := __import__(
        "Tooling.quality.dedupe", fromlist=["subprocess"]).subprocess,
                        "run", fake_run)


def test_lake_err_re_matches_windows_absolute_path() -> None:
    """#112(c) follow-up — `_LAKE_ERR_RE` must match Windows-style
    absolute paths emitted by lake under `cwd=workspace, file=str(tmp_file)`
    where workspace is an absolute Path. The earlier `[^:]+` prefix
    aborted at the drive-letter colon (`D:`), so error_lines came back
    empty and the per-pair attribution was skipped in favor of the
    'no error_lines despite rc!=0' all-False branch. Cost: every dedupe
    call on Windows silently returned no matches."""
    sample = (
        r"D:\Asterism\.attempts\_x.lean:91:2: error: Tactic apply failed"
        "\n"
        r"D:\Asterism\.attempts\_x.lean:103:5: error: another"
        "\n"
    )
    matches = dedupe._LAKE_ERR_RE.findall(sample)
    assert matches == ["91", "103"]


def test_lake_err_re_matches_posix_path() -> None:
    """Regression for the original posix-style path that worked under
    the old regex — ensure the relaxed `.+?` prefix didn't break it."""
    sample = (
        "/home/u/.attempts/_x.lean:42:1: error: foo\n"
        "/home/u/.attempts/_x.lean:88:2: error: bar\n"
    )
    assert dedupe._LAKE_ERR_RE.findall(sample) == ["42", "88"]


def test_batch_provable_via_apply_multiline_cand_sig_keeps_pair_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#112(c) follow-up — `_extract_full_signature` returns the
    candidate's signature text verbatim, which often spans multiple
    lines for long ∀-prefixed statements. The original code appended
    that multi-line string into `lines` as a single element, causing
    the file's actual line count to diverge from `len(lines)` and
    `pair_start_lines` to drift past lake's true error line numbers.
    Errors then landed in the wrong pair (or outside any pair) and
    every dedupe candidate came back False even when the lake batch
    found a valid alias. Fix: flatten cand_sig whitespace before
    embedding so each `lines.append` stays one file line.

    This test stages a 3-pair batch where pair 1's cand_sig has
    newlines; only pair 0 errors. Without the flatten fix, the error
    on pair 0 would mis-attribute (pair_start_lines for pairs 1/2
    drifted past where lake reports). With the fix, pair 0 stays
    correctly attributed and pairs 1/2 stay True."""
    # Build a synthetic lake response keyed to the post-flatten file
    # layout. Each pair occupies exactly 4 lines: comment, theorem,
    # apply, blank.
    err_at_pair_0 = (
        f"{tmp_path}/_x.lean:11:2: error: Tactic apply failed\n"
    )
    _patch_subprocess(monkeypatch, stdout=err_at_pair_0, stderr="", rc=1)
    multi_line_sig = ": ∀ (m : ℕ),\n  2 ≤ m →\n  m ^ 2 ∣ 2 ^ m + 1"
    pairs = [
        (": Nat", "Mod.A", "thm_a"),         # pair 0 (start ~ line 9)
        (multi_line_sig, "Mod.B", "thm_b"),  # pair 1 (start ~ line 13)
        (": Bool", "Mod.C", "thm_c"),        # pair 2 (start ~ line 17)
    ]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    # Pair 0 fails (error in its range), pairs 1 and 2 pass.
    assert result == [False, True, True], (
        f"expected [False, True, True], got {result}; flatten "
        f"likely regressed and pair_start_lines drifted"
    )


def test_batch_provable_via_apply_rc0_means_all_pairs_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F14: rc==0 from Lean is the canonical 'no errors anywhere' signal.
    Skip line-error parsing entirely in the happy path."""
    _patch_subprocess(monkeypatch, stdout="", stderr="", rc=0)
    # New 3-tuple shape: (cand_signature, canonical_module, canonical_thm).
    pairs = [(": Nat", "Mod.A", "thm_a"),
             (": Bool", "Mod.B", "thm_b")]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert result == [True, True]


def test_batch_provable_via_apply_global_error_outside_pair_range_rejects_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F14 root cause: when an error fires before the first pair (e.g.
    bad import on file line 1), Lean stops elaborating and the pair
    lines never produce errors. Old code defaulted to all-True.
    New code: rc != 0 + error outside any pair → all False."""
    # Pair lines start around 5; error at line 1 is global.
    stdout = "/tmp/x.lean:1:0: error: object file does not exist"
    _patch_subprocess(monkeypatch, stdout=stdout, stderr="", rc=1)
    pairs = [(": A", "Mod.A", "thm_a"), (": C", "Mod.C", "thm_c")]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert result == [False, False]


def test_batch_provable_via_apply_per_pair_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When all errors are inside pair ranges, attribute per-pair.
    File layout (with NEW _batch_provable_via_apply template):
      1: import Mathlib
      2: import Mod.A
      3: import Mod.B
      4: (blank)
      5: namespace dedupe_check
      6: (blank)
      7: -- pair 0
      8: theorem _dc_0 : A := by
      9:   apply @Mod.A.thm_a <;> assumption
     10: (blank)
     11: -- pair 1
     12: theorem _dc_1 : B := by
     13:   apply @Mod.B.thm_b <;> assumption
    pair_start_lines: [7, 11]. Error at line 12 → falls in pair 1's
    range (lines 11–end), so pair 1 fails, pair 0 passes.
    """
    stdout = "/tmp/x.lean:12:0: error: type mismatch"
    _patch_subprocess(monkeypatch, stdout=stdout, stderr="", rc=1)
    pairs = [(": A", "Mod.A", "thm_a"), (": B", "Mod.B", "thm_b")]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert result == [True, False]


def test_batch_provable_via_apply_unknown_failure_pattern_rejects_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc != 0 but no line-prefixed errors matched. Could be a parser
    panic / Lean crash. Conservative: reject all pairs."""
    _patch_subprocess(monkeypatch, stdout="", stderr="lean: panic", rc=1)
    pairs = [(": A", "Mod.A", "thm_a")]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert result == [False]


# ---------------------------------------------------------------------
# F42 — cross-strategy orphan reuse
# ---------------------------------------------------------------------

def test_orphan_pool_includes_proved_subs_of_dead_strategies(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A proved sub-goal whose owning strategy has died is still
    considered as a canonical for new candidates on the same parent.
    Pre-F42 this orphan was invisible (alive walk excluded it)."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT")
    parent = _seed_sub(conn, slug="parent", statement="PARENT")
    _link(conn, root, [parent])
    # First strategy on `parent` produced 2 sub-goals; one proved, then
    # the strategy died (e.g. another sub shelved → cascade).
    orphan_proved = _seed_sub(
        conn, slug="orph_a", statement="X", depth=2, status="proved")
    orphan_other = _seed_sub(
        conn, slug="orph_b", statement="Y", depth=2)
    s_dead = _link(conn, parent, [orphan_proved, orphan_other],
                   status="dead")
    _write_lean(tmp_path, "p", "orph_a",
        "import Mathlib\ntheorem orph_a : X := by trivial\n")
    _write_lean(tmp_path, "p", "orph_b",
        "import Mathlib\ntheorem orph_b : Y := by sorry\n")

    pool = dedupe._eligible_orphan_subgoals(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
    )
    ids = [r[0]["id"] for r in pool]
    assert orphan_proved in ids
    # Orphan sub that was never proved isn't a useful canonical
    assert orphan_other not in ids


def test_orphan_pool_excludes_already_alias_goals(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """An orphan that's itself an alias (alias_target_id IS NOT NULL)
    is excluded — we don't want to chain alias→alias→concrete (lifetime
    reasoning gets murky and the file already imports the real
    canonical, so adding another hop wastes a build edge)."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT")
    parent = _seed_sub(conn, slug="parent", statement="PARENT")
    _link(conn, root, [parent])
    real = _seed_sub(conn, slug="real", statement="X", depth=2,
                     status="proved")
    alias = _seed_sub(conn, slug="alias_g", statement="X", depth=2,
                      status="proved")
    db.set_alias_target(conn, alias, real)
    _link(conn, parent, [real, alias], status="dead")
    _write_lean(tmp_path, "p", "real",
        "import Mathlib\ntheorem real : X := by trivial\n")
    _write_lean(tmp_path, "p", "alias_g",
        "import Mathlib\ntheorem alias_g : X := by apply real\n")

    ids = [r[0]["id"] for r in dedupe._eligible_orphan_subgoals(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=10,
    )]
    assert real in ids
    assert alias not in ids


def test_orphan_pool_filters_by_binder_count(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Same binder rule applies to orphans as to ancestors."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT")
    parent = _seed_sub(conn, slug="parent", statement="PARENT")
    _link(conn, root, [parent])
    o = _seed_sub(conn, slug="orph", statement="X", depth=2,
                  status="proved")
    _link(conn, parent, [o], status="dead")
    _write_lean(tmp_path, "p", "orph",
        "import Mathlib\nnamespace P\n"
        "theorem orph (a : T) (b : T) (c : T) (d : T) (e : T) : X := by sorry\n"
        "end P\n")
    # Candidate has 3 binders → orphan (5) excluded
    p3 = dedupe._eligible_orphan_subgoals(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=3,
    )
    assert o not in [r[0]["id"] for r in p3]
    # Candidate has 6 binders → orphan eligible
    p6 = dedupe._eligible_orphan_subgoals(
        conn, tmp_path, problem="p",
        parent_goal_id=parent, candidate_count=6,
    )
    assert o in [r[0]["id"] for r in p6]


def test_orphan_pool_excludes_unrelated_parents(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Only orphans whose owning strategy targeted THIS parent are in
    the pool. Don't pull in proved goals from unrelated branches."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT")
    parent_a = _seed_sub(conn, slug="parent_a", statement="A")
    parent_b = _seed_sub(conn, slug="parent_b", statement="B")
    _link(conn, root, [parent_a, parent_b])
    # Orphan from parent_b's dead strategy
    orphan_b = _seed_sub(conn, slug="orph_b", statement="X", depth=2,
                         status="proved")
    _link(conn, parent_b, [orphan_b], status="dead")
    _write_lean(tmp_path, "p", "orph_b",
        "import Mathlib\ntheorem orph_b : X := by trivial\n")

    pool = dedupe._eligible_orphan_subgoals(
        conn, tmp_path, problem="p",
        parent_goal_id=parent_a, candidate_count=10,
    )
    assert orphan_b not in [r[0]["id"] for r in pool]


def test_db_set_alias_target_and_lookup(conn: sqlite3.Connection) -> None:
    """Round-trip on the new column + the helper that prune uses."""
    _seed_problem(conn)
    root = _seed_root(conn)
    canon = _seed_sub(conn, slug="canon", statement="X", status="proved")
    alias = _seed_sub(conn, slug="alias_g", statement="X", status="proved")
    db.set_alias_target(conn, alias, canon)
    g = db.get_goal(conn, alias)
    assert g["alias_target_id"] == canon
    assert db.aliases_pointing_at(conn, canon) == [alias]
    assert db.aliases_pointing_at(conn, root) == []


# ---------------------------------------------------------------------
# Original real-lake integration test
# ---------------------------------------------------------------------

def test_batch_provable_via_apply_template_handles_hypothesis_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for SG run #15: cand has MORE hypotheses than
    canonical, same conclusion. The old rfl-based check rejected this
    (hypothesis-extension types differ); the new provability check
    accepts because `apply canonical <;> assumption` proves the
    extras-vacuously case.

    We capture what _batch_provable_via_apply WRITES (the template) so
    a later refactor can't accidentally regress to a rfl-only check.
    """
    captured = {}

    def capture_run(*args, **kwargs):
        # First positional arg is the cmd list; we want the input file
        # path (last element) to read what got written.
        cmd = args[0]
        lean_file = Path(cmd[-1])
        captured["content"] = lean_file.read_text(encoding="utf-8")

        class _R:
            stdout = ""
            stderr = ""
            returncode = 0
        return _R()

    import Tooling.quality.dedupe as _d
    monkeypatch.setattr(_d.subprocess, "run", capture_run)

    # cand has extra hypothesis (hcard) vs canonical
    pairs = [
        ("(Q : Finset Nat) (h : Q.Nonempty) (hcard : 3 ≤ Q.card) : Q.Nonempty",
         "Problems.p.proofs.L_canon",
         "canon_thm"),
    ]
    dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    body = captured["content"]
    # Template shape: theorem _dc_0 with apply + assumption.
    # Canonical FQN is `Problems.<problem>.<thm_name>` because the
    # canonical's lean file declares `namespace Problems.<problem>`,
    # not nested under proofs. The MODULE path
    # `Problems.<problem>.proofs.L_<slug>` is for the import.
    assert "theorem _dc_0" in body
    assert "apply @Problems.p.canon_thm" in body
    assert "<;> assumption" in body
    # Must NOT use rfl (regression guard)
    assert ":= rfl" not in body
    # Imports the canonical's module
    assert "import Problems.p.proofs.L_canon" in body


@pytest.mark.skipif(shutil.which("lake") is None,
                    reason="requires lake CLI on PATH")
def test_batch_provable_via_apply_real_lake(tmp_path: Path) -> None:
    """Spin up the actual Lean kernel on a tiny pair to confirm the
    subprocess plumbing + parsing work. Slow (lake env startup ~3-5s);
    skipped unless lake is on PATH."""
    # Need a minimal lakefile in tmp_path so `lake env` works
    (tmp_path / "lakefile.lean").write_text(
        "import Lake\nopen Lake DSL\npackage tmp where\n"
        "@[default_target]\nlean_lib tmp where\n",
        encoding="utf-8")
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n",
                                              encoding="utf-8")
    # This may still fail because Mathlib isn't present in tmp_path's
    # lake project. We accept that and just verify the call-flow doesn't
    # crash; equality decision is opaque without Mathlib.
    pairs = [("(x : Nat) : x = x", "Mod.X", "thm_x")]
    result = dedupe._batch_provable_via_apply(tmp_path, "tmp", pairs)
    assert isinstance(result, list)
    assert len(result) == 1
