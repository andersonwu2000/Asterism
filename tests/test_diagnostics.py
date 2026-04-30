"""diagnostics: stderr regex patterns + annotate_failure_detail."""
from __future__ import annotations

import pytest

from Tooling.diagnostics import annotate_failure_detail, parse_lake_stderr


# ---------------------------------------------------------------------
# parse_lake_stderr — pattern detection
# ---------------------------------------------------------------------

def test_bad_import_path_recognized() -> None:
    stderr = "error: bad import 'Mathlib.Data.Nat.Prime'"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "Mathlib.Data.Nat.Prime" in hints[0]
    assert "import Mathlib" in hints[0]


def test_no_such_file_recognized() -> None:
    stderr = (
        "error: no such file or directory (error code: 4294963238)\n"
        "  file: D:\\Asterism\\.lake\\packages\\mathlib\\Mathlib\\Data\\Nat\\Prime.lean"
    )
    hints = parse_lake_stderr(stderr)
    assert any("Data/Nat/Prime.lean" in h for h in hints)


def test_unknown_identifier_recognized() -> None:
    stderr = "error: unknown identifier 'fun_like.ext_iff'"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "fun_like.ext_iff" in hints[0]


def test_unknown_constant_recognized() -> None:
    stderr = "error: unknown constant 'Set.eq_of_mem_iff_mem'"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "Set.eq_of_mem_iff_mem" in hints[0]


def test_unknown_tactic_recognized() -> None:
    stderr = "error: unknown tactic 'norm_num1'"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "norm_num1" in hints[0]


def test_no_match_returns_empty() -> None:
    stderr = "error: type mismatch in have h_1\n  expected: Nat\n  got: String"
    assert parse_lake_stderr(stderr) == []


def test_empty_input_returns_empty() -> None:
    assert parse_lake_stderr("") == []
    assert parse_lake_stderr(None) == []  # type: ignore[arg-type]


def test_multiple_distinct_patterns_in_order() -> None:
    stderr = (
        "error: bad import 'Mathlib.X'\n"
        "error: unknown identifier 'foo'\n"
        "error: unknown tactic 'bar'"
    )
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 3
    assert "Mathlib.X" in hints[0]
    assert "foo" in hints[1]
    assert "bar" in hints[2]


def test_duplicate_patterns_deduped() -> None:
    """Same `bad import` mentioned twice in stderr → one hint, not two."""
    stderr = (
        "error: bad import 'Mathlib.X'\n"
        "  ... trace ...\n"
        "error: bad import 'Mathlib.X'\n"
    )
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1


# ---------------------------------------------------------------------
# annotate_failure_detail
# ---------------------------------------------------------------------

def test_annotate_appends_hint_block_when_pattern_matches() -> None:
    stderr = "error: bad import 'Mathlib.Foo.Bar'"
    out = annotate_failure_detail(stderr)
    assert stderr in out
    assert "framework hints" in out
    assert "Mathlib.Foo.Bar" in out


def test_annotate_passthrough_when_no_pattern() -> None:
    """If no pattern matches, original stderr returned verbatim — no
    hint block appended (avoids polluting failure_detail with empty
    sections)."""
    stderr = "error: type mismatch\n  ..."
    out = annotate_failure_detail(stderr)
    assert out == stderr
    assert "framework hints" not in out


def test_annotate_handles_none() -> None:
    """Defensive: annotate_failure_detail must not crash on None."""
    assert annotate_failure_detail("") == ""
