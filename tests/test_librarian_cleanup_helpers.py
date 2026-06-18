"""Cleanup-stage helpers — the Mathlib-PR warning gate + variable-block tidy.

`_all_warnings` is the zero-warning bar the per-file cleanup gate enforces
(broader than polish's type-preserving subset — it must catch `deprecated`,
which core-Lean always emits and the old curated regex missed).
`_collapse_redundant_variable_blocks` drops the duplicate `variable` blocks the
per-decl migrate assembly replays, scope-safely.
"""
from __future__ import annotations

from Tooling.quality.librarian.cleanup import _common as C


# ---------------------------------------------------------------------
# _all_warnings — every `warning:` line, deduped
# ---------------------------------------------------------------------

def test_all_warnings_catches_deprecated_and_lints():
    out = (
        "Foo.lean:3:0: warning: `EuclideanSpace.single_apply` has been "
        "deprecated: use `PiLp.single_apply`\n"
        "Foo.lean:9:8: warning: unused variable `h`\n"
        "Foo.lean:1:0: warning: linter.style.longFile: file exceeds 1500 lines\n"
    )
    ws = C._all_warnings(out)
    assert len(ws) == 3
    assert any("deprecated" in w for w in ws)
    assert any("unused variable" in w for w in ws)


def test_all_warnings_dedups_and_empty_on_clean():
    dup = "x.lean:1:0: warning: unused variable `h`\n" * 3
    assert len(C._all_warnings(dup)) == 1
    assert C._all_warnings("Build completed successfully.\n") == []


def test_build_for_warnings_forces_mathlib_lint_set(monkeypatch):
    # `lake env lean` ignores the lakefile leanOptions, so the gate must inject
    # the mathlib standard linter set itself — else longFile/longLine/style/…
    # are silently off and the "zero-warning" bar is a fraction of mathlib's.
    captured = {}

    def fake(ws, content, **kw):
        captured["content"] = content
        return True, ""
    monkeypatch.setattr(C, "_build_with_output", fake)
    C._build_for_warnings(None, "import Mathlib\n\ntheorem t : True := by trivial\n",
                          prefix="x")
    assert "set_option linter.mathlibStandardSet true" in captured["content"]
    assert "set_option linter.deprecated true" in captured["content"]


# ---------------------------------------------------------------------
# _collapse_redundant_variable_blocks — scope-safe duplicate removal
# ---------------------------------------------------------------------

_VAR = ("variable {d : Nat}\n"
        "  {I : Bar d}\n"
        "  {N : Type}")


def test_collapse_adjacent_identical_block():
    # The StokesIntegralDefs:24/29 shape — two identical blocks, only a blank
    # between → the second is a no-op re-declaration, dropped.
    text = f"class Foo where\n  x : Nat\n\n{_VAR}\n\n{_VAR}\n\ndef t := 0\n"
    out = C._collapse_redundant_variable_blocks(text)
    assert out.count("variable {d : Nat}") == 1
    assert "def t := 0" in out and "class Foo" in out


def test_keep_duplicate_when_decl_between():
    # A declaration between the two blocks breaks adjacency → keep both
    # (conservative: only adjacent no-ops collapse).
    text = f"{_VAR}\n\ndef a := 0\n\n{_VAR}\n\ndef b := 0\n"
    assert C._collapse_redundant_variable_blocks(text).count(
        "variable {d : Nat}") == 2


def test_keep_duplicate_after_scope_end():
    # An `end` closes the first block's scope; the second is a real re-open.
    text = (f"section\n{_VAR}\ndef a := 0\nend\n\n{_VAR}\ndef b := 0\n")
    assert C._collapse_redundant_variable_blocks(text).count(
        "variable {d : Nat}") == 2


def test_keep_distinct_adjacent_blocks():
    text = "variable {d : Nat}\n\nvariable {e : Nat}\n\ndef a := 0\n"
    out = C._collapse_redundant_variable_blocks(text)
    assert "variable {d : Nat}" in out and "variable {e : Nat}" in out


def test_noop_without_duplicates():
    text = f"{_VAR}\n\ndef a := 0\n"
    assert C._collapse_redundant_variable_blocks(text) == text


# ---------------------------------------------------------------------
# warm-or-cold verify primitive (#35): a held cleanup session's claimed slot
# serves whole-file gates (~4-5s) instead of cold `lake env lean` (~25s);
# falls back to cold with no token / on a transient or indeterminate warm
# result. `_leanrun_from_verify` adapts diagnostics → LeanRun so the existing
# text-based `.ok` / `.error_lines` / `_all_warnings` consumers are unchanged.
# ---------------------------------------------------------------------

from Tooling.lsp import lifecycle as _lifecycle  # noqa: E402


def test_leanrun_from_verify_error_diag_not_ok():
    r = {"diagnostics": [{"line": 5, "col": 2, "severity": "error",
                          "message": "type mismatch"}], "timed_out": False}
    run = C._leanrun_from_verify(r)
    assert run.ok is False
    assert 5 in run.error_lines


def test_leanrun_from_verify_warning_surfaces_in_all_warnings():
    r = {"diagnostics": [{"line": 9, "col": 0, "severity": "warning",
                          "message": "unused variable `h`"}], "timed_out": False}
    run = C._leanrun_from_verify(r)
    assert run.ok is True                       # a warning is not an error
    assert any("unused variable" in w for w in C._all_warnings(run.output))


def test_verify_source_no_token_uses_cold(monkeypatch):
    """No session token → cold `lake_probe.run_lean_source` (unchanged path)."""
    calls = {"cold": 0}

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        return C._lp.LeanRun(returncode=0, output="", timed_out=False)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    run = C._verify_source(None, "x", prefix="p", session_token=None)
    assert calls["cold"] == 1 and run.ok is True


def test_verify_source_json_bypasses_warm(monkeypatch):
    """`json=True` (#check stream) stays cold even with a token — warm
    info-diagnostic parsing of `#check` is a later stage."""
    calls = {"warm": 0, "cold": 0}

    def warm(token, content, **k):
        calls["warm"] += 1
        return {"ok": True, "diagnostics": [], "timed_out": False}

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        return C._lp.LeanRun(returncode=0, output="", timed_out=False)
    monkeypatch.setattr(_lifecycle, "verify_in_session", warm)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    C._verify_source(None, "x", prefix="p", session_token="tok", json=True)
    assert calls["cold"] == 1 and calls["warm"] == 0


def test_verify_source_token_uses_warm_no_cold(monkeypatch):
    """Token present + clean warm verdict → warm result, cold never called."""
    calls = {"cold": 0}
    monkeypatch.setattr(
        _lifecycle, "verify_in_session",
        lambda token, content, **k: {"ok": True, "diagnostics": [],
                                     "timed_out": False})

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        return C._lp.LeanRun(returncode=0, output="", timed_out=False)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    run = C._verify_source(None, "x", prefix="p", session_token="tok")
    assert run.ok is True and calls["cold"] == 0


def test_verify_source_warm_transient_falls_back_to_cold(monkeypatch):
    """Warm returns a transient/unreachable error → cold fallback (a held
    cleanup must still work when the gateway is down / standalone)."""
    calls = {"cold": 0}
    monkeypatch.setattr(
        _lifecycle, "verify_in_session",
        lambda token, content, **k: {"error": "gateway unreachable",
                                     "transient": True})

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        return C._lp.LeanRun(returncode=0, output="", timed_out=False)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    run = C._verify_source(None, "x", prefix="p", session_token="tok")
    assert calls["cold"] == 1 and run.ok is True


def test_verify_source_warm_timeout_falls_back_to_cold(monkeypatch):
    """Warm returns an INDETERMINATE result (timed_out) → cold fallback; never
    trust an unconfirmed warm verdict as a clean pass."""
    calls = {"cold": 0}
    monkeypatch.setattr(
        _lifecycle, "verify_in_session",
        lambda token, content, **k: {"ok": False, "diagnostics": [],
                                     "timed_out": True})

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        return C._lp.LeanRun(returncode=0, output="", timed_out=False)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    C._verify_source(None, "x", prefix="p", session_token="tok")
    assert calls["cold"] == 1


def test_build_file_copy_isolated_threads_token_to_warm(monkeypatch):
    """`_build_file_copy_isolated` (whole-file, warm-eligible) forwards its
    `session_token` through `_lake_check` → `_verify_source` → warm path."""
    seen = {}

    def warm(token, content, **k):
        seen["token"] = token
        seen["content"] = content
        return {"ok": True, "diagnostics": [], "timed_out": False}
    monkeypatch.setattr(_lifecycle, "verify_in_session", warm)
    monkeypatch.setattr(
        C._lp, "run_lean_source",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("warm token present — cold must not run")))
    ok, _detail = C._build_file_copy_isolated(
        None, "FILE TEXT", session_token="tok-Z")
    assert ok is True
    assert seen == {"token": "tok-Z", "content": "FILE TEXT"}
