"""db.problem_dir / db.slug_from_problem_dir — slug ↔ filesystem path
mapping for nested Problem layouts."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import db


# ---------------------------------------------------------------------
# problem_dir — slug → filesystem path
# ---------------------------------------------------------------------

def test_problem_dir_legacy_single_component(tmp_path: Path) -> None:
    """Hand-authored problems use a single slug component — same as
    pre-nested behavior. `db.problem_dir(ws, 'sylvester_gallai')`
    returns `<ws>/Problems/sylvester_gallai`."""
    assert db.problem_dir(tmp_path, "sylvester_gallai") == \
        tmp_path / "Problems" / "sylvester_gallai"


def test_problem_dir_nested_via_dot_separator(tmp_path: Path) -> None:
    """Benchmark imports use a dot-separated slug. Each dot maps to a
    filesystem path component."""
    assert db.problem_dir(tmp_path, "Minif2f.algebra_1") == \
        tmp_path / "Problems" / "Minif2f" / "algebra_1"
    # Deeper nesting works too
    assert db.problem_dir(tmp_path, "A.B.C") == \
        tmp_path / "Problems" / "A" / "B" / "C"


# ---------------------------------------------------------------------
# slug_from_problem_dir — filesystem path → slug
# ---------------------------------------------------------------------

def test_slug_from_problem_dir_single(tmp_path: Path) -> None:
    """Inverse of problem_dir for the single-component case."""
    pdir = tmp_path / "Problems" / "wilson"
    pdir.mkdir(parents=True)
    assert db.slug_from_problem_dir(tmp_path, pdir) == "wilson"


def test_slug_from_problem_dir_nested(tmp_path: Path) -> None:
    """Path components joined by `.` form the slug."""
    pdir = tmp_path / "Problems" / "Minif2f" / "algebra_1"
    pdir.mkdir(parents=True)
    assert db.slug_from_problem_dir(tmp_path, pdir) == "Minif2f.algebra_1"


def test_slug_from_problem_dir_rejects_outside_problems(
    tmp_path: Path,
) -> None:
    """A path outside `Problems/` raises — guards against operator
    typos pointing at the wrong subtree."""
    pdir = tmp_path / "Library" / "Misc"
    pdir.mkdir(parents=True)
    with pytest.raises(ValueError):
        db.slug_from_problem_dir(tmp_path, pdir)


def test_slug_from_problem_dir_rejects_problems_root_itself(
    tmp_path: Path,
) -> None:
    """`Problems/` itself isn't a problem dir — raises rather than
    returning empty string."""
    pdir = tmp_path / "Problems"
    pdir.mkdir(parents=True)
    with pytest.raises(ValueError):
        db.slug_from_problem_dir(tmp_path, pdir)


# ---------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------

def test_problem_dir_slug_roundtrip(tmp_path: Path) -> None:
    """problem_dir ∘ slug_from_problem_dir = id (path → slug → path)."""
    for slug in ("wilson", "Minif2f.algebra_1", "Bench.cat.problem"):
        pdir = db.problem_dir(tmp_path, slug)
        pdir.mkdir(parents=True, exist_ok=True)
        assert db.slug_from_problem_dir(tmp_path, pdir) == slug
