"""Tests for Tooling.meta.scan_all_problems (P6 C42)."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.meta import MetaError, scan_all_problems


_VALID_META = """\
---
problem_name: {name}
axioms:
  - propext
  - Quot.sound
  - Classical.choice
---
# {name}
"""


def _write_problem(base: Path, name: str, body: str = None) -> None:
    pdir = base / "Problems" / name
    pdir.mkdir(parents=True)
    (pdir / "META.md").write_text(
        body if body is not None else _VALID_META.format(name=name),
        encoding="utf-8",
    )


class TestScanAllProblems:
    def test_empty_workspace_returns_empty(self, tmp_path):
        result = scan_all_problems(tmp_path)
        assert result == {}

    def test_no_problems_dir_returns_empty(self, tmp_path):
        # tmp_path itself, no Problems/ subdir
        result = scan_all_problems(tmp_path)
        assert result == {}

    def test_single_problem_returned(self, tmp_path):
        _write_problem(tmp_path, "list_lemmas")
        result = scan_all_problems(tmp_path)
        assert set(result.keys()) == {"list_lemmas"}
        assert "propext" in result["list_lemmas"].axioms

    def test_multiple_problems_returned(self, tmp_path):
        _write_problem(tmp_path, "alpha")
        _write_problem(tmp_path, "beta")
        _write_problem(tmp_path, "gamma")
        result = scan_all_problems(tmp_path)
        assert set(result.keys()) == {"alpha", "beta", "gamma"}

    def test_missing_meta_skipped(self, tmp_path):
        # alpha has META.md, beta has empty dir
        _write_problem(tmp_path, "alpha")
        (tmp_path / "Problems" / "beta").mkdir(parents=True)
        result = scan_all_problems(tmp_path)
        assert set(result.keys()) == {"alpha"}

    def test_malformed_meta_skipped(self, tmp_path):
        _write_problem(tmp_path, "good")
        # bad: no frontmatter
        bad_dir = tmp_path / "Problems" / "bad"
        bad_dir.mkdir(parents=True)
        (bad_dir / "META.md").write_text("just plain text\n", encoding="utf-8")
        result = scan_all_problems(tmp_path)
        assert "good" in result
        assert "bad" not in result

    def test_empty_axioms_skipped(self, tmp_path):
        # Missing axioms field → MetaError → skipped
        bad_meta = (
            "---\n"
            "problem_name: bad_axioms\n"
            "---\n"
        )
        _write_problem(tmp_path, "bad_axioms", body=bad_meta)
        _write_problem(tmp_path, "good")
        result = scan_all_problems(tmp_path)
        assert "good" in result
        assert "bad_axioms" not in result

    def test_problem_name_uses_directory(self, tmp_path):
        # META.md says problem_name: alias_name, but directory is canonical
        meta = (
            "---\n"
            "problem_name: alias_name\n"
            "axioms:\n  - propext\n"
            "---\n"
        )
        _write_problem(tmp_path, "real_dir_name", body=meta)
        result = scan_all_problems(tmp_path)
        assert "real_dir_name" in result
        assert "alias_name" not in result
        # The MetaConfig still carries the alias for downstream consumers
        assert result["real_dir_name"].problem_name == "alias_name"

    def test_files_under_problems_root_skipped(self, tmp_path):
        # A loose file (not a dir) under Problems/ shouldn't crash the scan
        problems = tmp_path / "Problems"
        problems.mkdir()
        (problems / "stray.txt").write_text("noise", encoding="utf-8")
        _write_problem(tmp_path, "real")
        result = scan_all_problems(tmp_path)
        assert set(result.keys()) == {"real"}
