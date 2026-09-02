"""cli.cmd_init — hand-written Root.lean + type-check gate.

Statement source-of-truth is the user-authored Root.lean theorem
signature. Phase 6 made Root.lean and Defs.lean OPTIONAL, user-pinned
inputs (pure-NL mode when both absent); every file that IS present must
`lake build` cleanly, and a present Root.lean's statement is extracted
for the DB. v40: the problem's definition (charter/word/settings) comes
from `problem.json` — init requires it (or an already-registered
non-empty charter) and never parses a Manifest.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from Tooling.core.cli import (
    _classify_root_body, _extract_root_statement,
    cmd_init, cmd_init_batch,
)


# ---------------------------------------------------------------------
# _classify_root_body — pure (kept for callers other than cmd_init)
# ---------------------------------------------------------------------

def test_classify_sorry_body() -> None:
    text = (
        "import Mathlib\n"
        "namespace Problems.x\n"
        "theorem main : True := by sorry\n"
        "end Problems.x\n"
    )
    assert _classify_root_body(text) == "sorry"


def test_classify_sorry_body_with_complex_statement() -> None:
    text = (
        "theorem main : ∀ p : ℕ, p.Prime → "
        "Nat.factorial (p - 1) % p = p - 1 := by sorry\n"
    )
    assert _classify_root_body(text) == "sorry"


def test_classify_wrap_body() -> None:
    text = (
        "import Mathlib\n"
        "import Problems.x.proofs._strategy_s122\n"
        "namespace Problems.x\n"
        "theorem main : ∀ p : ℕ, True := s122\n"
        "end Problems.x\n"
    )
    assert _classify_root_body(text) == "wrap"


def test_classify_wrap_body_multidigit_strategy_id() -> None:
    text = "theorem main : True := s9999\n"
    assert _classify_root_body(text) == "wrap"


def test_classify_unknown_hand_sketch() -> None:
    text = (
        "theorem main : ∀ p, P p := by\n"
        "  intro p hp\n"
        "  have h1 := main_sub_1 p hp\n"
        "  exact h1\n"
    )
    assert _classify_root_body(text) == "unknown"


def test_classify_no_main_theorem() -> None:
    text = "import Mathlib\nnamespace Problems.x\nend Problems.x\n"
    assert _classify_root_body(text) == "unknown"


# ---------------------------------------------------------------------
# _extract_root_statement — pure
# ---------------------------------------------------------------------

def test_extract_simple_statement() -> None:
    text = "theorem main : True := by sorry\n"
    assert _extract_root_statement(text) == "True"


def test_extract_multiline_statement() -> None:
    text = (
        "theorem main : ∃ (f g : Equidecomp E (E ≃ᵢ E)),\n"
        "  Disjoint f.source g.source ∧\n"
        "  f.source ∪ g.source = Metric.closedBall (0 : E) 1 := by sorry\n"
    )
    s = _extract_root_statement(text)
    assert s is not None
    assert s.startswith("∃ (f g")
    assert "Metric.closedBall (0 : E) 1" in s


def test_extract_returns_none_on_wrap_form() -> None:
    """Post-prove wrap form is not extractable; only the sorry-stub
    shape is recognized."""
    text = "theorem main : True := s122\n"
    assert _extract_root_statement(text) is None


def test_extract_returns_none_on_missing_main() -> None:
    text = "theorem helper : True := by sorry\n"
    assert _extract_root_statement(text) is None


# ---------------------------------------------------------------------
# cmd_init — fixture + mocks
# ---------------------------------------------------------------------

_MIN_SEED = (
    '{"problem": "wilson", "charter": "Some description."}\n'
)
_MIN_DEFS = (
    "import Mathlib\n\n"
    "namespace Problems.wilson\n\nend Problems.wilson\n"
)
_MIN_ROOT = (
    "import Mathlib\n"
    "import Problems.wilson.Defs\n\n"
    "namespace Problems.wilson\n\n"
    "theorem main : True := by sorry\n\n"
    "end Problems.wilson\n"
)


def _setup_problem(tmp_path: Path, *,
                    seed_body: str = _MIN_SEED,
                    defs_body: str | None = _MIN_DEFS,
                    root_body: str | None = _MIN_ROOT,
                    name: str = "wilson") -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(seed_body, encoding="utf-8")
    if defs_body is not None:
        (pdir / "Defs.lean").write_text(defs_body, encoding="utf-8")
    if root_body is not None:
        (pdir / "Root.lean").write_text(root_body, encoding="utf-8")
    return pdir


def _init_args(problem: str = "wilson", *, force: bool = False
               ) -> argparse.Namespace:
    return argparse.Namespace(problem=problem, force=force)


@pytest.fixture
def _mock_lake_pass(monkeypatch: pytest.MonkeyPatch):
    """Monkey-patch `lake_build` to always succeed without running lake."""
    from Tooling.pipeline import _lake
    monkeypatch.setattr(_lake, "lake_build", lambda ws, p: (True, ""))


# ---------------------------------------------------------------------
# cmd_init — failure modes
# ---------------------------------------------------------------------

def test_init_pure_nl_when_root_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], _mock_lake_pass,
) -> None:
    """Phase 6 — Root.lean is OPTIONAL: missing Root means pure-NL mode.
    init succeeds, inserts the problem row but NO root goal (the fresh
    problem is structurally stalled; the T4 wake bootstraps the
    Strategist's first Inject from the charter alone)."""
    _setup_problem(tmp_path, root_body=None)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    assert "pure-NL" in capsys.readouterr().out
    from Tooling.state import db
    conn = db.connect()
    assert conn.execute(
        "SELECT 1 FROM problems WHERE name='wilson'").fetchone() is not None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM goals WHERE problem='wilson'"
    ).fetchone()["n"] == 0


def test_init_succeeds_when_defs_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], _mock_lake_pass,
) -> None:
    """Phase 6 — Defs.lean is OPTIONAL (author-vouched anchor vocabulary
    when present). Root-only init succeeds and creates the root goal."""
    _setup_problem(tmp_path, defs_body=None)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    assert "root goal id=" in capsys.readouterr().out


def test_init_fails_when_root_lake_build_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dual type-check gate: Root.lean failing lake build blocks init."""
    _setup_problem(tmp_path)
    from Tooling.pipeline import _lake

    def _fake_lake(ws, p):
        if p.name == "Root.lean":
            return False, "error: unknown identifier 'foo'"
        return True, ""

    monkeypatch.setattr(_lake, "lake_build", _fake_lake)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 1
    err = capsys.readouterr().err
    assert "Root.lean did not type-check" in err


def test_init_fails_when_defs_lake_build_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dual type-check gate: Defs.lean failing lake build blocks init."""
    _setup_problem(tmp_path)
    from Tooling.pipeline import _lake

    def _fake_lake(ws, p):
        if p.name == "Defs.lean":
            return False, "error: unknown identifier 'bar'"
        return True, ""

    monkeypatch.setattr(_lake, "lake_build", _fake_lake)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 1
    assert "Defs.lean did not type-check" in capsys.readouterr().err


def test_init_fails_when_root_lacks_theorem_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], _mock_lake_pass,
) -> None:
    """Root.lean must have `theorem main : <stmt> := by sorry` shape so
    init can extract the statement for the goals.statement DB column."""
    bad_root = (
        "import Mathlib\n"
        "namespace Problems.wilson\n\n"
        "-- no theorem main\n\n"
        "end Problems.wilson\n"
    )
    _setup_problem(tmp_path, root_body=bad_root)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 1
    assert "theorem main" in capsys.readouterr().err


def test_init_missing_seed_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No problem.json and no already-registered charter → FAIL naming
    the missing seed (v40: init's only definition source)."""
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 1
    err = capsys.readouterr().err
    assert "no charter" in err
    assert "problem.json" in err


# ---------------------------------------------------------------------
# cmd_init — success paths
# ---------------------------------------------------------------------

def test_init_succeeds_with_valid_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
) -> None:
    """Happy path: valid Defs.lean + Root.lean + problem.json → init OK."""
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    # Root.lean unchanged (user-owned, framework doesn't rewrite)
    assert (pdir / "Root.lean").read_text(encoding="utf-8") == _MIN_ROOT


def test_init_extracts_statement_from_root_not_charter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
) -> None:
    """The DB's goals.statement comes from Root.lean's theorem signature,
    NOT from the charter (NL prose, never a statement source)."""
    # Charter claims "False" (wrong on purpose); Root.lean's signature
    # says "True" — DB should contain "True".
    misleading_seed = (
        '{"problem": "wilson", "charter": "Statement: False"}\n'
    )
    _setup_problem(tmp_path, seed_body=misleading_seed,
                    root_body=_MIN_ROOT)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    from Tooling.state import db
    conn = db.connect()
    row = conn.execute(
        "SELECT statement FROM goals WHERE problem='wilson' AND slug='main'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["statement"] == "True"


def test_init_force_bypasses_type_check_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--force skips the dual lake build gate. Useful when the operator
    knows the type error is in an unrelated downstream module."""
    _setup_problem(tmp_path)
    from Tooling.pipeline import _lake

    # lake_build would fail if called, but --force should skip it entirely
    monkeypatch.setattr(
        _lake, "lake_build",
        lambda ws, p: (False, "error: would block init without --force"),
    )
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args(force=True))
    assert rc == 0


def test_init_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
) -> None:
    """Re-init on an already-initialized problem is a no-op."""
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_init_args()) == 0
    assert cmd_init(_init_args()) == 0


# ---------------------------------------------------------------------
# cmd_init_batch — bulk init for benchmark imports
# ---------------------------------------------------------------------

def _setup_problem_named(tmp_path: Path, name: str) -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(
        '{"problem": "%s", "charter": "Some description."}' % name,
        encoding="utf-8")
    (pdir / "Defs.lean").write_text(
        f"import Mathlib\n\nnamespace Problems.{name}\n\nend Problems.{name}\n",
        encoding="utf-8",
    )
    (pdir / "Root.lean").write_text(
        f"import Mathlib\nimport Problems.{name}.Defs\n\n"
        f"namespace Problems.{name}\n\n"
        f"theorem main : True := by sorry\n\n"
        f"end Problems.{name}\n",
        encoding="utf-8",
    )
    return pdir


def test_init_batch_inits_subdirs_with_required_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
) -> None:
    """Walks <root> for problem.json seeds and inits each parent dir
    (Defs/Root optional but present here)."""
    _setup_problem_named(tmp_path, "alpha")
    _setup_problem_named(tmp_path, "beta")
    (tmp_path / "Problems" / "no_seed").mkdir()
    monkeypatch.chdir(tmp_path)
    rc = cmd_init_batch(argparse.Namespace(root="Problems"))
    assert rc == 0


def test_init_batch_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
) -> None:
    _setup_problem_named(tmp_path, "alpha")
    monkeypatch.chdir(tmp_path)
    rc1 = cmd_init_batch(argparse.Namespace(root="Problems"))
    rc2 = cmd_init_batch(argparse.Namespace(root="Problems"))
    assert rc1 == 0 and rc2 == 0


def test_init_batch_missing_root_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cmd_init_batch(argparse.Namespace(root="does/not/exist"))
    assert rc == 1
    assert "not a directory" in capsys.readouterr().err


def test_init_batch_skips_the_project_docs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mock_lake_pass,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A `problem.json` a person parked in their own document tree is a
    file, not a problem (HID §3.6). The batch walks `Problems/` for
    seeds, so `_docs/` has to be skipped by the WALK — reaching
    `cmd_init` with the slug `wilson._docs.user` fails the batch on
    something the person did nothing wrong to cause."""
    _setup_problem_named(tmp_path, "alpha")
    docs = tmp_path / "Problems" / "alpha" / "_docs" / "user"
    docs.mkdir(parents=True)
    (docs / "problem.json").write_text('{"note": "a draft I saved"}',
                                       encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_init_batch(argparse.Namespace(root="Problems"))
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert "_docs" not in captured.out + captured.err
