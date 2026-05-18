"""Phase 2 — Forward pipeline framework-side logic (Step 6 scaffold).

Tests extract_forward_metadata / is_decline / commit_forward_lemma.
Agent stage tests will be added when run_forward is fleshed out.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline import forward
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


# ---------------------------------------------------------------------
# extract_forward_metadata
# ---------------------------------------------------------------------

_NEW_LEAN_OK = """\
namespace Problems.p

-- Forward rationale: bridges Mathlib's smooth-curve formulation to
-- the piecewise case needed for residue-style contour integrals.
-- entry_kind: Backward
theorem contour_deformation_piecewise (γ : ℝ → ℂ) : True := by sorry

end Problems.p
"""

_NEW_LEAN_BUILDER_ENTRY = """\
-- Forward rationale: trivial identity needed for upstream rewrite.
-- entry_kind: Builder
theorem trivial_lemma : True := by sorry
"""

_NEW_LEAN_SORRY_FREE = """\
-- Forward rationale: closed by trivial.
-- entry_kind: Builder
theorem trivial_lemma : True := by trivial
"""

_NEW_LEAN_NO_RATIONALE = """\
-- entry_kind: Backward
theorem foo : True := by sorry
"""

_NEW_LEAN_BAD_SLUG = """\
-- Forward rationale: x
theorem Foo_Bar : True := by sorry
"""


def test_extract_metadata_happy_path() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_OK)
    assert err == ""
    assert md.slug == "contour_deformation_piecewise"
    assert "bridges Mathlib" in md.rationale
    assert md.entry_kind == "Backward"
    assert md.sorry_free is False


def test_extract_metadata_builder_entry() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_BUILDER_ENTRY)
    assert err == ""
    assert md.entry_kind == "Builder"


def test_extract_metadata_sorry_free() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    assert err == ""
    assert md.sorry_free is True


def test_extract_metadata_missing_rationale() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_NO_RATIONALE)
    assert md is None
    assert "rationale" in err.lower()


def test_extract_metadata_bad_slug() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_BAD_SLUG)
    assert md is None
    assert "slug" in err.lower()


def test_extract_metadata_no_theorem() -> None:
    text = "import Mathlib\nnamespace Problems.p\nend Problems.p\n"
    md, err = forward.extract_forward_metadata(text)
    assert md is None
    assert "theorem" in err.lower()


# ---------------------------------------------------------------------
# is_decline
# ---------------------------------------------------------------------

def test_is_decline_recognized() -> None:
    text = (
        "-- decline: library_sufficient\n"
        "-- ## Why\n"
        "-- Brief asked for X; existing covers it.\n"
        "theorem _forward_decline : True := by trivial\n"
    )
    assert forward.is_decline(text) is True


def test_is_decline_not_matched_on_normal_file() -> None:
    assert forward.is_decline(_NEW_LEAN_OK) is False


# ---------------------------------------------------------------------
# commit_forward_lemma
# ---------------------------------------------------------------------

def test_auto_prepend_candidate_imports_adds_mathlib_and_defs(
    workspace: Path,
) -> None:
    """SG 2026-05-18 regression: `forward.md` tells agents not to write
    imports, but framework's commit-side verify_file reads the file
    as-is. Without auto-prepend, bare statements fail to elaborate
    (e.g. `HSub ℝ ℝ` instance-resolution error). Mutate src so verify
    AND commit both see the enriched body."""
    pdir = workspace / "Problems" / "p"
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nopen Real\n\nnamespace Problems.p\n"
        "def Foo : Type := Unit\n\nend Problems.p\n",
        encoding="utf-8",
    )
    attempts = workspace / ".attempts" / "fwd-imports"
    attempts.mkdir(parents=True)
    src = attempts / "new_bare.lean"
    src.write_text(
        "namespace Problems.p\n\n"
        "-- Forward rationale: just check the import path\n"
        "-- entry_kind: Backward\n"
        "theorem bare (a b : ℝ) : a - b = a - b := by sorry\n\n"
        "end Problems.p\n",
        encoding="utf-8",
    )

    enriched = forward._auto_prepend_candidate_imports(
        src, problem="p", workspace=workspace,
    )

    on_disk = src.read_text(encoding="utf-8")
    assert on_disk == enriched, "src must be mutated on disk"
    assert "import Mathlib" in on_disk
    assert "import Problems.p.Defs" in on_disk
    assert "open Real" in on_disk
    # Original body preserved (not overwritten).
    assert "theorem bare (a b : ℝ)" in on_disk


def test_auto_prepend_candidate_imports_idempotent(
    workspace: Path,
) -> None:
    """Re-running on already-enriched content is a no-op — agents who
    DID write the imports themselves don't get duplicate lines."""
    pdir = workspace / "Problems" / "p"
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\nnamespace Problems.p\n\nend Problems.p\n",
        encoding="utf-8",
    )
    attempts = workspace / ".attempts" / "fwd-idem"
    attempts.mkdir(parents=True)
    src = attempts / "new_x.lean"
    pre_body = (
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "-- Forward rationale: pre-imported\n"
        "-- entry_kind: Backward\n"
        "theorem x : True := by trivial\n\n"
        "end Problems.p\n"
    )
    src.write_text(pre_body, encoding="utf-8")

    enriched = forward._auto_prepend_candidate_imports(
        src, problem="p", workspace=workspace,
    )

    assert enriched == pre_body
    assert src.read_text(encoding="utf-8") == pre_body


def test_commit_writes_lean_file_and_inserts_goal(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-1"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )

    dest = workspace / "Problems" / "p" / "proofs" / \
        "L_contour_deformation_piecewise.lean"
    assert dest.exists()
    g = db.get_goal(conn, outcome.goal_id)
    assert g["origin"] == "forward"
    assert g["entry_kind"] == "Backward"
    assert g["status"] == "open"


def test_commit_sorry_free_marks_goal_proved(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-2"
    attempts.mkdir(parents=True)
    (attempts / "new_trivial_lemma.lean").write_text(
        _NEW_LEAN_SORRY_FREE, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["status"] == "proved"


def test_commit_collision_raises(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    # Pre-existing file at the target path
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    (proofs / "L_contour_deformation_piecewise.lean").write_text(
        "preexisting\n", encoding="utf-8")

    attempts = workspace / ".attempts" / "fwd-3"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    with pytest.raises(FileExistsError):
        forward.commit_forward_lemma(
            conn, problem="p", workspace=workspace,
            attempts_dir=attempts, metadata=md,
            source_filename="new_<slug>.lean",
        )


# ---------------------------------------------------------------------
# Phase 4 — Forward produces def / structure / class
# ---------------------------------------------------------------------

_NEW_LEAN_DEF = """\
namespace Problems.p

-- Forward rationale: scaffolding `lineThrough` predicate referenced by
-- the planned perpendicular-distance chain. No proof obligation.
def line_through (q r : ℝ × ℝ) : Set (ℝ × ℝ) := { p | True }

end Problems.p
"""

_NEW_LEAN_STRUCTURE = """\
namespace Problems.p

-- Forward rationale: bundle (foot, distance) so downstream lemmas can
-- pass a single record instead of two parallel arguments.
structure perp_data where
  foot : ℝ × ℝ
  dist : ℝ

end Problems.p
"""

_NEW_LEAN_CLASS = """\
namespace Problems.p

-- Forward rationale: typeclass abstraction over the determinant test
-- so future variants can plug in alternative collinearity oracles.
class collinear_oracle (α : Type) where
  test : α → α → α → Prop

end Problems.p
"""


def test_extract_metadata_def_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_DEF)
    assert err == ""
    assert md.kind == "def"
    assert md.slug == "line_through"
    # entry_kind is irrelevant for non-theorem kinds; default kept for
    # NOT NULL column compatibility.
    assert md.entry_kind == "Backward"


def test_extract_metadata_structure_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_STRUCTURE)
    assert err == ""
    assert md.kind == "structure"
    assert md.slug == "perp_data"


def test_extract_metadata_class_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_CLASS)
    assert err == ""
    assert md.kind == "class"
    assert md.slug == "collinear_oracle"


def test_non_theorem_kinds_in_NON_THEOREM_KINDS_constant() -> None:
    """Constant must list every non-theorem kind the parser accepts so
    dispatch / library / verify share a single source of truth."""
    assert forward.NON_THEOREM_KINDS == frozenset({"def", "structure", "class"})


def test_commit_def_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """def has no proof obligation: commit sets status='proved' directly,
    bypassing BFS. sorry_free is irrelevant for non-theorem kinds."""
    attempts = workspace / ".attempts" / "fwd-def"
    attempts.mkdir(parents=True)
    (attempts / "new_line_through.lean").write_text(_NEW_LEAN_DEF,
                                                    encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_DEF)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "def"
    assert g["status"] == "proved"
    assert g["origin"] == "forward"


def test_commit_structure_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-struct"
    attempts.mkdir(parents=True)
    (attempts / "new_perp_data.lean").write_text(_NEW_LEAN_STRUCTURE,
                                                 encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_STRUCTURE)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "structure"
    assert g["status"] == "proved"


def test_commit_class_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-class"
    attempts.mkdir(parents=True)
    (attempts / "new_collinear_oracle.lean").write_text(_NEW_LEAN_CLASS,
                                                        encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_CLASS)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "class"
    assert g["status"] == "proved"


def test_non_theorem_goal_excluded_from_open_goals(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Defensive: even if a non-theorem goal somehow ends up with
    status='open' (shouldn't, but bug-resistant), `db.open_goals` must
    NOT return it — dispatch has no worker that knows how to 'prove' a
    def. The SQL filter on `g.kind = 'theorem'` in open_goals enforces
    this single source of truth."""
    # Need a root so the CTE seeds the alive set; without one, no goal
    # is reachable and the kind filter would be vacuously satisfied.
    db.insert_goal(
        conn, problem="p", slug="main", lean_path="P/main.lean",
        statement="T", origin="root", depth=0, kind="theorem",
    )
    # Manually insert a def-kind goal with status='open' (bypasses
    # commit_forward_lemma's auto-proved path to test the SQL filter).
    bad_open = db.insert_goal(
        conn, problem="p", slug="leaked_def",
        lean_path="P/proofs/L_leaked_def.lean", statement="def line",
        origin="forward", depth=0, kind="def",
    )
    # Force detach=1 so the recursive alive CTE includes the def even
    # though no strategy edge connects it to the root.
    db.set_goal_detached(conn, bad_open, True)
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert bad_open not in open_ids
    # Sanity: a theorem-kind open goal IS returned via the same path.
    good_open = db.insert_goal(
        conn, problem="p", slug="leaked_theorem",
        lean_path="P/proofs/L_leaked_theorem.lean", statement="T",
        origin="forward", depth=0, kind="theorem",
    )
    db.set_goal_detached(conn, good_open, True)
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert good_open in open_ids


def test_commit_marks_forward_goal_detached(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Regression — Forward output goals must be `detached=1` so BFS
    picks them up. `db.open_goals` alive CTE seeds = root ∪ detached
    ∪ strategy descendants; Forward goals have NO parent strategy edge,
    so without detached=1 a sorry-bearing Forward (status='open') is
    invisible to BFS forever (silent stuck). SG 2026-05-18 take 7
    trace: goal 1676 'kelly_step_inward_kernel' sat at open/detached=0
    while bfs_refill silently skipped it; daemon idle-progressed
    against root without ever closing the Forward sorry."""
    # Sorry-bearing Forward — needs Backward attack
    attempts = workspace / ".attempts" / "fwd-detach-open"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["status"] == "open"
    assert g["detached"] == 1
    # And it now appears in open_goals (BFS dispatch source).
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert outcome.goal_id in open_ids

    # Sorry-free Forward — proved at commit. detached still set
    # defensively; open_goals filters by status so it doesn't surface.
    attempts2 = workspace / ".attempts" / "fwd-detach-proved"
    attempts2.mkdir(parents=True)
    (attempts2 / "new_trivial_lemma.lean").write_text(
        _NEW_LEAN_SORRY_FREE, encoding="utf-8")
    md2, _ = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    outcome2 = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts2, metadata=md2,
        source_filename="new_<slug>.lean",
    )
    g2 = db.get_goal(conn, outcome2.goal_id)
    assert g2["status"] == "proved"
    assert g2["detached"] == 1


def test_extract_metadata_no_declaration_lists_all_kinds() -> None:
    """Error message must mention all 4 accepted kinds so the agent
    knows what to write when it omits the declaration head."""
    md, err = forward.extract_forward_metadata(
        "-- Forward rationale: empty body\nnamespace Problems.p\nend Problems.p\n"
    )
    assert md is None
    for kw in ("theorem", "def", "structure", "class"):
        assert kw in err
