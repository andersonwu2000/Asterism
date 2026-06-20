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


def test_build_for_warnings_warm_surfaces_diagnostics(monkeypatch):
    """Stage 3: with a session token, `_build_for_warnings` verifies on the warm
    claimed slot (the lint set is driven by the injected in-content set_option,
    so warm == cold) and its warning diagnostics surface through `_all_warnings`
    exactly as a cold `lake env lean` stdout `warning:` line would."""
    def warm(token, content, **k):
        # the gate must still force the mathlib linter set ON in-content
        assert "set_option linter.mathlibStandardSet true" in content
        return {"ok": True, "timed_out": False, "diagnostics": [
            {"line": 5, "col": 0, "severity": "warning",
             "message": "This line exceeds the 100 character limit"}]}
    monkeypatch.setattr(_lifecycle, "verify_in_session", warm)
    monkeypatch.setattr(
        C._lp, "run_lean_source",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("token present — warnings gate must run warm")))
    ok, out = C._build_for_warnings(
        None, "import Mathlib\n\ntheorem t : True := by trivial\n",
        prefix="x", session_token="tok")
    assert ok is True
    assert any("100 character" in w for w in C._all_warnings(out))


# ---------------------------------------------------------------------
# #check type-snapshot extraction: the shared `_extract_check_types` core parses
# `lean --json` severities (used by the cold `_parse_check_output`). NOTE the
# type gate `_typecheck_capturing_types` is COLD-ONLY (#35 stage-2 warm path
# reverted) — its base-vs-candidate snapshot comparison demands one capture mode.
# ---------------------------------------------------------------------

def test_extract_check_types_handles_cold_and_warm_severity():
    """Same `@foo : T` payload under 'information' (cold json) and 'info' (warm
    formatted diag) must yield identical normalized types; 'error' collects."""
    cold = C._extract_check_types(
        [("information", "@A.foo : Nat → Nat"),
         ("information", "A.bar : Bool")], ["A.foo", "A.bar"])
    warm = C._extract_check_types(
        [("info", "@A.foo : Nat → Nat"),
         ("info", "A.bar : Bool")], ["A.foo", "A.bar"])
    assert cold[0] == warm[0]
    assert cold[0]["A.foo"] and cold[0]["A.bar"]
    errs = C._extract_check_types([("error", "type mismatch")], ["A.foo"])[1]
    assert errs == ["type mismatch"]


def test_extract_check_types_universe_and_prefix_disambiguation():
    """Universe annotation `@foo.{u}` is stripped; a prefix name (`foo`) does not
    capture a longer one (`foo_bar`)."""
    types, _ = C._extract_check_types(
        [("info", "@A.foo.{u} : Type u"),
         ("info", "@A.foo_bar : Nat")], ["A.foo", "A.foo_bar"])
    assert "A.foo" in types and "A.foo_bar" in types
    assert types["A.foo"] != types["A.foo_bar"]


def test_typecheck_capturing_types_is_cold_only(monkeypatch):
    """Regression (#35 stage-2 revert): the type gate MUST be cold-only — no
    `session_token` / warm path. A warm LSP `#check` capture formats complex
    types (Finset / dite / inner-product) differently from the cold `lean --json`
    baseline, so mixing them read every complex-type audit candidate as spurious
    type-drift → infinite reconverge (BasisConstruction 104-min grind in the svd
    e2e; would hit every residue complex-analysis file). Asserts the signature is
    cold-only and that it routes through the `lean --json` probe."""
    import inspect
    assert "session_token" not in inspect.signature(
        C._typecheck_capturing_types).parameters
    calls = {"cold": 0}

    def cold(ws, content, *, prefix, json=False, timeout=0):
        calls["cold"] += 1
        assert json is True                      # #check capture uses lean --json
        return C._lp.LeanRun(
            returncode=0,
            output='{"severity":"information","data":"@A.foo : Nat"}',
            timed_out=False)
    monkeypatch.setattr(C._lp, "run_lean_source", cold)
    ok, _d, types = C._typecheck_capturing_types(None, "import Mathlib\n", ["A.foo"])
    assert calls["cold"] == 1 and ok is True and types.get("A.foo") == "Nat"


# ---------------------------------------------------------------------
# Defs-origin freeze: cleanup must not modify a declaration that came from the
# problem's Defs.lean (its canonical definition). _decl_line_spans drives the
# underscore-unused skip; _decl_src + the audit frozen gate guard the audit
# free-form rewrite ("Defs 來的東西禁止任何改動").
# ---------------------------------------------------------------------

from Tooling.quality.librarian.cleanup import mechanical as M   # noqa: E402
from Tooling.quality.librarian.cleanup import audit as A        # noqa: E402

_DEFS_FILE = (
    "import Mathlib\n"
    "\n"
    "namespace P\n"
    "\n"
    "def windingNumber (n : Nat) : Nat :=\n"
    "  n + 1\n"
    "\n"
    "theorem helper (h : True) : True := by trivial\n"
    "\n"
    "end P\n")


def test_decl_line_spans_covers_def_body_only():
    spans = M._decl_line_spans(_DEFS_FILE, {"windingNumber"})
    # covers the `def` header (line 5) + its body (line 6); stops AT the next
    # decl `theorem` (line 8 excluded). Trailing blank (7) before it is harmless.
    assert 5 in spans and 6 in spans
    assert 8 not in spans and 3 not in spans          # next/prev decls excluded
    # a name not present → empty
    assert M._decl_line_spans(_DEFS_FILE, {"nope"}) == set()


def test_underscore_unused_skips_frozen(monkeypatch, tmp_path):
    # a `def` with an unused param inside a FROZEN decl must NOT be `_`-prefixed
    rel = "Library/P/F.lean"
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    src = ("import Mathlib\n\ndef windingNumber (n : Nat) : Nat :=\n  0\n")
    f.write_text(src, encoding="utf-8")
    monkeypatch.setattr(C, "_missing_oleans", lambda *a, **k: [])

    def fake_build(ws, content, *, prefix, timeout=0):
        if prefix == "_unusedvar_scan":
            # injected +2 lines → the def header is on line 5, `n` at col ~17
            return True, f"{ws}/x.lean:5:17: warning: unused variable `n`\n"
        return True, ""
    monkeypatch.setattr(C, "_build_with_output", fake_build)
    changed = M.file_cleanup_underscore_unused_hyps(
        tmp_path, "P", rel, frozen={"windingNumber"})
    assert changed is False                          # frozen → skipped, no write
    assert f.read_text(encoding="utf-8") == src      # untouched


def test_audit_gate_frozen_source_change_rejected():
    decls = [A._Decl(fqn="P.windingNumber", rel="r", module="P",
                     name="windingNumber", sig="(n : Nat) : Nat", binders=1,
                     concl_tokens=frozenset())]
    new = _DEFS_FILE.replace("  n + 1", "  n + 1 + 0")   # body reformatted
    status, detail, _ap, _w = A._audit_gate(
        None, "r", decls, original=_DEFS_FILE, new_text=new, renames_raw=None,
        base_types={}, scope=[], pool=[], frozen={"windingNumber"})
    assert status == "frozen"
    assert "windingNumber" in detail


def test_audit_gate_frozen_unchanged_passes_fence(monkeypatch):
    # frozen decl untouched → no frozen rejection (proceeds to the type gate,
    # which we stub green so the test stays lake-free)
    decls = [A._Decl(fqn="P.windingNumber", rel="r", module="P",
                     name="windingNumber", sig="(n : Nat) : Nat", binders=1,
                     concl_tokens=frozenset())]
    # add a docstring ABOVE the frozen def (allowed) — its own span is unchanged
    new = _DEFS_FILE.replace("def windingNumber",
                             "/-- the winding number. -/\ndef windingNumber")
    monkeypatch.setattr(
        C, "_typecheck_capturing_types",
        lambda ws, t, fqns, **k: (True, "", {f: "Nat → Nat" for f in fqns}))
    monkeypatch.setattr(C, "_build_for_warnings", lambda ws, t, **k: (True, ""))
    status, _d, _ap, _w = A._audit_gate(
        None, "r", decls, original=_DEFS_FILE, new_text=new, renames_raw=None,
        base_types={"P.windingNumber": "Nat → Nat"}, scope=[], pool=[],
        frozen={"windingNumber"})
    assert status != "frozen"                         # docstring above is fine


# ---------------------------------------------------------------------
# Whitespace / empty-line normalization — the text-based mathlib style linters
# (linter.style.whitespace / .emptyLine) that fire ONLY on a real module build,
# so the cold gate misses them but the audit agent's LSP errors_at surfaces them
# and it burns its 960s budget hand-fixing them. Mechanized in mechanical.py.
# ---------------------------------------------------------------------

# `lake build` leads each diagnostic with `warning:` (UNLIKE `lake env lean`'s
# `<loc>: warning: <msg>`); the parser must anchor on the `:L:C: <msg>` tail.
_WS_BUILD_OUT = (
    "warning: Library/P/X.lean:91:59: missing space in the source\n"
    "\n"
    "This part of the code\n"
    "  '(0:R) 1'\n"
    "should be written as\n"
    "  '(0 : R)'\n"
    "\n"
    "Note: This linter can be disabled with `set_option linter.style.whitespace false`\n"
    "warning: Library/P/X.lean:91:78: missing space in the source\n"
    "\n"
    "This part of the code\n"
    "  '(0:R) 1))'\n"
    "should be written as\n"
    "  '(0 : R)'\n"
    "\n"
    "warning: Library/P/X.lean:127:0: Please, write a comment here or remove this "
    "line, but do not place empty lines within commands!\n"
    "warning: Library/Other/Dep.lean:3:0: missing space in the source\n"   # other file
)


def test_parse_whitespace_warnings_lake_build_format():
    ws = M._parse_whitespace_warnings(_WS_BUILD_OUT, "X.lean")
    # both col-59 and col-78 are on line 91, same GOOD; the Dep.lean one filtered
    assert ws == {91: {"(0 : R)"}}


def test_parse_emptyline_warnings_filters_basename():
    el = M._parse_emptyline_warnings(_WS_BUILD_OUT, "X.lean")
    assert el == [127]


def test_apply_whitespace_fixes_replaces_all_on_line():
    # GOOD's spaces removed = the cramped core; every occurrence on the line is
    # the same flagged mistake, so replace-all is correct.
    text = "a\ntheorem f : (0:R) = (0:R) := rfl\nb"
    new, n = M._apply_whitespace_fixes(text, {2: {"(0 : R)"}})
    assert new == "a\ntheorem f : (0 : R) = (0 : R) := rfl\nb"
    assert n == 1


def test_apply_whitespace_fixes_longest_core_first():
    # two distinct GOODs on one line; the longer must apply first so its core
    # isn't pre-empted by the shorter.
    text = "x : ((i:R)/N) := y"
    new, _ = M._apply_whitespace_fixes(text, {1: {"((i : R)", "R) / N)"}})
    assert new == "x : ((i : R) / N) := y"


def test_apply_emptyline_fixes_descending_and_skip_nonblank():
    text = "a\n\nb\n\nc"            # blanks at lines 2 and 4
    new, d = M._apply_emptyline_fixes(text, [2, 4])
    assert new == "a\nb\nc" and d == 2
    # a non-blank flagged line is a stale diagnostic → skipped, never corrupts
    new2, d2 = M._apply_emptyline_fixes("a\nb\nc", [2])
    assert new2 == "a\nb\nc" and d2 == 0


def test_normalize_whitespace_skips_frozen(monkeypatch, tmp_path):
    rel = "Library/P/F.lean"
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    # frozen `def` whose body line has a cramped `(0:R)` — must NOT be touched
    src = ("import Mathlib\n\ndef windingNumber : R :=\n  (0:R)\n")
    f.write_text(src, encoding="utf-8")
    monkeypatch.setattr(C, "_missing_oleans", lambda *a, **k: [])
    # build reports the frozen line (4) as the only whitespace warning. The pass
    # appends a detection marker, builds, finds the only fix is on a frozen line,
    # skips it, then strips the marker — leaving the file byte-identical.
    monkeypatch.setattr(
        "Tooling.pipeline._lake.lake_build_modules",
        lambda ws, mods: (True,
                          f"warning: {rel}:4:2: missing space in the source\n"
                          "This part of the code\n  '(0:R)'\n"
                          "should be written as\n  '(0 : R)'\n"))
    changed = M.file_cleanup_normalize_whitespace(
        tmp_path, "P", rel, frozen={"windingNumber"})
    assert changed is False                              # frozen line skipped
    assert f.read_text(encoding="utf-8") == src          # marker stripped, untouched
