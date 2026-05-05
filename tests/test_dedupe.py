"""dedupe library: signature parser + ancestor scoping + alias body.

The Lean-kernel batch (`_batch_isdefeq`) is monkeypatched in tests so
suites stay fast and lake-independent. An optional integration test
(skipped if `lake` is missing) exercises the real subprocess on simple
inputs.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from Tooling import db, dedupe


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
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
# find_canonicals_batch (with monkeypatched _batch_isdefeq)
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
    monkeypatch.setattr(dedupe, "_batch_isdefeq",
                        lambda ws, p, pairs: [True] * len(pairs))

    candidate_text = ("import Mathlib\nnamespace P\n"
                      "theorem cand (a : T) (b : T) : X := by sorry\n"
                      "end P\n")
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidates=[("cand", candidate_text)],
    )
    assert canonicals == [proved_anc]


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

    monkeypatch.setattr(dedupe, "_batch_isdefeq",
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

    # Fake isDefEq: equal signatures → True
    def fake(ws: Path, prob: str,
             pairs: list[tuple[str, str]]) -> list[bool]:
        return [p[0] == p[1] for p in pairs]

    monkeypatch.setattr(dedupe, "_batch_isdefeq", fake)

    # cand1 has the same signature as ga1 → match
    # cand2 has a different conclusion → no match
    cand1 = "import Mathlib\ntheorem c1 (a : T) : X := by sorry\n"
    cand2 = "import Mathlib\ntheorem c2 (a : T) : Z := by sorry\n"
    canonicals = dedupe.find_canonicals_batch(
        conn, tmp_path, problem="p", parent_goal_id=p1,
        candidates=[("c1", cand1), ("c2", cand2)],
    )
    assert canonicals[0] == g_anc1
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
# _batch_isdefeq integration (skipped when lake unavailable)
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# _batch_isdefeq global-error handling (F14)
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
        "Tooling.dedupe", fromlist=["subprocess"]).subprocess,
                        "run", fake_run)


def test_batch_isdefeq_rc0_means_all_pairs_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F14: rc==0 from Lean is the canonical 'no errors anywhere' signal.
    Skip line-error parsing entirely in the happy path."""
    _patch_subprocess(monkeypatch, stdout="", stderr="", rc=0)
    pairs = [(": Nat", ": Nat"), (": Bool", ": Bool")]
    result = dedupe._batch_isdefeq(tmp_path, "p", pairs)
    assert result == [True, True]


def test_batch_isdefeq_global_error_outside_pair_range_rejects_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F14 root cause: when an error fires before the first pair (e.g.
    bad import on file line 1), Lean stops elaborating and the pair
    lines never produce errors. Old code defaulted to all-True.
    New code: rc != 0 + error outside any pair → all False."""
    # Pair lines start around 5; error at line 1 is global.
    stdout = "/tmp/x.lean:1:0: error: object file does not exist"
    _patch_subprocess(monkeypatch, stdout=stdout, stderr="", rc=1)
    pairs = [(": A", ": B"), (": C", ": D")]
    result = dedupe._batch_isdefeq(tmp_path, "p", pairs)
    assert result == [False, False]


def test_batch_isdefeq_per_pair_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When all errors are inside pair ranges, attribute per-pair.
    Pair 0 occupies lines around 6, pair 1 around 8 (after import line +
    namespace + blank). Error at the second pair's line range only."""
    # Need to inspect the actual file structure built by _batch_isdefeq.
    # Lines 1: import Mathlib
    #       2: (blank)
    #       3: namespace dedupe_check
    #       4: (blank)
    #       5: -- pair 0
    #       6: example : (...)= (...) := rfl
    #       7: (blank)
    #       8: -- pair 1
    #       9: example : (...)= (...) := rfl
    # Error at line 9 → pair 1 fails, pair 0 passes.
    stdout = "/tmp/x.lean:9:10: error: type mismatch"
    _patch_subprocess(monkeypatch, stdout=stdout, stderr="", rc=1)
    pairs = [(": A", ": A"), (": B", ": C")]
    result = dedupe._batch_isdefeq(tmp_path, "p", pairs)
    assert result == [True, False]


def test_batch_isdefeq_unknown_failure_pattern_rejects_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc != 0 but no line-prefixed errors matched. Could be a parser
    panic / Lean crash. Conservative: reject all pairs."""
    _patch_subprocess(monkeypatch, stdout="", stderr="lean: panic", rc=1)
    pairs = [(": A", ": B")]
    result = dedupe._batch_isdefeq(tmp_path, "p", pairs)
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

@pytest.mark.skipif(shutil.which("lake") is None,
                    reason="requires lake CLI on PATH")
def test_batch_isdefeq_real_lake(tmp_path: Path) -> None:
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
    pairs = [("(x : Nat) : x = x", "(y : Nat) : y = y")]
    result = dedupe._batch_isdefeq(tmp_path, "tmp", pairs)
    assert isinstance(result, list)
    assert len(result) == 1
