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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
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
