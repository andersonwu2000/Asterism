"""diagnostics: stderr regex patterns + annotate_failure_detail."""
from __future__ import annotations

import pytest

from Tooling.diagnostics import (
    annotate_failure_detail,
    parse_lake_stderr,
    strip_lake_noise,
)


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


# ---------------------------------------------------------------------
# F13 — smart_truncate_stderr preserves error/warning lines over LEAN_PATH
# ---------------------------------------------------------------------

def test_smart_truncate_short_stderr_passthrough() -> None:
    """If stderr is already under budget, return verbatim."""
    from Tooling.diagnostics import smart_truncate_stderr
    text = "error: foo\nwarning: bar"
    assert smart_truncate_stderr(text, budget=2000) == text


def test_smart_truncate_keeps_error_when_lean_path_dominates() -> None:
    """F13 root cause: Windows lake build emits LEAN_PATH=...;...;... as
    a giant first chunk. Naive truncation cuts the actual error. Smart
    truncate must surface error lines first."""
    from Tooling.diagnostics import smart_truncate_stderr
    lean_path = "trace: .> LEAN_PATH=" + ";".join(
        f"D:/lake/packages/p{i}/lib/lean" for i in range(120)
    )  # ~3000+ chars
    error_line = "/file.lean:5:10: error: bad import 'Mathlib.Foo'"
    stderr = lean_path + "\n" + error_line + "\nmore trace"
    out = smart_truncate_stderr(stderr, budget=500)
    assert error_line in out
    assert len(out) <= 500


def test_smart_truncate_dedupes_repeated_error_lines() -> None:
    """Same error line repeated in trace + stderr should appear once
    in the surfaced section (the head-trace fill might re-include it
    verbatim, so we only check the count after dedupe — that the
    extracted block has it once)."""
    from Tooling.diagnostics import smart_truncate_stderr
    error = "error: bad import 'X'"
    # Force truncation by exceeding budget
    long_filler = "z" * 3000
    stderr = f"{error}\n{long_filler}\n{error}\nmore"
    out = smart_truncate_stderr(stderr, budget=500)
    head_marker = "--- trace head ---"
    extracted = out.split(head_marker)[0] if head_marker in out else out
    assert extracted.count(error) == 1


def test_annotate_uses_smart_truncate_then_finds_hint() -> None:
    """Integration: a long stderr with error line buried mid-text should
    yield a hint after smart-truncation surfaces the error."""
    lean_path = "trace: .> LEAN_PATH=" + ";".join(
        f"path{i}" for i in range(100)
    )
    stderr = lean_path + "\n/x.lean:1:0: error: bad import 'Mathlib.Old.Path'"
    out = annotate_failure_detail(stderr)
    assert "framework hints" in out
    assert "Mathlib.Old.Path" in out


def test_smart_truncate_preserves_lean_unknown_identifier() -> None:
    """Lean errors like `unknown identifier 'foo'` (without file:line:col
    prefix) must also be preserved."""
    from Tooling.diagnostics import smart_truncate_stderr
    long_trace = "x" * 3000
    stderr = long_trace + "\nerror: unknown identifier 'foo'\n"
    out = smart_truncate_stderr(stderr, budget=500)
    assert "unknown identifier 'foo'" in out


# ---------------------------------------------------------------------
# F17 — case-insensitive matching + autoImplicit hint variant
# ---------------------------------------------------------------------

def test_unknown_constant_capital_u_matched() -> None:
    """Lean emits `Unknown constant` (capital U) in some contexts.
    Pre-F17 the lowercase-only regex missed this entirely, so Haiku
    failures with `Unknown constant ` Nat.factorial`` got no umbrella-
    import hint and looped to shelve."""
    stderr = "error: Unknown constant `Nat.factorial`"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "Nat.factorial" in hints[0]


def test_bad_import_capital_b_matched() -> None:
    """Defensive: Lean's casing is inconsistent across versions / paths.
    `Bad import` should also work."""
    stderr = "error: Bad import 'Mathlib.X'"
    hints = parse_lake_stderr(stderr)
    assert len(hints) == 1
    assert "Mathlib.X" in hints[0]


def test_autoimplicit_hint_recognized() -> None:
    """Lean's autoImplicit elaboration hint:
       `Hint: The identifier ` ZMod` is unknown, and Lean's autoImplicit ...`
    Same root cause as a missing import — F17 surfaces an umbrella-import
    suggestion for this phrasing too."""
    stderr = (
        "error: ...\n"
        "Hint: The identifier `ZMod` is unknown, and Lean's `autoImplicit` "
        "option causes an unknown identifier to be treated as ..."
    )
    hints = parse_lake_stderr(stderr)
    assert any("ZMod" in h and "import Mathlib" in h for h in hints)


def test_annotate_surfaces_capital_u_unknown_constant() -> None:
    """End-to-end: a real Haiku-style failure (`Unknown constant
    ` Nat.factorial``) reaches `annotate_failure_detail` and now yields
    a hint section (pre-F17 it did not)."""
    stderr = (
        "error: Problems/x/L.lean:3:20: Unknown constant `Nat.factorial`\n"
        "error: Lean exited with code 1"
    )
    out = annotate_failure_detail(stderr)
    assert "framework hints" in out
    assert "Nat.factorial" in out


# ---------------------------------------------------------------------
# F32 — strip_lake_noise
# ---------------------------------------------------------------------

def test_strip_removes_lean_path_trace_line() -> None:
    """The `trace: .> LEAN_PATH=...lean.exe ...args... --json` single
    line is always pure noise."""
    stderr = (
        "✖ [10/10] Building x (3s)\n"
        "trace: .> LEAN_PATH=D:\\.lake\\packages\\Cli;...lean.exe ... --json\n"
        "error: file.lean:7: Type mismatch\n"
    )
    out = strip_lake_noise(stderr)
    assert "LEAN_PATH=" not in out
    assert "lean.exe" not in out
    assert "Type mismatch" in out
    assert "Building x" in out  # progress marker preserved


def test_strip_removes_redundant_exit_summary() -> None:
    """Lake emits `error: Lean exited with code N` + `Some required
    targets ...` + `error: build failed` after the actual error.
    All three are summary noise."""
    stderr = (
        "error: real failure here\n"
        "error: Lean exited with code 1\n"
        "Some required targets logged failures:\n"
        "- Problems.wilson.proofs.L_xxx\n"
        "error: build failed\n"
    )
    out = strip_lake_noise(stderr)
    assert "real failure here" in out
    assert "Lean exited with code" not in out
    assert "Some required targets" not in out
    assert "build failed" not in out
    assert "- Problems.wilson" not in out


def test_strip_preserves_error_warning_note_hint() -> None:
    """Actionable lines must survive verbatim."""
    stderr = (
        "error: Type mismatch on `Foo.bar`\n"
        "warning: unused variable `x`\n"
        "Note: This linter can be disabled with ...\n"
        "Hint: Use the `+revert` option to ...\n"
    )
    out = strip_lake_noise(stderr)
    assert "Type mismatch on `Foo.bar`" in out
    assert "warning: unused variable `x`" in out
    assert "Note: This linter" in out
    assert "Hint: Use the `+revert`" in out


def test_strip_preserves_multiline_type_mismatch_block() -> None:
    """`Type mismatch` reports include 3-5 lines of expected/actual
    type info — those lines don't match noise patterns and must
    survive."""
    stderr = (
        "error: file.lean:7:2: Type mismatch\n"
        "  ZMod.val_neg_one (p - 1)\n"
        "has type\n"
        "  (-(1 : ZMod (p - 1).succ)).val = p - 1\n"
        "but is expected to have type\n"
        "  (-(1 : ZMod p)).val = p - 1\n"
    )
    out = strip_lake_noise(stderr)
    assert "ZMod.val_neg_one" in out
    assert "has type" in out
    assert "but is expected to have type" in out


def test_strip_preserves_omega_counterexample_block() -> None:
    """`omega` failures emit a multi-line counterexample. Each line
    is non-noise and must survive."""
    stderr = (
        "error: file.lean:6:2: omega could not prove the goal:\n"
        "a possible counterexample may satisfy the constraints\n"
        "  a ≥ 2\n"
        "where\n"
        " a := ↑p\n"
    )
    out = strip_lake_noise(stderr)
    assert "omega could not prove" in out
    assert "counterexample" in out
    assert "a ≥ 2" in out
    assert "a := ↑p" in out


def test_strip_realistic_sample_drops_majority(
) -> None:
    """End-to-end size check on a realistic single-error stderr.
    Pre-F32: ~1400 chars, mostly LEAN_PATH dump. Post-F32: just the
    actionable lines, ≤300 chars."""
    stderr = (
        "✖ [8368/8368] Building Problems.wilson.proofs.L_s126_sub_1 (22s)\n"
        "trace: .> LEAN_PATH=D:\\Asterism\\.lake\\packages\\Cli\\.lake\\build\\lib\\lean;"
        + ";".join("D:/lake/p" + str(i) for i in range(50))
        + " c:\\elan\\toolchains\\lean.exe D:\\file.lean -o ... -i ... -c ... --json\n"
        "error: Problems/wilson/proofs/L_s126_sub_1.lean:7:2: No applicable extensionality theorem found for type\n"
        "  ZMod p\n"
        "Note: Extensionality theorems can be registered by marking them with the `[ext]` attribute\n"
        "error: Lean exited with code 1\n"
        "Some required targets logged failures:\n"
        "- Problems.wilson.proofs.L_s126_sub_1\n"
        "error: build failed\n"
    )
    out = strip_lake_noise(stderr)
    # All meaningful content preserved
    assert "Building Problems.wilson" in out
    assert "No applicable extensionality" in out
    assert "ZMod p" in out
    assert "Note: Extensionality theorems" in out
    # Significant size reduction
    assert len(out) < len(stderr) // 3


def test_strip_handles_empty() -> None:
    assert strip_lake_noise("") == ""
    assert strip_lake_noise(None) is None  # type: ignore[arg-type]


def test_strip_collapses_blank_runs() -> None:
    """Removing noise lines leaves blank lines; strip should collapse
    multiple consecutive blanks to at most one."""
    stderr = (
        "error: real\n"
        "trace: .> LEAN_PATH=foo\n"
        "trace: .> LEAN_PATH=bar\n"
        "trace: .> LEAN_PATH=baz\n"
        "Note: hi\n"
    )
    out = strip_lake_noise(stderr)
    # No 3+ blank-line runs
    assert "\n\n\n" not in out
