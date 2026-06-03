"""watcher._lookup_spawn_info Context.md label parsing.

Guards the librarian pipeline labels shown in stats.md — in particular that
a migrate spawn surfaces WHICH file is in flight ("migrate <File>.lean"),
parsed read-only from the `## Migrate file `<path>`` line the librarian
Context.md already carries.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))
import watcher  # noqa: E402


def _ctx(tmp_path: Path, body: str) -> Path:
    (tmp_path / "Context.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_migrate_label_surfaces_target_file(tmp_path):
    d = _ctx(
        tmp_path,
        "# Librarian — migrate — LinearAlgebra.jordan_normal_form\n"
        "\n"
        "## Migrate file `Library/LinearAlgebra/JordanForm/BlockDiagonal.lean`\n"
        "\n"
        "body…\n",
    )
    assert watcher._lookup_spawn_info(d) == (
        "migrate BlockDiagonal.lean", "LinearAlgebra.jordan_normal_form")


def test_non_migrate_librarian_label_unchanged(tmp_path):
    d = _ctx(
        tmp_path,
        "# Librarian — dedup — LinearAlgebra.jordan_normal_form\n"
        "\nbody…\n",
    )
    assert watcher._lookup_spawn_info(d) == (
        "dedup", "LinearAlgebra.jordan_normal_form")


def test_migrate_label_falls_back_to_decl_subdir(tmp_path):
    # The incremental migrate's top-level spawn dir has no Context.md; each
    # hole lives in a `decl-<slug>/` subdir. The label must still resolve
    # (with the file) by descending into a subdir's Context.md.
    sub = tmp_path / "decl-glue_maxgen_jordan_blocks"
    sub.mkdir()
    _ctx(
        sub,
        "# Librarian — migrate — LinearAlgebra.jordan_normal_form\n"
        "\n"
        "## Migrate file `Library/LinearAlgebra/JordanForm/BlockDiagonal.lean`\n",
    )
    assert watcher._lookup_spawn_info(tmp_path) == (
        "migrate BlockDiagonal.lean", "LinearAlgebra.jordan_normal_form")
