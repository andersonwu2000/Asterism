"""cmd_init statement-hygiene gate.

The root statement extracted into `goals.statement` must not hard-code
its own `Problems.<problem>.` namespace prefix — it should use bare
names (the theorem already lives inside `namespace Problems.<problem>`
with `import Problems.<problem>.Defs`). A bare name is Library-portable:
the Librarian's Gate B re-derives this exact statement from a Defs-free
bridge by swapping the import/open, which only works if the name isn't
pinned to the Problems namespace. This enforces that at the source.

Mirrors test_e2e_dispatcher's _seed_workspace pattern: cmd_init runs
with force=True to bypass the real-toolchain dual type-check gate (no
lakefile in tmp), so this isolates the statement parse + hygiene check.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from Tooling.core import cli
from Tooling.state import db


def _seed(tmp_path: Path, statement: str) -> Path:
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    import json
    (pdir / "problem.json").write_text(
        json.dumps({"problem": "p", "charter": "Statement: True"}),
        encoding="utf-8")
    (pdir / "Defs.lean").write_text("import Mathlib\n", encoding="utf-8")
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        "import Problems.p.Defs\n"
        "namespace Problems.p\n"
        f"theorem main : {statement} := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 1\n", encoding="utf-8")
    return pdir


def test_init_rejects_self_namespace_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "Problems.p.IsFoo 0")
    rc = cli.cmd_init(argparse.Namespace(problem="p", force=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert "Problems.p." in err
    assert "bare name" in err
    # The gate fires before init_schema/db wiring (early return), so no
    # schema is even created — querying goals here would itself hit a
    # missing table. rc==1 + the stderr above is the full contract; the
    # absence of any DB side effect is implied by the early return.


def test_init_accepts_bare_statement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "0 < 1")
    rc = cli.cmd_init(argparse.Namespace(problem="p", force=True))
    assert rc == 0
    conn = db.connect()
    row = conn.execute(
        "SELECT statement FROM goals WHERE problem='p'").fetchone()
    assert row is not None
    assert row["statement"] == "0 < 1"


def test_init_accepts_bare_defs_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A statement that uses a Defs-defined predicate by its BARE name
    (the correct form) passes — only the fully-qualified self-namespace
    form is rejected."""
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "∀ n : ℕ, IsFoo n")
    rc = cli.cmd_init(argparse.Namespace(problem="p", force=True))
    assert rc == 0
    conn = db.connect()
    row = conn.execute(
        "SELECT statement FROM goals WHERE problem='p'").fetchone()
    assert row is not None and "Problems.p." not in row["statement"]
