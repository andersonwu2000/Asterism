"""dedupe library: signature parser + ancestor scoping + alias body.

The Lean-kernel batch (`_batch_provable_via_apply`) is monkeypatched in tests so
suites stay fast and lake-independent. An optional integration test
(skipped if `lake` is missing) exercises the real subprocess on simple
inputs.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.quality import dedupe

# Captured at import time — BEFORE conftest's autouse cold-lake stubs
# replace them per-test. This file tests the real implementations (with
# subprocess mocked locally), so restore them; the side-effect fence
# still backstops any un-mocked toolchain spawn.
_REAL_BATCH_PROVABLE = dedupe._batch_provable_via_apply


@pytest.fixture(autouse=True)
def _use_real_batch_provable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        _REAL_BATCH_PROVABLE)


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
# _strict_ancestor_slugs (backward circular-decomposition guard, #4)
# ---------------------------------------------------------------------

def test_strict_ancestor_slugs_walks_full_chain(conn: sqlite3.Connection) -> None:
    from Tooling.pipeline.backward import _strict_ancestor_slugs
    _seed_problem(conn, "p")
    root = _seed_root(conn, problem="p", slug="main")
    grand = _seed_sub(conn, problem="p", slug="grand", statement="Tg")
    parent = _seed_sub(conn, problem="p", slug="parent", statement="Tp")
    child = _seed_sub(conn, problem="p", slug="child", statement="Tc")
    _link(conn, root, [grand])
    _link(conn, grand, [parent])
    _link(conn, parent, [child])
    anc = _strict_ancestor_slugs(conn, child)
    # every strict ancestor, excluding `child` itself
    assert set(anc) == {"main", "grand", "parent"}
    assert anc["parent"].endswith("L_parent.lean")
    # the root has no parent strategy → no strict ancestors
    assert _strict_ancestor_slugs(conn, root) == {}


def test_theorem_head_extracts_and_matches() -> None:
    from Tooling.pipeline.backward import _theorem_head
    a = "theorem foo (n : Nat) : ∫ x, f x = 0 := by sorry"
    # whitespace-insensitive, same head extracted regardless of formatting
    b = "theorem foo (n : Nat) :\n    ∫ x, f x = 0 :=\n  sorry"
    assert _theorem_head(a, "foo") == _theorem_head(b, "foo")
    # a genuinely different conclusion → different head (falls through to _2)
    c = "theorem foo (n : Nat) : ∫ x, g x = 1 := by sorry"
    assert _theorem_head(a, "foo") != _theorem_head(c, "foo")
    # no matching declaration → None
    assert _theorem_head(a, "bar") is None


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
# BUG1 regression (2026-07-03 mv_delta): the signature extractor must be
# def-blind AND comment-unaware, so a `def` candidate never seeds a probe
# via a stray theorem/lemma token in a comment.
# ---------------------------------------------------------------------

def test_extract_signature_ignores_comment_lemma_token_for_def() -> None:
    """A `def` candidate whose ONLY `lemma`/`theorem` token is in a comment
    (the Forward seed's `-- Write ONE forward lemma here`) must yield no
    signature — else its garbage 'signature' seeds a false-positive alias
    (the real mv_delta δ was false-aliased to an unrelated support lemma)."""
    def_cand = (
        "import Mathlib\n"
        "-- Write ONE forward lemma here\n"
        "noncomputable def mv_delta {R : Type} [Ring R] : SomeHom := realTerm\n"
    )
    assert dedupe._extract_full_signature(def_cand) is None
    assert dedupe._signature_binder_count(def_cand) == 0


def test_extract_signature_matches_real_head_past_comment_token() -> None:
    """A real theorem preceded by a comment mentioning `lemma` must still
    extract the REAL head's signature, not the comment."""
    thm = (
        "-- this lemma proves foo\n"
        "theorem realfoo (x : Nat) : P x := by sorry\n"
    )
    assert dedupe._extract_full_signature(thm) == "(x : Nat) : P x"
    assert dedupe._signature_binder_count(thm) == 1


def test_extract_signature_matches_modifier_prefixed_head() -> None:
    assert dedupe._extract_full_signature(
        "private theorem bar (a : A) : Q := by sorry") == "(a : A) : Q"


def test_build_alias_content_rewrites_sorry_stub() -> None:
    """build_alias_content delegates a `:= by sorry` stub to the canonical."""
    out = dedupe.build_alias_content(
        original_content="import Mathlib\ntheorem foo : P := by sorry\n",
        canonical_module="Problems.p.proofs.L_canon", canonical_slug="canon")
    assert "apply canon" in out and "by sorry" not in out
    assert "import Problems.p.proofs.L_canon" in out


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


def test_leading_decl_attrs_preserves_instance() -> None:
    """`leading_decl_attrs` captures `@[instance]` (same-line + own-line, and
    over an already-aliased `def`) so a Prop-class root's instance attribute
    survives alias-finalization; returns '' for a plain theorem (no regression
    for the non-instance majority)."""
    f = dedupe.leading_decl_attrs
    assert f("@[instance] theorem main : T := by sorry", "main") == "@[instance]\n"
    assert f("@[instance]\ntheorem main : T := by sorry", "main") == "@[instance]\n"
    assert f("@[instance] def main := @X.s1", "main") == "@[instance]\n"
    assert (f("@[simp, instance] theorem main : T := by sorry", "main")
            == "@[simp, instance]\n")
    assert f("theorem main : T := by sorry", "main") == ""


# ---------------------------------------------------------------------
# _eligible_ancestors (DB-driven, no subprocess)
# ---------------------------------------------------------------------

def test_eligible_ancestors_excludes_immediate_parent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """parent_goal_id itself is excluded from ancestors (anti-cycle).
    Need a depth-3 chain so parent has a strict ancestor we can verify
    is INCLUDED (and parent itself is EXCLUDED). Ancestors must be PROVED
    to be alias candidates (unproved ancestors are the no_progress tier)."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    grand = _seed_sub(conn, slug="grand", statement="X", status="proved")
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
    """Ancestors with more binders than candidate are excluded.
    Ancestor must be PROVED to be an alias candidate."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    grand = _seed_sub(conn, slug="grand", statement="Sat M", status="proved")
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
        return [thm == "Problems.p.dead_approach" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=disproved_g, kind="disproved"),
    ]


def test_binder_bracket_seq_and_forall_form() -> None:
    """P1 interface layer: top-level binder bracket sequence — names and
    types free, nesting skipped depth-aware, explicitness visible."""
    sig = "(g : ℕ → ℕ) {r : ℝ} [inst : Nonempty ℕ] (h : (A → B) ∧ C) : P g r"
    assert dedupe._binder_bracket_seq(sig) == "({[("
    assert dedupe._forall_form(sig) == (
        "∀ (g : ℕ → ℕ) {r : ℝ} [inst : Nonempty ℕ] (h : (A → B) ∧ C), P g r")
    # zero binders
    assert dedupe._binder_bracket_seq(": True") == ""
    assert dedupe._forall_form(": True") == "True"
    # binder-name drift is invisible (same sequence)
    assert dedupe._binder_bracket_seq("(a : T) : X") == \
        dedupe._binder_bracket_seq("(b : T) : X")
    # implicit/explicit flip IS visible (call interface differs)
    assert dedupe._binder_bracket_seq("(a : T) : X") != \
        dedupe._binder_bracket_seq("{a : T} : X")
    # malformed (no top-level colon) → None
    assert dedupe._binder_bracket_seq("(a : T)") is None


def test_find_canonicals_batch_defeq_links_paraphrased_shelved_twin(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1 (b6 twin-minting churn): a candidate whose binder NAMES differ
    from a shelved twin (strict shape gate misses) but whose statement
    is kernel-defeq gets kind='reuse' via the statement-defeq pass —
    linked, no fresh twin minted."""
    _seed_problem(conn)
    root = _seed_root(conn)
    twin = _seed_sub(conn, slug="crux_twin", statement="X",
                     status="shelved")
    _link(conn, root, [twin])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "crux_twin",
        "import Mathlib\ntheorem crux_twin (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    # apply probe finds nothing; defeq probe confirms the pair
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [False] * len(pairs))
    seen: dict = {}

    def fake_defeq(ws: Path, p: str,
                   pairs: list[tuple[str, str, str]]) -> list[bool]:
        seen["pairs"] = pairs
        return [True] * len(pairs)
    monkeypatch.setattr(dedupe, "_batch_statement_defeq", fake_defeq)

    # binder name differs (b : T vs a : T) → strict shape gate misses
    cand = "import Mathlib\ntheorem c (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=twin, kind="reuse"),
    ]
    # probe compared the ∀-forms
    assert seen["pairs"][0][0].startswith("∀ (b : T)")
    assert seen["pairs"][0][1].startswith("∀ (a : T)")


def test_defeq_pass_skips_interface_mismatch(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit-vs-implicit binder flip never reaches the defeq probe —
    defeq would pass (explicitness is elaboration metadata) but the
    reference rewrite would break at every call site."""
    _seed_problem(conn)
    root = _seed_root(conn)
    twin = _seed_sub(conn, slug="crux_twin", statement="X",
                     status="shelved")
    _link(conn, root, [twin])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "crux_twin",
        "import Mathlib\ntheorem crux_twin {a : T} : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [False] * len(pairs))
    called: dict = {"n": 0}

    def fake_defeq(ws, p, pairs):
        called["n"] += len(pairs)
        return [True] * len(pairs)
    monkeypatch.setattr(dedupe, "_batch_statement_defeq", fake_defeq)

    cand = "import Mathlib\ntheorem c (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [None]      # mints as novel — conservative
    assert called["n"] == 0          # probe never consulted


def test_existing_duplicate_strategy_guard(
    conn: sqlite3.Connection,
) -> None:
    """P3: a fully-linked decomposition whose link set equals an existing
    proposed/stalled strategy's subgoal set is a duplicate; different
    sets or dead twins do not block."""
    from Tooling.pipeline.backward import _existing_duplicate_strategy
    _seed_problem(conn)
    root = _seed_root(conn)
    crux = _seed_sub(conn, slug="crux", statement="X", status="shelved")
    other = _seed_sub(conn, slug="other", statement="Y")
    target = _seed_sub(conn, slug="target", statement="Q", depth=2)
    _link(conn, root, [target])
    sid = _link(conn, target, [crux], status="stalled")
    conn.commit()

    assert _existing_duplicate_strategy(conn, target, {crux}) == sid
    assert _existing_duplicate_strategy(conn, target, {crux, other}) is None
    assert _existing_duplicate_strategy(conn, target, set()) is None
    # dead twin strategy does not block a fresh assertion
    db.update_strategy_status(conn, sid, "dead")
    conn.commit()
    assert _existing_duplicate_strategy(conn, target, {crux}) is None


def test_find_canonicals_batch_dead_match_returns_dead_kind(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent_feedback 2026-07-09/10 — a candidate statement-equivalent to
    a DEAD in-problem twin gets kind='dead' so the caller can decline it
    with the twin's forensics (or release it if the proved base grew).
    Pre-fix a dead twin matched NOTHING and the blind duplicate minted."""
    _seed_problem(conn)
    root = _seed_root(conn)
    dead_g = _seed_sub(conn, slug="spent_twin",
                       statement="X", status="dead")
    _link(conn, root, [dead_g])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "spent_twin",
        "import Mathlib\ntheorem spent_twin (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "Problems.p.spent_twin" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals == [
        dedupe.CanonicalMatch(goal_id=dead_g, kind="dead"),
    ]


def test_dead_twin_block_reason_blocks_and_releases(
    conn: sqlite3.Connection,
) -> None:
    """Backward's dead-twin verdict: unchanged world → decline fragment
    carrying the twin's last failure forensics; a goal PROVED after the
    twin died → None (world changed, retry is the designed path)."""
    from Tooling.pipeline.backward import _dead_twin_block_reason
    _seed_problem(conn)
    dead_g = _seed_sub(conn, slug="spent_twin", statement="X",
                       status="dead")
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('pp1', 'Backward', ?, 'Goal', 'failed', 'failed',"
        " ?, ?)", (str(dead_g), db.now(), db.now()))
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, ts)"
        " VALUES (?, 'Goal', 'pp1', 'agent_declined',"
        " 'T1 constant too large; needs K0 bound', ?)",
        (dead_g, db.now()))
    conn.commit()

    why = _dead_twin_block_reason(conn, "p", dead_g)
    assert why is not None
    assert "T1 constant too large" in why and "spent_twin" in why

    # A goal proved AFTER the twin died releases the guard.
    fresh = _seed_sub(conn, slug="new_tool", statement="Y")
    conn.execute(
        "UPDATE goals SET status='proved',"
        " updated_at='299-01-01T00:00:00+00:00' WHERE id=?", (fresh,))
    conn.commit()
    assert _dead_twin_block_reason(conn, "p", dead_g) is None


def test_find_canonicals_batch_shelved_is_reused(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#2 — a soft-terminal 'shelved' twin is now REUSED, not ignored.
    'shelved' never blocks (only 'disproved' does), and a candidate that
    unifies with a shelved goal's statement gets kind='reuse' (the caller
    turns it into a citation + revives the shelved goal) rather than
    spawning a duplicate. Pre-#2 this returned None (new goal); the parked
    twin would re-duplicate once reopened."""
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

    # Only the shelved canonical's name unifies with the candidate.
    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "Problems.p.soft_dead" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    # Same statement SHAPE as the twin (task #6: the reuse tier requires
    # it — the citation rewrite keeps the arg list, so shape identity is
    # what makes the rewrite sound).
    cand = "import Mathlib\ntheorem c (a : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals[0] is not None
    assert canonicals[0].kind == "reuse"
    assert canonicals[0].goal_id == shelved_g


def test_find_canonicals_batch_open_cross_branch_is_reused(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#2 — an OPEN cross-branch twin (two branches landed on the same
    statement) is matched as kind='reuse' so the candidate links to it
    instead of both branches proving it."""
    _seed_problem(conn)
    root = _seed_root(conn)
    twin = _seed_sub(conn, slug="twin", statement="X", status="open")
    _link(conn, root, [twin])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "twin",
        "import Mathlib\ntheorem twin (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "Problems.p.twin" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    # Same statement SHAPE as the twin (task #6 reuse gate; see the
    # shelved-reuse test above for the rationale).
    cand = "import Mathlib\ntheorem c (a : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals[0] is not None
    assert canonicals[0].kind == "reuse"
    assert canonicals[0].goal_id == twin


def test_find_canonicals_batch_open_ancestor_is_no_progress_not_reuse(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-cycle — an OPEN ANCESTOR of the goal being decomposed must NOT
    be reused (linking to it is circular: it transitively waits for this
    candidate). It is classified `no_progress`, never `reuse`."""
    _seed_problem(conn)
    root = _seed_root(conn)
    mid = _seed_sub(conn, slug="mid", statement="X", status="open", depth=1)
    _link(conn, root, [mid])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, mid, [parent])   # parent is BELOW mid → mid is an ancestor
    _write_lean(tmp_path, "p", "mid",
        "import Mathlib\ntheorem mid (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)

    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "Problems.p.mid" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)],
    )
    assert canonicals[0] is not None
    assert canonicals[0].kind == "no_progress"


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
    # canonical fqn must NOT be empty — the regex picks up the def, then
    # find_canonicals_batch wraps it as `Problems.<problem>.<name>`.
    assert captured["pairs"], "no pair produced — regex still misses def"
    _cand_sig, _mod, canonical_fqn = captured["pairs"][0]
    assert canonical_fqn == "Problems.p.promoted_anc"
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
    root = _seed_root(conn, status="proved")
    g_anc1 = _seed_sub(conn, slug="ga1", statement="X", status="proved")
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
        return [(": X" in cand_sig and thm == "Problems.p.ga1")
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


def test_find_canonicals_batch_no_progress_on_unproved_parent(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sub-goal definitionally equal to the (still-unproved) goal being
    decomposed is `no_progress`, never an alias — the self-similar `X ⊢ X`
    decomposition that caused 13/13 of the Jordan intra-problem dups. The
    parent goal itself is the canonical the match points at."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    parent = _seed_sub(conn, slug="par", statement="X", depth=1)  # OPEN
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "par",
        "import Mathlib\ntheorem par : X := by sorry\n")

    # fake: candidate provable from canonical iff canonical is the parent.
    def fake(ws: Path, prob: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [thm == "Problems.p.par" for _sig, _mod, thm in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = "import Mathlib\ntheorem c : X := by sorry\n"
    res = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)])
    assert res[0] == dedupe.CanonicalMatch(goal_id=parent, kind="no_progress")


def test_no_progress_is_retryable_not_terminal() -> None:
    """`no_progress` must NOT be a terminal decline — the in-pipeline retry
    helper should re-prompt the same agent to decompose smaller / prove
    directly, rather than killing the strategy on a fresh cold dispatch."""
    from Tooling.pipeline._retry import _TERMINAL_DECLINE_REASONS
    assert "no_progress" not in _TERMINAL_DECLINE_REASONS
    # contrast: same_as_disproved IS terminal (re-prompt would re-emit it)
    assert "same_as_disproved" in _TERMINAL_DECLINE_REASONS


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

    monkeypatch.setattr(
        __import__("Tooling.quality.dedupe",
                   fromlist=["subprocess"]).subprocess, "run", fake_run)


def test_lake_err_re_matches_windows_absolute_path() -> None:
    """`_LAKE_ERR_RE` must match Windows-style absolute paths emitted by
    lake (`D:\\...`). The lazy `.+?` prefix lets the path contain the
    drive-letter colon; the `\\d+:\\d+` line-col anchor finds the
    boundary."""
    sample = (
        r"D:\Asterism\.attempts\_x.lean:91:2: error: Tactic apply failed"
        "\n"
        r"D:\Asterism\.attempts\_x.lean:103:5: error: another"
        "\n"
    )
    assert dedupe._LAKE_ERR_RE.findall(sample) == ["91", "103"]


def test_lake_err_re_matches_posix_path() -> None:
    """Posix-style path still matches."""
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
    # 3-tuple shape: (cand_signature, canonical_module, canonical_fqn).
    pairs = [(": Nat", "Mod.A", "Problems.p.thm_a"),
             (": Bool", "Mod.B", "Problems.p.thm_b")]
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
    pairs = [(": A", "Mod.A", "Problems.p.thm_a"),
             (": C", "Mod.C", "Problems.p.thm_c")]
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
    pairs = [(": A", "Mod.A", "Problems.p.thm_a"),
             (": B", "Mod.B", "Problems.p.thm_b")]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert result == [True, False]


def test_batch_provable_via_apply_unknown_failure_pattern_rejects_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc != 0 but no line-prefixed errors matched. Could be a parser
    panic / Lean crash. Conservative: reject all pairs."""
    _patch_subprocess(monkeypatch, stdout="", stderr="lean: panic", rc=1)
    pairs = [(": A", "Mod.A", "Problems.p.thm_a")]
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

    # cand has extra hypothesis (hcard) vs canonical. The 3rd tuple slot
    # is now the FULL fqn to `apply @` (caller-built), not a bare name;
    # the probe no longer reconstructs `Problems.<problem>.<thm>` itself.
    pairs = [
        ("(Q : Finset Nat) (h : Q.Nonempty) (hcard : 3 ≤ Q.card) : Q.Nonempty",
         "Problems.p.proofs.L_canon",
         "Problems.p.canon_thm"),
    ]
    dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    body = captured["content"]
    # Template shape: theorem _dc_0 with apply + assumption. The fqn is
    # emitted verbatim from the pair. The MODULE path
    # `Problems.<problem>.proofs.L_<slug>` is for the import.
    assert "theorem _dc_0" in body
    assert "apply @Problems.p.canon_thm" in body
    assert "<;> assumption" in body
    # Must NOT use rfl (regression guard)
    assert ":= rfl" not in body
    # Imports the canonical's module
    assert "import Problems.p.proofs.L_canon" in body


# ---------------------------------------------------------------------
# G1 — find_shelved_revivals_for_forward
# ---------------------------------------------------------------------

def _seed_forward(conn: sqlite3.Connection, *, slug: str,
                   statement: str = "T") -> int:
    """Insert a Forward-origin goal as if `commit_forward_lemma` had
    just landed it. detached=1 mirrors the runtime behaviour."""
    gid = db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement=statement, origin="forward", depth=0,
    )
    db.set_goal_detached(conn, gid, True)
    return gid


def test_find_shelved_revivals_links_matching_shelved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward output X has a signature an existing shelved S restates
    (modulo specialization). The probe pairs (S_signature, X_module,
    X_name) and returns S's id so caller can link via set_alias_target.
    """
    _seed_problem(conn)
    root = _seed_root(conn)
    shelved = _seed_sub(conn, slug="shelved_eq", statement="X",
                        status="shelved")
    _link(conn, root, [shelved])
    forward = _seed_forward(conn, slug="forward_eq")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "shelved_eq",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem shelved_eq (n : Nat) : n = n := by sorry\n"
        "end Problems.p\n")
    _write_lean(tmp_path, "p", "forward_eq",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem forward_eq (n : Nat) : n = n := by sorry\n"
        "end Problems.p\n")

    captured: dict = {}

    def fake_apply(ws, p, pairs):
        captured["pairs"] = pairs
        return [True] * len(pairs)

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake_apply)

    out = dedupe.find_shelved_revivals_for_forward(
        conn, tmp_path, problem="p", forward_goal_id=forward,
    )
    assert out == [shelved]
    # Probe direction: S as candidate (signature side), X as canonical
    # (module + thm name side).
    assert len(captured["pairs"]) == 1
    cand_sig, mod, thm = captured["pairs"][0]
    assert "n = n" in cand_sig
    assert thm == "Problems.p.forward_eq"
    assert "L_forward_eq" in mod.replace(".", "/")


def test_find_shelved_revivals_skips_non_shelved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only status='shelved' candidates enter the probe — open / proved
    / disproved are out of scope for G1."""
    _seed_problem(conn)
    _seed_root(conn)
    open_sub = _seed_sub(conn, slug="open_sub", statement="X",
                         status="open")
    proved_sub = _seed_sub(conn, slug="proved_sub", statement="X",
                           status="proved")
    forward = _seed_forward(conn, slug="f")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "open_sub",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem open_sub : True := by sorry\nend Problems.p\n")
    _write_lean(tmp_path, "p", "proved_sub",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem proved_sub : True := by sorry\nend Problems.p\n")
    _write_lean(tmp_path, "p", "f",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem f : True := by sorry\nend Problems.p\n")

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))

    out = dedupe.find_shelved_revivals_for_forward(
        conn, tmp_path, problem="p", forward_goal_id=forward,
    )
    assert out == []
    assert open_sub  # silence unused
    assert proved_sub


def test_find_shelved_revivals_skips_already_aliased(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shelved goals already linked via alias_target_id are skipped —
    each link is at-most-once to keep alias chains flat."""
    _seed_problem(conn)
    _seed_root(conn)
    s1 = _seed_sub(conn, slug="s1", statement="X", status="shelved")
    s2 = _seed_sub(conn, slug="s2", statement="X", status="shelved")
    earlier_forward = _seed_forward(conn, slug="earlier")
    db.set_alias_target(conn, s1, earlier_forward)
    forward = _seed_forward(conn, slug="f")
    for slug in ("main",):
        _write_lean(tmp_path, "p", slug,
            "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    for slug in ("s1", "s2", "earlier", "f"):
        _write_lean(tmp_path, "p", slug,
            f"import Mathlib\nnamespace Problems.p\n"
            f"theorem {slug} : True := by sorry\nend Problems.p\n")

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))

    out = dedupe.find_shelved_revivals_for_forward(
        conn, tmp_path, problem="p", forward_goal_id=forward,
    )
    assert out == [s2]


def test_find_shelved_revivals_no_match_returns_empty(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Probe returns all-False → no links."""
    _seed_problem(conn)
    _seed_root(conn)
    _seed_sub(conn, slug="s", statement="X", status="shelved")
    forward = _seed_forward(conn, slug="f")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "s",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem s : True := by sorry\nend Problems.p\n")
    _write_lean(tmp_path, "p", "f",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem f : True := by sorry\nend Problems.p\n")

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [False] * len(pairs))

    out = dedupe.find_shelved_revivals_for_forward(
        conn, tmp_path, problem="p", forward_goal_id=forward,
    )
    assert out == []


def test_find_shelved_revivals_binder_rule_skips_underbinned_candidate(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate (shelved S) must have ≥ binder GROUPS than canonical X
    so `apply @X <;> assumption` can specialize. Underbinned S can't be
    discharged via apply + assumption → pre-filter excludes. Note
    `_signature_binder_count` counts top-level groups, not individual
    names — `(x y z : Nat)` is one group."""
    _seed_problem(conn)
    _seed_root(conn)
    s = _seed_sub(conn, slug="s", statement="X", status="shelved")
    forward = _seed_forward(conn, slug="f")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    # S has 0 binder groups (no parameters before the type colon)
    _write_lean(tmp_path, "p", "s",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem s : True := by sorry\nend Problems.p\n")
    # X has 2 binder groups — strictly more, so S underbinned for X
    _write_lean(tmp_path, "p", "f",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem f (x : Nat) (h : True) : True := by sorry\nend Problems.p\n")

    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))

    out = dedupe.find_shelved_revivals_for_forward(
        conn, tmp_path, problem="p", forward_goal_id=forward,
    )
    assert s not in out


# ---------------------------------------------------------------------
# _batch_provable_via_apply pre-flight (lake build canonical modules)
# ---------------------------------------------------------------------

def test_batch_provable_pre_flight_lake_builds_unique_canonical_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before `lake env lean` runs over the dedupe check file, the
    function must `lake_build` every unique canonical module to
    materialize their .oleans. Without this pre-flight, any canonical
    whose .olean is missing trips a global 'object file does not exist'
    error and fail-opens the entire batch to all-False.

    Replaces the prior 9cc7322 scheme that materialized .oleans inline
    in verify_housekeeping — that path stalled the dispatcher main
    thread on every cascade chain.
    """
    from Tooling.pipeline import _lake as _lake_module
    import subprocess as _subprocess
    class _R:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _R())

    called: list[tuple[Path, list[str]]] = []
    def fake_lake_build_modules(workspace, modules):
        called.append((workspace, list(modules)))
        return (True, "")
    monkeypatch.setattr(_lake_module, "lake_build_modules",
                        fake_lake_build_modules)

    pairs = [
        ("(x : Nat) : x = x", "Problems.p.proofs.L_a", "Problems.p.thm_a"),
        ("(y : Nat) : y = y", "Problems.p.proofs.L_b", "Problems.p.thm_b"),
        # Duplicate canonical module — must dedupe before lake build
        ("(z : Nat) : z = z", "Problems.p.proofs.L_a", "Problems.p.thm_a2"),
    ]
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert len(result) == 3
    assert len(called) == 1, (
        f"expected exactly one batched pre-flight lake build call; "
        f"got {len(called)}")
    ws, modules = called[0]
    assert ws == tmp_path
    # Modules must be unique + sorted for determinism
    assert modules == ["Problems.p.proofs.L_a", "Problems.p.proofs.L_b"]


def test_batch_provable_pre_flight_swallows_lake_build_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-flight failure must NOT prevent the subsequent `lake env lean`
    elaboration from running; the existing fail-open path takes over
    (the batch returns all-False if Lean can't import a missing
    canonical, but dedupe still proceeds rather than crashing)."""
    from Tooling.pipeline import _lake as _lake_module
    import subprocess as _subprocess
    class _R:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _R())

    def boom_lake_build(workspace, modules):
        raise RuntimeError("lake binary missing in test env")
    monkeypatch.setattr(_lake_module, "lake_build_modules", boom_lake_build)

    pairs = [("(x : Nat) : x = x", "Mod.X", "Problems.p.thm_x")]
    # Should not raise; dedupe proceeds despite the pre-flight failure
    result = dedupe._batch_provable_via_apply(tmp_path, "p", pairs)
    assert isinstance(result, list)
    assert len(result) == 1


# ---------------------------------------------------------------------
# real-lake integration (kept last, skip if lake missing)
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Tier 1 slug-pattern dedupe (2026-05-26 post-Jordan)
# ---------------------------------------------------------------------

def test_slug_match_strips_alias_suffix(conn: sqlite3.Connection) -> None:
    """`<base>_alias` candidate should match proved `<base>` in same problem."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    base = _seed_sub(conn, slug="pushforward_d_eq", statement="T",
                    status="proved")
    hit = dedupe._slug_match_proved(
        conn, problem="p", candidate_slug="pushforward_d_eq_alias",
        parent_goal_id=root,
    )
    assert hit == base


def test_slug_match_strips_numeric_suffix(conn: sqlite3.Connection) -> None:
    """`<base>_2`, `<base>_3` etc. should match proved `<base>`."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    base = _seed_sub(conn, slug="jordan_add_const_diag", statement="T",
                    status="proved")
    for suffix in ("_2", "_3", "_4", "_5"):
        hit = dedupe._slug_match_proved(
            conn, problem="p",
            candidate_slug=f"jordan_add_const_diag{suffix}",
            parent_goal_id=root,
        )
        assert hit == base, f"slug{suffix} should match {base}"


def test_slug_match_does_not_strip_strong(conn: sqlite3.Connection) -> None:
    """`_strong` is NOT a duplicate suffix (it's a strict logical
    strengthening — different statement). Must NOT strip."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    _seed_sub(conn, slug="family_li_span", statement="T", status="proved")
    hit = dedupe._slug_match_proved(
        conn, problem="p", candidate_slug="family_li_span_strong",
        parent_goal_id=root,
    )
    assert hit is None


def test_slug_match_returns_none_when_base_missing(
    conn: sqlite3.Connection,
) -> None:
    """Stripped name not in DB → no match (don't false-positive)."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    hit = dedupe._slug_match_proved(
        conn, problem="p", candidate_slug="nonexistent_2",
        parent_goal_id=root,
    )
    assert hit is None


def test_slug_match_skips_unproved_base(conn: sqlite3.Connection) -> None:
    """Base exists but not proved (open/dead/shelved) → no match."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    _seed_sub(conn, slug="some_lemma", statement="T", status="dead")
    hit = dedupe._slug_match_proved(
        conn, problem="p", candidate_slug="some_lemma_2",
        parent_goal_id=root,
    )
    assert hit is None


def test_slug_match_excludes_parent_goal(conn: sqlite3.Connection) -> None:
    """Anti-cycle: never alias to parent_goal_id even if slug-stripped
    name would match."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    # If parent itself has slug 'main' and candidate is 'main_2', it
    # shouldn't alias to parent.
    hit = dedupe._slug_match_proved(
        conn, problem="p", candidate_slug="main_2",
        parent_goal_id=root,
    )
    assert hit is None


def test_find_canonicals_batch_tier1_hit_rides_the_probe(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT REVERSED by task #6 (was: "Tier 1 short-circuits; kernel
    probe must not run"). A slug hit is a strong PRIOR, not a verdict —
    the blind alias exploded far downstream whenever the `_2`'s statement
    had drifted from its base. The hit now seeds the probe pool's front
    and rides the existing batch call; no probe confirmation → no alias."""
    _seed_problem(conn)
    root = _seed_root(conn, status="proved")
    base = _seed_sub(conn, slug="lem_x", statement="T", status="proved")
    _write_lean(tmp_path, "p", "lem_x",
        "import Mathlib\ntheorem lem_x : T := by trivial\n")
    calls = {"pairs": []}

    def _probe(ws, p, pairs):
        calls["pairs"].extend(pairs)
        return [True] * len(pairs)
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", _probe)
    result = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=root,
        candidates=[("lem_x_alias", "theorem lem_x_alias : T := by sorry")],
    )
    assert result == [dedupe.CanonicalMatch(goal_id=base, kind="alias")]
    assert calls["pairs"], "tier-1 hit must be probe-confirmed now"
    assert calls["pairs"][0][2] == "Problems.p.lem_x"   # front of the pool


# ---------------------------------------------------------------------
# A — Library-as-dedupe-pool (cross-problem reuse)
# ---------------------------------------------------------------------

def _write_library(workspace, *,
                   index_entries,
                   files,
                   conn=None,
                   problem="libsrc"):
    """Stage a Library/ for reuse tests: decl files on disk + the v18 DB
    index (placed library_decls rows under a BRIDGED source problem -
    was: an INDEX.md file). Returns the conn (fresh in-memory one when
    not given) so callers query the same index the code under test sees."""
    if conn is None:
        conn = db.connect(":memory:")
        db.init_schema(conn)
    _seed_problem(conn, problem)
    for i, (fqn, rel) in enumerate(index_entries):
        slug = fqn.rsplit(".", 1)[-1]
        db.upsert_library_decl(conn, problem=problem, slug=slug,
                               source_goal_id=None)
        db.set_library_verdict(conn, problem=problem, slug=slug,
                               verdict="keep")
        db.set_library_classification(
            conn, problem=problem, slug=slug, target_file=rel,
            target_name=fqn, file_order=i)
        db.mark_library_migrated(conn, problem=problem, slug=slug)
    db.mark_library_bridged(conn, problem)
    for rel, content in files.items():
        fp = workspace / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    return conn


def test_conclusion_of_signature() -> None:
    assert dedupe._conclusion_of_signature("(x : Nat) : x = x") == "x = x"
    assert dedupe._conclusion_of_signature(": True") == "True"
    # colon inside a binder group is not the boundary
    assert dedupe._conclusion_of_signature(
        "(S : Submodule) : finrank S > 0") == "finrank S > 0"


def test_conclusion_of_signature_quantifier_colon_not_missplit() -> None:
    # Regression (§13 latent bug): a `∃ x : T,` / `∀ x : T,` colon in the
    # conclusion is unparenthesised → the OLD last-depth-0-colon scan split
    # there and returned a mangled tail. The type colon is the FIRST depth-0 `:`.
    assert dedupe._conclusion_of_signature(
        "(U : S) (h : P) : ∃ x : E, x ∈ U") == "∃ x : E, x ∈ U"
    assert dedupe._conclusion_of_signature(
        ": ∀ y : T, P y") == "∀ y : T, P y"


def test_to_forall_form_quantifier_colon_not_missplit() -> None:
    assert dedupe._to_forall_form(
        "(U : S) : ∃ x : E, x ∈ U") == "∀ (U : S), ∃ x : E, x ∈ U"
    # strict-implicit `⦃ ⦄` binder colon is bracketed, not the boundary
    assert dedupe._to_forall_form(
        "⦃s : S⦄ : P s") == "∀ ⦃s : S⦄, P s"


def test_distinctive_tokens_drops_stopwords_and_singletons() -> None:
    toks = dedupe._distinctive_tokens("Submodule.finrank S + n > 0")
    assert "Submodule" in toks and "finrank" in toks
    assert "S" not in toks and "n" not in toks  # single-char names dropped
    assert "by" not in dedupe._distinctive_tokens("p by q")  # stopword


def test_parse_library_decl_sigs_multidecl_skips_def() -> None:
    text = (
        "import Mathlib\n"
        "namespace Library.LinearAlgebra.SVD.Basic\n"
        "theorem alpha (x : Nat) : x = x := by rfl\n"
        "def helper := 5\n"
        "lemma beta {α} (s : Set α) : s ⊆ s := by simp\n"
        "end Library.LinearAlgebra.SVD.Basic\n"
    )
    sigs = dedupe._parse_library_decl_sigs(text)
    assert set(sigs) == {"alpha", "beta"}  # `def helper` skipped
    assert sigs["alpha"][0] == 1            # (x : Nat)
    assert "x = x" in sigs["alpha"][1]
    assert sigs["beta"][0] == 2             # {α} (s : Set α)
    assert "⊆" in sigs["beta"][1]


def test_library_canonicals_domain_filtered(tmp_path: Path) -> None:
    lconn = _write_library(
        tmp_path,
        index_entries=[
            ("Library.LinearAlgebra.SVD.Basic.alpha",
             "Library/LinearAlgebra/SVD/Basic.lean"),
            ("Library.Topology.Foo.beta", "Library/Topology/Foo.lean"),
        ],
        files={
            "Library/LinearAlgebra/SVD/Basic.lean":
                "import Mathlib\ntheorem alpha (x : Nat) : x = x := by rfl\n",
            "Library/Topology/Foo.lean":
                "import Mathlib\ntheorem beta : True := by trivial\n",
        },
    )
    canons = dedupe._library_canonicals(lconn, tmp_path, "LinearAlgebra")
    assert {c.fqn for c in canons} == {"Library.LinearAlgebra.SVD.Basic.alpha"}
    c = canons[0]
    assert c.module == "Library.LinearAlgebra.SVD.Basic"
    assert c.binder_count == 1


def test_eligible_library_filters_by_token_and_binder(tmp_path: Path) -> None:
    lconn = _write_library(
        tmp_path,
        index_entries=[
            ("Library.LinearAlgebra.A.match_decl", "Library/LinearAlgebra/A.lean"),
            ("Library.LinearAlgebra.A.no_token", "Library/LinearAlgebra/A.lean"),
            ("Library.LinearAlgebra.A.too_many_binders",
             "Library/LinearAlgebra/A.lean"),
        ],
        files={
            "Library/LinearAlgebra/A.lean":
                "import Mathlib\n"
                "theorem match_decl (S : Submodule) : "
                "Submodule.finrank S > 0 := by sorry\n"
                "theorem no_token (n : Nat) : n = n := by rfl\n"
                "theorem too_many_binders (a b c : Submodule) (h : True) : "
                "Submodule.finrank a > 0 := by sorry\n",
        },
    )
    out = dedupe._eligible_library(
        lconn, tmp_path, domain="LinearAlgebra", candidate_count=1,
        candidate_concl="Submodule.finrank T > 0")
    fqns = {fqn for _, fqn in out}
    assert "Library.LinearAlgebra.A.match_decl" in fqns       # token + binder ok
    assert "Library.LinearAlgebra.A.no_token" not in fqns     # no shared token
    assert "Library.LinearAlgebra.A.too_many_binders" not in fqns  # 2 groups > 1


def test_find_canonicals_batch_library_hit(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A candidate sub-goal that a domain Library decl can close → the
    cross-problem `library_alias` match (goal_id=-1, carries module+fqn)."""
    _seed_problem(conn, "LinearAlgebra.t")
    root = _seed_root(conn, problem="LinearAlgebra.t", status="proved")
    parent = _seed_sub(conn, problem="LinearAlgebra.t", slug="parent",
                       statement="P")
    _link(conn, root, [parent], problem="LinearAlgebra.t")
    # No in-problem lean files on disk → the in-problem pools skip (OSError),
    # so only the Library tier produces pairs.
    _write_library(
        tmp_path, conn=conn,
        index_entries=[("Library.LinearAlgebra.A.match_decl",
                        "Library/LinearAlgebra/A.lean")],
        files={"Library/LinearAlgebra/A.lean":
               "import Mathlib\ntheorem match_decl (S : Submodule) : "
               "Submodule.finrank S > 0 := by sorry\n"},
    )

    # Probe accepts only the Library pair (defends against an in-problem
    # pair sneaking in and shadowing on first-hit).
    def fake(ws: Path, p: str,
             pairs: list[tuple[str, str, str]]) -> list[bool]:
        return [fqn.startswith("Library.") for _sig, _mod, fqn in pairs]
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake)

    cand = ("import Mathlib\ntheorem c (S : Submodule) : "
            "Submodule.finrank S > 0 := by sorry\n")
    res = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="LinearAlgebra.t", parent_goal_id=parent,
        candidates=[("c", cand)])
    assert res[0] == dedupe.CanonicalMatch(
        goal_id=-1, kind="library_alias",
        library_module="Library.LinearAlgebra.A",
        library_fqn="Library.LinearAlgebra.A.match_decl")


def test_find_canonicals_batch_inproblem_shadows_library(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both an in-problem proved ancestor AND a Library decl match,
    the in-problem alias wins (Library tier is appended last → lower
    first-hit priority: prefer local reuse, keep deps in-problem)."""
    _seed_problem(conn, "LinearAlgebra.t")
    root = _seed_root(conn, problem="LinearAlgebra.t", status="proved")
    anc = _seed_sub(conn, problem="LinearAlgebra.t", slug="anc",
                    statement="X", status="proved")
    _link(conn, root, [anc], problem="LinearAlgebra.t")
    parent = _seed_sub(conn, problem="LinearAlgebra.t", slug="parent",
                       statement="OTHER", depth=2)
    _link(conn, anc, [parent], problem="LinearAlgebra.t")
    _write_lean(tmp_path, "LinearAlgebra.t", "anc",
        "import Mathlib\ntheorem anc (S : Submodule) : "
        "Submodule.finrank S > 0 := by sorry\n")
    _write_lean(tmp_path, "LinearAlgebra.t", "parent",
        "import Mathlib\ntheorem parent : OTHER := by sorry\n")
    _write_library(
        tmp_path, conn=conn,
        index_entries=[("Library.LinearAlgebra.A.match_decl",
                        "Library/LinearAlgebra/A.lean")],
        files={"Library/LinearAlgebra/A.lean":
               "import Mathlib\ntheorem match_decl (S : Submodule) : "
               "Submodule.finrank S > 0 := by sorry\n"},
    )
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [True] * len(pairs))
    cand = ("import Mathlib\ntheorem c (S : Submodule) : "
            "Submodule.finrank S > 0 := by sorry\n")
    res = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="LinearAlgebra.t", parent_goal_id=parent,
        candidates=[("c", cand)])
    assert res[0] == dedupe.CanonicalMatch(goal_id=anc, kind="alias")


def test_build_alias_with_apply_expr_uses_full_fqn() -> None:
    """Library alias body delegates via the fully-qualified `@<fqn>`
    (its namespace isn't open in the sub-goal file)."""
    original = "import Mathlib\ntheorem c (S : T) : P := by sorry\n"
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Library.LinearAlgebra.A",
        canonical_slug="Library.LinearAlgebra.A.match_decl",
        apply_expr="@Library.LinearAlgebra.A.match_decl",
    )
    assert "import Library.LinearAlgebra.A" in out
    assert (":= by apply @Library.LinearAlgebra.A.match_decl <;> assumption"
            in out)
    assert ":= by sorry" not in out


# ---------------------------------------------------------------------
# task #6 — probe-perimeter hardening
# ---------------------------------------------------------------------

def test_extract_theorem_name_skips_annotation_prose() -> None:
    """cbe5bc3's bug family, second instance: the Strategist annotation
    block opening every canonical file may mention `theorem X` in prose —
    that must not seed the probe with a garbage name."""
    text = ("-- Strategy: apply theorem foo_helper to close the gap,\n"
            "-- then the def bar_aux trick from the notes.\n"
            "theorem real_name (a : T) : X := by sorry\n")
    assert dedupe._extract_theorem_name(text) == "real_name"
    # prose only, no real declaration → None (old code returned 'foo_helper')
    prose = "-- consider theorem foo_helper here\n"
    assert dedupe._extract_theorem_name(prose) is None
    # framework-promoted alias body (def) still extracts
    alias_body = ("-- annotation\n"
                  "def promoted := @Problems.p.s99\n")
    assert dedupe._extract_theorem_name(alias_body) == "promoted"


def test_tier1_slug_hit_is_probe_confirmed(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """task #6: a `_2` slug collision with a proved base no longer blind-
    aliases — the hit seeds the probe pool (first priority) and only a
    kernel confirmation aliases. Probe says no → NO alias (the old code
    aliased on the name alone; a drifted statement then exploded at the
    parent strategy's lake build, far from the cause)."""
    _seed_problem(conn)
    root = _seed_root(conn)
    base = _seed_sub(conn, slug="foo", statement="X", status="proved")
    _link(conn, root, [base])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "foo",
        "import Mathlib\ntheorem foo (a : T) : X := by trivial\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    cand = "import Mathlib\ntheorem foo_2 (a : T) : X := by sorry\n"

    # probe confirms → alias, and the tier-1 pair was probed FIRST
    seen_pairs: list = []

    def fake_yes(ws, p, pairs):
        seen_pairs.extend(pairs)
        return [True] * len(pairs)
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply", fake_yes)
    got = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("foo_2", cand)])
    assert got == [dedupe.CanonicalMatch(goal_id=base, kind="alias")]
    assert seen_pairs and seen_pairs[0][2] == "Problems.p.foo"

    # probe refutes → NO alias (old behavior: blind alias)
    monkeypatch.setattr(dedupe, "_batch_provable_via_apply",
                        lambda ws, p, pairs: [False] * len(pairs))
    got = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("foo_2", cand)])
    assert got == [None]


def test_sig_shape_drops_kind_and_name() -> None:
    a = dedupe._sig_shape("theorem foo  (a : T)\n  : X")
    b = dedupe._sig_shape("lemma bar (a : T) : X")
    assert a == b == "(a : T) : X"
    assert dedupe._sig_shape("theorem z (a : T) (b : T) : X") != a


def test_reuse_gate_rejects_shape_mismatch(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """task #6: the reuse REWRITE keeps the candidate's arg list, so an
    apply-hit on a shape-mismatched twin (the probe is deliberately loose
    since 2026-05-11 — right for the alias tiers) must NOT become a reuse
    link: two recorded incidents ended in commit lake `Function expected`.
    Conservative: shape mismatch → novel sub-goal (None)."""
    _seed_problem(conn)
    root = _seed_root(conn)
    twin = _seed_sub(conn, slug="twin", statement="X", status="open")
    _link(conn, root, [twin])
    parent = _seed_sub(conn, slug="parent", statement="Q", depth=2)
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "twin",
        "import Mathlib\ntheorem twin (a : T) : X := by sorry\n")
    _write_lean(tmp_path, "p", "parent",
        "import Mathlib\ntheorem parent : Q := by sorry\n")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : T := by sorry\n", root=True)
    monkeypatch.setattr(
        dedupe, "_batch_provable_via_apply",
        lambda ws, p, pairs: [thm == "Problems.p.twin"
                              for _sig, _mod, thm in pairs])
    # candidate has an EXTRA binder — apply would discharge it, but the
    # citation rewrite would emit `twin a b` → Function expected
    cand = "import Mathlib\ntheorem c (a : T) (b : T) : X := by sorry\n"
    got = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("c", cand)])
    assert got == [None]


def test_library_canonicals_signature_column_no_file_read(
        tmp_path: Path) -> None:
    """v18 signature path: a decl whose kernel-true `signature`/`decl_kind`
    columns are backfilled is served straight from the DB — the .lean file
    is NEVER read (it does not even exist here). A backfilled data decl
    (kind != 'thm') is excluded from the apply-canonical pool."""
    from Tooling.state import db as _dbm
    lconn = _write_library(
        tmp_path,
        index_entries=[
            ("Library.LinearAlgebra.S.sig_thm", "Library/LinearAlgebra/S.lean"),
            ("Library.LinearAlgebra.S.sig_def", "Library/LinearAlgebra/S.lean"),
        ],
        files={})    # no files on disk — DB signatures must suffice
    _dbm.set_library_signature(
        lconn, problem="libsrc", slug="sig_thm",
        signature="Library.LinearAlgebra.S.sig_thm (S : Submodule) :"
                  " Submodule.finrank S > 0",
        decl_kind="thm")
    _dbm.set_library_signature(
        lconn, problem="libsrc", slug="sig_def",
        signature="Library.LinearAlgebra.S.sig_def : Nat", decl_kind="def")
    canons = dedupe._library_canonicals(lconn, tmp_path, "LinearAlgebra")
    assert {c.fqn for c in canons} == {"Library.LinearAlgebra.S.sig_thm"}
    c = canons[0]
    assert c.binder_count == 1
    assert "finrank" in c.concl_tokens or "Submodule.finrank" in " ".join(
        c.concl_tokens)


def test_library_canonicals_star_domain(tmp_path: Path) -> None:
    """task #6: domain='*' spans the whole Library corpus (cross-domain
    reuse unblocked); a concrete domain still filters."""
    lib = tmp_path / "Library"
    (lib / "Geometry").mkdir(parents=True)
    (lib / "LinearAlgebra").mkdir(parents=True)
    (lib / "Geometry" / "A.lean").write_text(
        "theorem geo_thm (a : T) : GX := by trivial\n", encoding="utf-8")
    (lib / "LinearAlgebra" / "B.lean").write_text(
        "theorem la_thm (a : T) : LX := by trivial\n", encoding="utf-8")
    lconn = _write_library(
        tmp_path,
        index_entries=[
            ("Library.Geometry.A.geo_thm", "Library/Geometry/A.lean"),
            ("Library.LinearAlgebra.B.la_thm",
             "Library/LinearAlgebra/B.lean"),
        ],
        files={})
    star = {c.fqn for c in dedupe._library_canonicals(lconn, tmp_path, "*")}
    geo = {c.fqn
           for c in dedupe._library_canonicals(lconn, tmp_path, "Geometry")}
    assert "Library.Geometry.A.geo_thm" in geo
    assert "Library.LinearAlgebra.B.la_thm" not in geo
    assert {"Library.Geometry.A.geo_thm",
            "Library.LinearAlgebra.B.la_thm"} <= star
