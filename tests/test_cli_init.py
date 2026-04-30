"""F15: cli.cmd_init Root.lean-shape guard + lifecycle behavior.

Each test sets up an isolated workspace under tmp_path and chdir's
into it so `db.connect()` (which uses a relative `asterism.db` path)
produces a fresh DB per test.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from Tooling.cli import _classify_root_body, cmd_init


# ---------------------------------------------------------------------
# _classify_root_body — pure
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
    """User-written intermediate sketch (matches f1a2b9f-style 4-sub
    form): structured proof body referring to user-named sub-lemmas."""
    text = (
        "theorem main : ∀ p, P p := by\n"
        "  intro p hp\n"
        "  have h1 := main_sub_1 p hp\n"
        "  exact h1\n"
    )
    assert _classify_root_body(text) == "unknown"


def test_classify_unknown_inline_omega() -> None:
    """Even a one-line `:= omega` is 'unknown' — only `by sorry` and
    `:= s<N>` are framework-managed shapes."""
    text = "theorem main : 1 + 1 = 2 := by omega\n"
    assert _classify_root_body(text) == "unknown"


def test_classify_no_main_theorem() -> None:
    """No theorem main at all — defensive: classify as unknown."""
    text = "import Mathlib\nnamespace Problems.x\nend Problems.x\n"
    assert _classify_root_body(text) == "unknown"


# ---------------------------------------------------------------------
# cmd_init — lifecycle integration
# ---------------------------------------------------------------------

def _setup_problem(tmp_path: Path, *, manifest_body: str) -> Path:
    pdir = tmp_path / "Problems" / "wilson"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(manifest_body, encoding="utf-8")
    return pdir


_MIN_MANIFEST = (
    "# wilson\n\n"
    "## Statement\n\n"
    "True\n\n"
    "## Difficulty\n\n"
    "1\n"
)


def _init_args(problem: str = "wilson", *, force: bool = False
               ) -> argparse.Namespace:
    return argparse.Namespace(problem=problem, force=force)


def test_init_creates_root_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing behavior — fresh init writes a sorry-stub Root.lean."""
    _setup_problem(tmp_path, manifest_body=_MIN_MANIFEST)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    root = tmp_path / "Problems" / "wilson" / "Root.lean"
    assert root.exists()
    assert ":= by sorry" in root.read_text(encoding="utf-8")


def test_init_idempotent_when_root_is_sorry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-init on a workspace with sorry-stub Root.lean is a noop and
    does not rewrite the file."""
    pdir = _setup_problem(tmp_path, manifest_body=_MIN_MANIFEST)
    monkeypatch.chdir(tmp_path)
    cmd_init(_init_args())
    before = (pdir / "Root.lean").read_text(encoding="utf-8")
    rc = cmd_init(_init_args())
    after = (pdir / "Root.lean").read_text(encoding="utf-8")
    assert rc == 0
    assert before == after


def test_init_accepts_wrap_form_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root.lean already in wrap form (problem previously proved) →
    init proceeds as a noop, no rewrite, no rejection."""
    pdir = _setup_problem(tmp_path, manifest_body=_MIN_MANIFEST)
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        "import Problems.wilson.proofs._strategy_s5\n\n"
        "namespace Problems.wilson\n\n"
        "theorem main : True := s5\n\n"
        "end Problems.wilson\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 0
    # Root.lean unchanged
    assert "s5" in (pdir / "Root.lean").read_text(encoding="utf-8")


def test_init_rejects_hand_written_sketch_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Operator confusion guard: a Root.lean someone hand-edited (e.g.
    leftover sketch from a previous experiment) must be flagged so a
    fresh init never silently wraps non-canonical state."""
    pdir = _setup_problem(tmp_path, manifest_body=_MIN_MANIFEST)
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        "namespace Problems.wilson\n\n"
        "theorem main : ∀ p, True := by\n"
        "  intro p\n"
        "  trivial\n\n"
        "end Problems.wilson\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args(force=False))
    assert rc == 1
    err = capsys.readouterr().err
    assert "non-sorry" in err.lower() or "non-wrap" in err.lower()


def test_init_force_bypasses_shape_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--force lets the user keep their hand-written Root.lean and
    proceed to DB init anyway. The file is not rewritten."""
    pdir = _setup_problem(tmp_path, manifest_body=_MIN_MANIFEST)
    custom = (
        "import Mathlib\n"
        "namespace Problems.wilson\n\n"
        "theorem main : True := trivial\n\n"
        "end Problems.wilson\n"
    )
    (pdir / "Root.lean").write_text(custom, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args(force=True))
    assert rc == 0
    assert (pdir / "Root.lean").read_text(encoding="utf-8") == custom


def test_init_missing_manifest_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pre-existing behavior: no Manifest.md → fail before touching
    Root.lean. Verify the F15 guard didn't break this path."""
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    rc = cmd_init(_init_args())
    assert rc == 1
    assert "Manifest.md" in capsys.readouterr().err
