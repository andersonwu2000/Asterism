"""Pure functions in pipeline.py — no DB, no filesystem (mostly)."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline import _lake as _lake_mod

# Real lake_build_modules, captured before conftest's autouse cold-lake
# stub — the two lake-build tests here exercise the real path-resolution
# logic with subprocess mocked locally.
_REAL_LAKE_BUILD_MODULES = _lake_mod.lake_build_modules


@pytest.fixture(autouse=True)
def _use_real_lake_build(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_lake_mod, "lake_build_modules",
                        _REAL_LAKE_BUILD_MODULES)


from Tooling.pipeline import (
    _is_sorry_stub,
    _replace_proof_body,
    _grep_forbidden,
    _extract_statement,
    _extract_decline_reason,
    _extract_leading_comments,
    _lean_path_to_module,
    _slug_from_filename,
    _safe_glob,
    _SORRY_RE,
)


# ---------------------------------------------------------------------
# _is_sorry_stub / _replace_proof_body
# ---------------------------------------------------------------------

def test_sorry_stub_canonical() -> None:
    assert _is_sorry_stub("theorem foo : Nat := by sorry\n")
    assert _is_sorry_stub("theorem foo : Nat := by sorry")


def test_sorry_stub_in_namespace() -> None:
    src = "namespace X\ntheorem foo : Nat := by sorry\nend X\n"
    assert _is_sorry_stub(src)


def test_sorry_stub_rejects_structured_patch() -> None:
    src = """theorem foo : Nat := by
  have h1 : Nat := L_sub_1
  exact h1
"""
    assert not _is_sorry_stub(src)


def test_sorry_stub_rejects_existing_proof() -> None:
    assert not _is_sorry_stub("theorem foo : Nat := by simp\n")


def test_replace_proof_body_keeps_trailing_newline() -> None:
    src = "theorem foo : Nat := by sorry\n"
    assert _replace_proof_body(src, "simp") == "theorem foo : Nat := by simp\n"


def test_replace_proof_body_strips_by_prefix() -> None:
    src = "theorem foo : Nat := by sorry\n"
    assert _replace_proof_body(src, "by aesop") == "theorem foo : Nat := by aesop\n"


# ---------------------------------------------------------------------
# _grep_forbidden
# ---------------------------------------------------------------------

def test_grep_forbidden_exact() -> None:
    assert _grep_forbidden("by exact ZMod.wilsons_lemma p hp", ["ZMod.wilsons_lemma"]) == "ZMod.wilsons_lemma"


def test_grep_forbidden_misses_substring() -> None:
    assert _grep_forbidden("by exact xZMod.wilsons_lemma_y", ["ZMod.wilsons_lemma"]) is None


def test_grep_forbidden_word_boundary() -> None:
    # the word boundary must reject `wilsons_lemma_extension`
    assert _grep_forbidden("wilsons_lemma_extension", ["wilsons_lemma"]) is None


def test_grep_forbidden_wildcard() -> None:
    assert _grep_forbidden("Mathlib.Wilson.theorem", ["Mathlib.*.theorem"]) == "Mathlib.*.theorem"


def test_grep_forbidden_returns_none_when_clean() -> None:
    assert _grep_forbidden("by simp", ["ZMod.wilsons_lemma"]) is None


# ---------------------------------------------------------------------
# _extract_statement
# ---------------------------------------------------------------------

@pytest.mark.parametrize("src,want", [
    ("theorem foo : Nat := by sorry", "Nat"),
    ("theorem foo (x : Nat) : x = x := by rfl", "x = x"),
    ("theorem foo {α : Type*} (x : α) : x = x := by rfl", "x = x"),
    ("theorem foo (h : x ≥ 0) (hy : y > 0) : x + y > 0 := by sorry", "x + y > 0"),
    ("theorem foo : ∀ p : ℕ, p.Prime → p ≥ 2 := by sorry", "∀ p : ℕ, p.Prime → p ≥ 2"),
    ("theorem foo [Inhabited α] : α := by exact default", "α"),
    ("theorem foo : (a : Nat) × (b : Nat) := by sorry", "(a : Nat) × (b : Nat)"),
    ("namespace X\ntheorem foo : True := trivial\nend X", "True"),
])
def test_extract_statement(src: str, want: str) -> None:
    assert _extract_statement(src) == want


def test_extract_statement_no_theorem() -> None:
    assert _extract_statement("def foo : Nat := 1") == ""


# ---------------------------------------------------------------------
# _lean_path_to_module / _slug_from_filename
# ---------------------------------------------------------------------

def test_lean_path_to_module(tmp_path: Path) -> None:
    workspace = tmp_path
    p = workspace / "Problems" / "wilson" / "Root.lean"
    assert _lean_path_to_module(workspace, p) == "Problems.wilson.Root"


def test_lean_path_to_module_nested(tmp_path: Path) -> None:
    workspace = tmp_path
    p = workspace / "Problems" / "wilson" / "proofs" / "L_main_sub_1.lean"
    assert _lean_path_to_module(workspace, p) == "Problems.wilson.proofs.L_main_sub_1"


def test_slug_from_filename() -> None:
    assert _slug_from_filename("new_main_sub_1.lean") == "main_sub_1"
    assert _slug_from_filename("foo.lean") == "foo"


# ---------------------------------------------------------------------
# _SORRY_RE — sorry-detection used by _try_promote_sorry_free
# ---------------------------------------------------------------------

def test_sorry_re_detects_canonical_stub() -> None:
    assert _SORRY_RE.search("theorem foo : Nat := by sorry")
    assert _SORRY_RE.search("theorem foo : Nat := by\n  sorry\n")


def test_sorry_re_detects_sorryAx_token() -> None:
    # `sorry` is a substring of `sorryAx` and we want both flagged.
    assert _SORRY_RE.search("def foo := @sorryAx _")


def test_sorry_re_misses_words_containing_sorry_substring() -> None:
    # Word-boundary anchored: hypothetical identifier with `sorry`
    # baked in as a substring (e.g. `sorrying`, `sorryless`) should
    # not flag. Realistic Lean code rarely names anything this way,
    # but the regex protects us if it ever does.
    assert _SORRY_RE.search("foo := sorrying") is None
    assert _SORRY_RE.search("foo := nosorry") is None


def test_sorry_re_clean_proof() -> None:
    src = (
        "theorem foo (n : ℕ) : n + 0 = n := by\n"
        "  rfl\n"
    )
    assert _SORRY_RE.search(src) is None


# ---------------------------------------------------------------------
# F17 + Defs auto-inject — sub-goal files get `import Mathlib` and
# `import Problems.<problem>.Defs` (when present) prepended if missing.
# ---------------------------------------------------------------------

def _make_workspace(tmp_path: Path, problem: str,
                    *, with_defs: bool) -> Path:
    p = tmp_path / "Problems" / problem
    p.mkdir(parents=True)
    if with_defs:
        (p / "Defs.lean").write_text("-- defs\n", encoding="utf-8")
    return tmp_path


def test_ensure_imports_subgoal_prepends_when_no_imports(
    tmp_path: Path,
) -> None:
    """Strict-prompt output: no imports at all. Must be patched with
    Mathlib + Defs (when Defs ships)."""
    from Tooling.pipeline import _ensure_imports_subgoal
    ws = _make_workspace(tmp_path, "x", with_defs=True)
    src = (
        "namespace Problems.x\n\n"
        "theorem foo : Nat.factorial 1 % 2 = 1 := by sorry\n\n"
        "end Problems.x\n"
    )
    out = _ensure_imports_subgoal(src, problem="x", workspace=ws)
    assert out.startswith("import Mathlib\nimport Problems.x.Defs\n")
    assert "namespace Problems.x" in out


def test_ensure_imports_subgoal_no_defs_when_problem_lacks_defs(
    tmp_path: Path,
) -> None:
    """Problem ships no Defs.lean: only Mathlib gets prepended."""
    from Tooling.pipeline import _ensure_imports_subgoal
    ws = _make_workspace(tmp_path, "x", with_defs=False)
    src = "namespace Problems.x\nend Problems.x\n"
    out = _ensure_imports_subgoal(src, problem="x", workspace=ws)
    assert out.startswith("import Mathlib\n")
    assert "import Problems.x.Defs" not in out


def test_ensure_imports_subgoal_adds_defs_when_only_mathlib(
    tmp_path: Path,
) -> None:
    """Agent wrote `import Mathlib` but forgot Defs — fill in Defs."""
    from Tooling.pipeline import _ensure_imports_subgoal
    ws = _make_workspace(tmp_path, "x", with_defs=True)
    src = "import Mathlib\n\nnamespace Problems.x\nend Problems.x\n"
    out = _ensure_imports_subgoal(src, problem="x", workspace=ws)
    assert "import Mathlib" in out
    assert "import Problems.x.Defs" in out


def test_ensure_imports_subgoal_idempotent_when_both_present(
    tmp_path: Path,
) -> None:
    """Both imports already present — passthrough, no double-injection."""
    from Tooling.pipeline import _ensure_imports_subgoal
    ws = _make_workspace(tmp_path, "x", with_defs=True)
    src = (
        "import Mathlib\n"
        "import Problems.x.Defs\n\n"
        "namespace Problems.x\n"
        "theorem foo : True := trivial\n"
        "end Problems.x\n"
    )
    assert _ensure_imports_subgoal(
        src, problem="x", workspace=ws,
    ) == src


def test_ensure_imports_subgoal_anchored_to_line_start(
    tmp_path: Path,
) -> None:
    """`import` inside a comment is not a real import — re.MULTILINE
    anchors detection to start-of-line."""
    from Tooling.pipeline import _ensure_imports_subgoal
    ws = _make_workspace(tmp_path, "x", with_defs=False)
    src = (
        "-- this comment mentions import Mathlib but isn't a directive\n"
        "namespace X\n"
        "theorem t : True := trivial\n"
        "end X\n"
    )
    out = _ensure_imports_subgoal(src, problem="x", workspace=ws)
    assert out.startswith("import Mathlib\n")


# ---------------------------------------------------------------------
# F23 — _lake_build_batch / _lake_build_modules: single subprocess for
# multiple targets so lake's internal scheduler can parallelize. Mocks
# subprocess; real-lake exercise is the existing _lake_build coverage.
# ---------------------------------------------------------------------

def test_lake_build_modules_passes_all_targets_in_one_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single `lake build m1 m2 m3` invocation — not three separate."""
    import subprocess
    from unittest.mock import MagicMock
    from Tooling import pipeline
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok, _ = pipeline._lake_build_modules(tmp_path, ["m1", "m2", "m3"])
    assert ok is True
    fake_run.assert_called_once()
    cmd = fake_run.call_args[0][0]
    assert cmd[:2] == ["lake", "build"]
    assert cmd[2:] == ["m1", "m2", "m3"]


def test_lake_build_modules_returns_failure_on_nonzero_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    from unittest.mock import MagicMock
    from Tooling import pipeline
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=1,
        stdout="", stderr="error: build failed"))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok, err = pipeline._lake_build_modules(tmp_path, ["m1", "m2"])
    assert ok is False
    assert "error" in err.lower()


def test_lake_build_modules_treats_error_in_output_as_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lake sometimes returns rc=0 but emits `error:` in stderr (e.g.
    incremental rebuild that hit a Lean elaboration error). Treat it
    as failure to match _lake_build's existing semantics."""
    import subprocess
    from unittest.mock import MagicMock
    from Tooling import pipeline
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="", stderr="error: Type mismatch ..."))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok, _ = pipeline._lake_build_modules(tmp_path, ["m1"])
    assert ok is False


def test_lake_build_modules_returns_timeout_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    from Tooling import pipeline

    def _timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=600)
    monkeypatch.setattr(pipeline.subprocess, "run", _timeout)

    ok, err = pipeline._lake_build_modules(tmp_path, ["m1", "m2"])
    assert ok is False
    assert "timed out" in err
    assert "m1 m2" in err


def test_lake_build_batch_resolves_paths_to_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_lake_build_batch(paths)` should derive module names from
    each .lean path and invoke lake once."""
    import subprocess
    from unittest.mock import MagicMock
    from Tooling import pipeline

    # Set up a workspace layout so _lean_path_to_module resolves
    (tmp_path / "Problems" / "p" / "proofs").mkdir(parents=True)
    p1 = tmp_path / "Problems" / "p" / "proofs" / "L_sub_1.lean"
    p2 = tmp_path / "Problems" / "p" / "proofs" / "L_sub_2.lean"
    p1.write_text("", encoding="utf-8")
    p2.write_text("", encoding="utf-8")

    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok, _ = pipeline._lake_build_batch(tmp_path, [p1, p2])
    assert ok is True
    fake_run.assert_called_once()
    cmd = fake_run.call_args[0][0]
    assert cmd[:2] == ["lake", "build"]
    assert cmd[2] == "Problems.p.proofs.L_sub_1"
    assert cmd[3] == "Problems.p.proofs.L_sub_2"


def test_lake_build_single_target_uses_modules_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_lake_build` (single) should still work; behaviorally
    equivalent to `_lake_build_modules(workspace, [module])`."""
    import subprocess
    from unittest.mock import MagicMock
    from Tooling import pipeline

    (tmp_path / "Problems" / "p").mkdir(parents=True)
    p = tmp_path / "Problems" / "p" / "Root.lean"
    p.write_text("", encoding="utf-8")

    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok, _ = pipeline._lake_build(tmp_path, p)
    assert ok is True
    fake_run.assert_called_once()
    cmd = fake_run.call_args[0][0]
    assert cmd == ["lake", "build", "Problems.p.Root"]


# ---------------------------------------------------------------------
# Phase 1 hint-output parser
# ---------------------------------------------------------------------

def test_parse_hint_winner_picks_first_close_marker() -> None:
    """`hint` marks goal-closing tactics with 🎉️; non-closers (only
    leave subgoals) lack the marker. Parser takes the first 🎉️ entry."""
    from Tooling.pipeline import _parse_hint_winner
    sample = (
        "info: Foo.lean:3:26: Try these:\n"
        "  [apply] 🎉️ trivial\n"
        "  [apply] norm_num\n"
        "  Remaining subgoals:\n"
        "  ⊢ False\n"
    )
    assert _parse_hint_winner(sample) == "trivial"


def test_parse_hint_winner_handles_complex_tactic() -> None:
    """Winning tactic may carry arguments / spaces."""
    from Tooling.pipeline import _parse_hint_winner
    sample = (
        "info: Foo.lean:3:60: Try these:\n"
        "  [apply] 🎉️ exact Std.lt_trans h1 h2\n"
    )
    assert _parse_hint_winner(sample) == "exact Std.lt_trans h1 h2"


def test_parse_hint_winner_returns_none_on_no_close() -> None:
    """No 🎉️-marked entry → None (caller falls through to Phase 2)."""
    from Tooling.pipeline import _parse_hint_winner
    # Output where every candidate left subgoals — pathological but
    # possible if hint passed but no full close.
    assert _parse_hint_winner("info: foo: Try these:\n  [apply] norm_num\n") is None
    # Empty / unrelated output.
    assert _parse_hint_winner("") is None
    assert _parse_hint_winner("error: No suggestions available") is None


# ---------------------------------------------------------------------
# F52 — _signature_prefix / _build_strategy_skeleton / _inject_imports_for_subs
# ---------------------------------------------------------------------

def test_signature_prefix_simple() -> None:
    from Tooling.pipeline import _signature_prefix
    src = "theorem foo : Nat := by rfl\n"
    assert _signature_prefix(src, "foo") == "theorem foo : Nat "


def test_signature_prefix_with_binders() -> None:
    from Tooling.pipeline import _signature_prefix
    src = (
        "theorem foo {X : Type*} (P : X → X) (x : X) : P x = P x := by sorry\n"
    )
    out = _signature_prefix(src, "foo")
    assert "{X : Type*}" in out
    assert "(P : X → X)" in out
    assert "(x : X)" in out
    assert "P x = P x" in out
    assert ":=" not in out


def test_signature_prefix_ignores_assign_inside_binder_default() -> None:
    """Top-level `:=` walking must skip `:=` nested inside parens."""
    from Tooling.pipeline import _signature_prefix
    src = "theorem foo (x : Nat := 0) : x = x := by rfl\n"
    out = _signature_prefix(src, "foo")
    # Must not stop at the inner `:=` (binder default), should reach
    # the top-level `:=` after `x = x`.
    assert "x = x" in out


def test_signature_prefix_picks_named_theorem_among_aux() -> None:
    """Agent might write helper theorems before the locked one. We must
    return the prefix of `theorem <sid>` specifically."""
    from Tooling.pipeline import _signature_prefix
    src = (
        "theorem helper : Nat := 0\n\n"
        "theorem s42 (x : Nat) : x = x := by rfl\n"
    )
    out = _signature_prefix(src, "s42")
    assert "(x : Nat)" in out
    assert "x = x" in out
    assert "helper" not in out


def test_signature_prefix_missing_decl_returns_empty() -> None:
    from Tooling.pipeline import _signature_prefix
    # No theorem/def/structure/class head named `foo` → empty.
    assert _signature_prefix("notation \"x\" => y", "foo") == ""


def test_signature_prefix_supports_def_with_type() -> None:
    """Curry-Howard unified — `def <name> : <type> := ...` parses the
    same way as `theorem <name> : <type> := ...`."""
    from Tooling.pipeline import _signature_prefix
    src = "def foo : Nat := 0\n"
    assert _signature_prefix(src, "foo") == "def foo : Nat "


def test_signature_prefix_rejects_comment_only_subgoal_file() -> None:
    """Bug B regression — Backward agent occasionally writes a
    `new_<slug>.lean` containing only imports + an `-- obsolete:
    superseded by ...` comment (polar 2026-05-22's
    `square_root_of_positive`). The framework relies on
    `signature_prefix` returning empty for such files so the parse-fn
    `_abort`s with `parse_proposal_fail` and forces the agent to
    delete the redundant file rather than leaving a comment placeholder."""
    from Tooling.pipeline import _signature_prefix
    src = (
        "import Mathlib\n"
        "import Problems.foo.Defs\n"
        "\n"
        "-- obsolete: superseded by other_lemma\n"
    )
    assert _signature_prefix(src, "square_root_of_positive") == ""


def test_normalize_signature_collapses_whitespace() -> None:
    from Tooling.pipeline import _normalize_signature
    a = "theorem  s1 \n   {X : Type*}  \t : True"
    b = "theorem s1 {X : Type*} : True"
    assert _normalize_signature(a) == _normalize_signature(b)


def test_build_strategy_skeleton_renames_and_stubs() -> None:
    from Tooling.pipeline import _build_strategy_skeleton, _normalize_signature
    parent = (
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "theorem g {X : Type*} (P : X → X) (x : X) : P x = P x := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s7", namespace="Problems.p")
    assert sk is not None
    # Renamed
    assert "theorem s7" in sk
    assert "theorem g" not in sk
    # Binders + conclusion preserved
    assert "{X : Type*}" in sk
    assert "(P : X → X)" in sk
    assert "P x = P x" in sk
    # Body stubbed
    assert ":= by sorry" in sk
    # Imports + namespace carried
    assert "import Mathlib" in sk
    assert "import Problems.p.Defs" in sk
    assert "namespace Problems.p" in sk
    assert "end Problems.p" in sk


def test_build_strategy_skeleton_returns_none_when_parent_already_promoted() -> None:
    """Race-safe: if a sibling Verify already replaced parent stub with
    `def g := @ns.s5`, the resulting decl has no top-level type colon.
    `_has_top_level_type_colon` returns False → skeleton aborts cleanly
    instead of producing a meaningless `def s_new := by sorry` patch."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nnamespace Problems.p\n\n"
        "def g := @Problems.p.s5\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s9", namespace="Problems.p")
    assert sk is None


def test_build_strategy_skeleton_preserves_def_kind() -> None:
    """Curry-Howard unified — a `def parent : T := by sorry` stub is a
    Type-valued obligation, attacked the same way as a theorem. The
    skeleton preserves the `def` keyword so the strategy patch elaborates
    as a def (not a theorem, which would need explicit type and refuse
    the alias-time `def s := @...` promotion shape)."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nnamespace Problems.p\n\n"
        "def boundary (n : Nat) : Nat → Nat := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="boundary", sid_token="s12",
        namespace="Problems.p",
    )
    assert sk is not None
    assert "def s12" in sk
    assert "theorem s12" not in sk
    assert "(n : Nat) : Nat → Nat" in sk
    assert ":= by sorry" in sk


def test_build_strategy_skeleton_carries_open_header() -> None:
    """T2: the seeded skeleton carries the goal's own `open` lines, not
    just imports. `𝓡∂` needs `open scoped Manifold`, `volume`/`Integrable`
    need `open MeasureTheory`; omitting them elaborated the stub with a
    misleading `unexpected token '∂'` / autoImplicit error and cost a
    header-reconstruction round-trip every Backward spawn
    (agent_feedback T2). Opens are hoisted before the namespace
    (file-level scope) and sourced from the goal's OWN file, so a
    pure-analysis sub-goal whose parent has no opens stays cargo-free."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "open scoped Manifold\nopen MeasureTheory\n\n"
        "namespace Problems.p\n\n"
        "theorem g (f : ℝ → ℝ) : HasDerivAt f 0 0 := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s7", namespace="Problems.p")
    assert sk is not None
    assert "open scoped Manifold" in sk
    assert "open MeasureTheory" in sk
    # Opens land before the namespace (file-level scope), after imports.
    assert sk.index("import Mathlib") < sk.index("open scoped Manifold")
    assert sk.index("open MeasureTheory") < sk.index("namespace Problems.p")


def test_build_strategy_skeleton_no_opens_when_parent_has_none() -> None:
    """A parent with imports only seeds an opens-free skeleton — the
    fix must not fabricate an empty `open` line or change the
    no-opens shape."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\n\n"
        "namespace Problems.p\n\n"
        "theorem g (n : Nat) : n = n := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s3", namespace="Problems.p")
    assert sk is not None
    assert "open " not in sk
    assert sk.startswith("import Mathlib\n\nnamespace Problems.p")


def test_build_strategy_skeleton_carries_variable_block() -> None:
    """T13: the seeded skeleton carries the goal's file-level `variable {...}`
    binders, not just imports/opens. A signature copied from a manifold/
    abstract parent often relies on auto-bound `variable` binders rather than
    spelling them in the head; omitting them elaborates the stub with
    `unknown identifier` on the binder names and cost a Backward
    header-reconstruction round-trip (agent_feedback T13). Variables land
    inside the namespace, above the decl (mirrors the parent's scoping)."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "open scoped Manifold\n\n"
        "namespace Problems.p\n\n"
        "variable {M : Type*} [TopologicalSpace M]\n\n"
        "theorem g (x : M) : x = x := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s9", namespace="Problems.p")
    assert sk is not None
    assert "variable {M : Type*} [TopologicalSpace M]" in sk
    # Inside the namespace, above the renamed decl.
    assert sk.index("namespace Problems.p") < sk.index("variable {M")
    assert sk.index("variable {M") < sk.index("s9")


def test_build_strategy_skeleton_no_variable_when_parent_has_none() -> None:
    """A parent without a `variable` block seeds a variable-free skeleton —
    the fix must not fabricate one."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\n\n"
        "namespace Problems.p\n\n"
        "theorem g (n : Nat) : n = n := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s3", namespace="Problems.p")
    assert sk is not None
    assert "variable " not in sk


def test_build_strategy_skeleton_preserves_structure_kind() -> None:
    """structure parent with a `:= by sorry` body (rare but legal Lean
    when fields are absent and a default term is provided): preserve
    `structure` keyword."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nnamespace Problems.p\n\n"
        "structure data : Type := by sorry\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="data", sid_token="s33",
        namespace="Problems.p",
    )
    assert sk is not None
    assert "structure s33" in sk


def test_inject_imports_for_subs_adds_missing(tmp_path: Path) -> None:
    from Tooling.pipeline import _inject_imports_for_subs
    workspace = tmp_path
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    patch = proofs / "_strategy_s7.lean"
    patch.write_text(
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "theorem s7 : True := by trivial\n\n"
        "end Problems.p\n",
        encoding="utf-8")
    sub1 = proofs / "L_s7_sub_1.lean"
    sub1.write_text("--", encoding="utf-8")
    sub2 = proofs / "L_s7_sub_2.lean"
    sub2.write_text("--", encoding="utf-8")
    _inject_imports_for_subs(workspace, patch, [sub1, sub2])
    text = patch.read_text(encoding="utf-8")
    assert "import Problems.p.proofs.L_s7_sub_1" in text
    assert "import Problems.p.proofs.L_s7_sub_2" in text
    # Original imports preserved, theorem unchanged
    assert "import Mathlib" in text
    assert "theorem s7" in text


def test_inject_imports_for_subs_idempotent(tmp_path: Path) -> None:
    from Tooling.pipeline import _inject_imports_for_subs
    workspace = tmp_path
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    patch = proofs / "_strategy_s7.lean"
    patch.write_text(
        "import Mathlib\nimport Problems.p.proofs.L_s7_sub_1\n\n"
        "namespace Problems.p\nend Problems.p\n",
        encoding="utf-8")
    sub1 = proofs / "L_s7_sub_1.lean"
    sub1.write_text("--", encoding="utf-8")
    _inject_imports_for_subs(workspace, patch, [sub1])
    text = patch.read_text(encoding="utf-8")
    assert text.count("import Problems.p.proofs.L_s7_sub_1") == 1


def test_promote_to_alias_writes_def_re_export(tmp_path: Path) -> None:
    """def (not theorem) — Lean 4 theorem requires explicit `: <type>`,
    and we want the type to come from the strategy's signature, not
    from a serialized goal.statement (which lacks binders)."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_g.lean"
    parent.write_text(
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "theorem g {X : Type*} (P : X → X) (x : X) : P x = P x := by sorry\n\n"
        "end Problems.p\n",
        encoding="utf-8")
    backup = _promote_to_alias(
        parent,
        namespace="Problems.p", slug="g", sid_token="s42",
        scratch_module="Problems.p.proofs._strategy_s42",
    )
    new = parent.read_text(encoding="utf-8")
    assert "def g := @Problems.p.s42" in new
    assert "{X : Type*}" not in new  # binders replaced — type comes from s42
    assert "by sorry" not in new
    assert "import Mathlib" in new
    assert "import Problems.p.Defs" in new
    assert "import Problems.p.proofs._strategy_s42" in new
    assert backup is not None and "by sorry" in backup.read_text(encoding="utf-8")


def test_promote_to_alias_carries_noncomputable_modifier(tmp_path: Path) -> None:
    """A `noncomputable def` data-goal parent must re-export as
    `noncomputable def <slug> := @<sid>`. Dropping the modifier (carrying
    only `@[attrs]`) compile-fails on cold `lake build` — "mark it
    'noncomputable'" — because the strategy `sN` IS noncomputable. This
    slips past verify-collapse (mechanical promote, no cold build) and a
    trivial `main : True` root (never imports the closure), staying latent
    until harvest / review cold-builds it (BUG4, MV ingest stress test)."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_iso.lean"
    parent.write_text(
        "import Mathlib\n\nnamespace Problems.p\n\n"
        "noncomputable def iso : SomeCat.Iso A B := by sorry\n\n"
        "end Problems.p\n",
        encoding="utf-8")
    _promote_to_alias(
        parent,
        namespace="Problems.p", slug="iso", sid_token="s77",
        scratch_module="Problems.p.proofs._strategy_s77",
    )
    new = parent.read_text(encoding="utf-8")
    assert "noncomputable def iso := @Problems.p.s77" in new


def test_promote_to_alias_noncomputable_from_strategy_decl(tmp_path: Path) -> None:
    """BUG4 residual (sphere_homology 2026-07-04, bit twice): the parent
    STUB was never marked `noncomputable` but the winning strategy decl
    IS — carrying only the stub's modifiers still writes a cold-broken
    alias with no cold backstop. The strategy decl is the authority for
    `noncomputable` (it is a property of the proof term); visibility
    modifiers remain the stub's choice."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_iso.lean"
    parent.write_text(
        "import Mathlib\n\nnamespace Problems.p\n\n"
        "def iso : SomeCat.Iso A B := by sorry\n\n"      # stub NOT marked
        "end Problems.p\n",
        encoding="utf-8")
    scratch_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "noncomputable def s77 : SomeCat.Iso A B := someConstruction\n"
        "end Problems.p\n")
    _promote_to_alias(
        parent,
        namespace="Problems.p", slug="iso", sid_token="s77",
        scratch_module="Problems.p.proofs._strategy_s77",
        scratch_text=scratch_text,
    )
    new = parent.read_text(encoding="utf-8")
    assert "noncomputable def iso := @Problems.p.s77" in new


def test_promote_to_alias_plain_theorem_stays_bare(tmp_path: Path) -> None:
    """A plain `theorem` parent (Prop goal) has no keyword modifier, so the
    re-export stays a bare `def <slug> := @<sid>` — the modifier carry must
    not spuriously prepend anything (guards the common case)."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_g.lean"
    parent.write_text(
        "import Mathlib\n\nnamespace Problems.p\n\n"
        "theorem g : True := by sorry\n\nend Problems.p\n",
        encoding="utf-8")
    _promote_to_alias(
        parent,
        namespace="Problems.p", slug="g", sid_token="s5",
        scratch_module="Problems.p.proofs._strategy_s5",
    )
    new = parent.read_text(encoding="utf-8")
    assert "def g := @Problems.p.s5" in new
    assert "noncomputable" not in new


def test_promote_to_alias_no_backup_when_parent_absent(tmp_path: Path) -> None:
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_new.lean"
    backup = _promote_to_alias(
        parent,
        namespace="Problems.p", slug="g", sid_token="s1",
        scratch_module="Problems.p.proofs._strategy_s1",
    )
    assert backup is None
    assert parent.exists()


def test_promote_to_alias_prepends_annotation_block(tmp_path: Path) -> None:
    """An `annotation` kwarg (already-formatted Lean line-comment block)
    is prepended verbatim before the imports. Comments are Lean-inert
    so this affects only what humans/agents see, not elaboration."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_g.lean"
    parent.write_text(
        "import Mathlib\nnamespace Problems.p\n\n"
        "theorem g : True := by sorry\n\nend Problems.p\n",
        encoding="utf-8")
    annotation = (
        "-- g: split via combinator on subgoal pair\n"
        "-- A is identity, B is metric bound\n"
    )
    _promote_to_alias(
        parent,
        namespace="Problems.p", slug="g", sid_token="s42",
        scratch_module="Problems.p.proofs._strategy_s42",
        annotation=annotation,
    )
    new = parent.read_text(encoding="utf-8")
    assert new.startswith(
        "-- g: split via combinator on subgoal pair\n"
        "-- A is identity, B is metric bound\n"
        "import Mathlib"
    )
    # Alias body still present after the annotation
    assert "def g := @Problems.p.s42" in new


def test_promote_to_alias_empty_annotation_is_noop(tmp_path: Path) -> None:
    """Default `annotation=""` matches the pre-Phase-2 behavior — no
    comment lines added, alias starts with imports."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_g.lean"
    parent.write_text(
        "import Mathlib\nnamespace Problems.p\n\n"
        "theorem g : True := by sorry\n\nend Problems.p\n",
        encoding="utf-8")
    _promote_to_alias(
        parent,
        namespace="Problems.p", slug="g", sid_token="s7",
        scratch_module="Problems.p.proofs._strategy_s7",
    )
    new = parent.read_text(encoding="utf-8")
    assert new.startswith("import Mathlib")


def test_promote_to_alias_idempotent(tmp_path: Path) -> None:
    """Re-promote of an already-aliased file produces same content with
    no doubled imports or doubled defs."""
    from Tooling.pipeline import _promote_to_alias
    parent = tmp_path / "L_g.lean"
    parent.write_text(
        "import Mathlib\nnamespace Problems.p\n\n"
        "theorem g : True := by sorry\n\nend Problems.p\n",
        encoding="utf-8")
    _promote_to_alias(
        parent, namespace="Problems.p", slug="g", sid_token="s5",
        scratch_module="Problems.p.proofs._strategy_s5")
    first = parent.read_text(encoding="utf-8")
    _promote_to_alias(
        parent, namespace="Problems.p", slug="g", sid_token="s5",
        scratch_module="Problems.p.proofs._strategy_s5")
    second = parent.read_text(encoding="utf-8")
    assert first == second
    assert second.count("import Problems.p.proofs._strategy_s5") == 1
    assert second.count("def g := @Problems.p.s5") == 1


def test_rollback_promote_restores_original(tmp_path: Path) -> None:
    from Tooling.pipeline import _promote_to_alias, _rollback_promote
    parent = tmp_path / "L_g.lean"
    original = (
        "import Mathlib\nnamespace Problems.p\n\n"
        "theorem g {x : Nat} : x = x := by sorry\n\nend Problems.p\n"
    )
    parent.write_text(original, encoding="utf-8")
    backup = _promote_to_alias(
        parent, namespace="Problems.p", slug="g", sid_token="s9",
        scratch_module="Problems.p.proofs._strategy_s9")
    assert "by sorry" not in parent.read_text(encoding="utf-8")
    _rollback_promote(parent, backup)
    assert parent.read_text(encoding="utf-8") == original
    assert backup is not None and not backup.exists()


def test_verify_backup_path_keyed_by_strategy_id(tmp_path: Path) -> None:
    """P0-#1: backup filename includes sid_token so concurrent
    Verifies on sibling strategies of the same parent goal don't
    clobber each other's backup."""
    from Tooling.pipeline import _verify_backup_path
    parent = tmp_path / "L_g.lean"
    parent.write_text("orig", encoding="utf-8")
    b10 = _verify_backup_path(parent, "s10")
    b11 = _verify_backup_path(parent, "s11")
    assert b10 != b11
    assert "s10" in b10.name
    assert "s11" in b11.name


def test_concurrent_promote_two_siblings_keeps_both_backups(
    tmp_path: Path,
) -> None:
    """Regression for the original race: two sibling strategies
    promoting the same parent_abs in sequence (or interleaved)
    must each keep their own backup so each can roll back to the
    PREVIOUS state — not to whatever the other sibling wrote.
    """
    from Tooling.pipeline import _promote_to_alias, _rollback_promote
    parent = tmp_path / "L_g.lean"
    original = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem g : True := by sorry\nend Problems.p\n"
    )
    parent.write_text(original, encoding="utf-8")
    # W1 promotes for s10
    b10 = _promote_to_alias(
        parent, namespace="Problems.p", slug="g", sid_token="s10",
        scratch_module="Problems.p.proofs._strategy_s10")
    after_w1 = parent.read_text(encoding="utf-8")
    assert b10 is not None and b10.exists()
    assert b10.read_text(encoding="utf-8") == original  # s10's backup IS orig
    # W2 promotes for s11 against the parent_abs W1 just rewrote
    b11 = _promote_to_alias(
        parent, namespace="Problems.p", slug="g", sid_token="s11",
        scratch_module="Problems.p.proofs._strategy_s11")
    assert b11 is not None and b11.exists()
    assert b11 != b10  # distinct files
    assert b11.read_text(encoding="utf-8") == after_w1  # not orig
    # Now simulate W2 fail → rollback. After rollback, parent_abs
    # should be W1's content (not lost). W1's own backup still
    # holds orig so W1 could still rollback if it later failed.
    _rollback_promote(parent, b11)
    assert parent.read_text(encoding="utf-8") == after_w1
    assert b10.exists() and b10.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------
# _safe_glob — survives Windows-reserved chars in sibling filenames
# ---------------------------------------------------------------------

def test_safe_glob_returns_pattern_matches(tmp_path: Path) -> None:
    """Plain happy path: behaves like Path.glob for ordinary names."""
    (tmp_path / "patch.lean").write_text("x", encoding="utf-8")
    (tmp_path / "new_s1_sub_1.lean").write_text("x", encoding="utf-8")
    (tmp_path / "PROPOSAL.md").write_text("x", encoding="utf-8")
    patches = _safe_glob(tmp_path, "patch*.lean")
    assert {p.name for p in patches} == {"patch.lean"}
    subs = _safe_glob(tmp_path, "new_*.lean")
    assert {p.name for p in subs} == {"new_s1_sub_1.lean"}


def test_safe_glob_skips_reserved_char_sibling(monkeypatch,
                                               tmp_path: Path) -> None:
    """A sibling whose name carries a Windows-reserved char (e.g. `?` from an
    agent confusing `exact?` for an identifier) must not crash the glob — the
    scenario `_safe_glob` exists for, and one that only bites on Windows. The
    previous test created a real `?`-named file, which Windows NTFS rejects, so
    it skipped on the one platform the bug occurs on. Simulate the scandir entry
    instead so the reserved-char branch runs everywhere; then, where the
    filesystem accepts the name (POSIX), repeat the check end-to-end."""
    import os
    import contextlib
    from types import SimpleNamespace

    entries = [
        SimpleNamespace(name="patch.lean", path=str(tmp_path / "patch.lean")),
        SimpleNamespace(name="won_exact?.lean",
                        path=str(tmp_path / "won_exact?.lean")),
    ]

    @contextlib.contextmanager
    def _fake_scandir(_directory):
        yield iter(entries)

    monkeypatch.setattr(os, "scandir", _fake_scandir)
    patches = _safe_glob(tmp_path, "patch*.lean")
    assert {p.name for p in patches} == {"patch.lean"}

    # End-to-end on a filesystem that accepts the name (POSIX). On Windows the
    # create raises and the simulated branch above is the whole coverage.
    monkeypatch.undo()
    (tmp_path / "patch.lean").write_text("x", encoding="utf-8")
    try:
        (tmp_path / "won_exact?.lean").write_text("x", encoding="utf-8")
    except OSError:
        return
    assert {p.name for p in _safe_glob(tmp_path, "patch*.lean")} == {"patch.lean"}


def test_safe_glob_returns_empty_on_missing_directory(tmp_path: Path) -> None:
    """Defensive — never raise, just return empty if the directory is
    gone (e.g. attempts_dir cleaned up between spawn and validation)."""
    assert _safe_glob(tmp_path / "does-not-exist", "*") == []


# ---------------------------------------------------------------------
# Sub-goal slug pattern (`_SLUG_RE`) — agent-picked descriptive ids
# ---------------------------------------------------------------------

def test_slug_re_accepts_descriptive_lowercase() -> None:
    from Tooling.pipeline.backward import _SLUG_RE
    assert _SLUG_RE.match("cross_sq_add_inner_sq")
    assert _SLUG_RE.match("a")
    assert _SLUG_RE.match("foo_2")
    assert _SLUG_RE.match("step1")


def test_slug_re_rejects_leading_digit_or_underscore() -> None:
    from Tooling.pipeline.backward import _SLUG_RE
    assert not _SLUG_RE.match("1bad")
    assert not _SLUG_RE.match("_leading_underscore")


def test_slug_re_rejects_uppercase_or_hyphen() -> None:
    from Tooling.pipeline.backward import _SLUG_RE
    assert not _SLUG_RE.match("CamelCase")
    assert not _SLUG_RE.match("kebab-case")
    assert not _SLUG_RE.match("foo bar")  # space


def test_slug_re_rejects_empty_or_punctuation() -> None:
    from Tooling.pipeline.backward import _SLUG_RE
    assert not _SLUG_RE.match("")
    assert not _SLUG_RE.match("foo.bar")
    assert not _SLUG_RE.match("foo/bar")


# ---------------------------------------------------------------------
# camelCase slug normalization (`_normalize_slug`, backlog #3)
# ---------------------------------------------------------------------

def test_normalize_slug_camelcase_to_snake() -> None:
    from Tooling.pipeline.backward import _normalize_slug, _SLUG_RE
    assert _normalize_slug("termIntegrableOn") == "term_integrable_on"
    assert _normalize_slug("tangentialTermIntegralZero") == \
        "tangential_term_integral_zero"
    # PascalCase (leading uppercase)
    assert _normalize_slug("HalfSpace") == "half_space"
    # acronym run → split before the final word's capital
    assert _normalize_slug("HalfSpaceFTCStep") == "half_space_ftc_step"
    # every normalized result must satisfy the gate
    for raw in ("termIntegrableOn", "HalfSpace", "HalfSpaceFTCStep"):
        assert _SLUG_RE.match(_normalize_slug(raw))


def test_normalize_slug_passes_through_valid_and_rejects_unfixable() -> None:
    from Tooling.pipeline.backward import _normalize_slug
    # already snake_case → unchanged (still a valid normalization)
    assert _normalize_slug("term_integrable_on") == "term_integrable_on"
    # not mechanically fixable (uppercase isn't the only problem) → None
    assert _normalize_slug("1bad") is None          # leading digit survives
    assert _normalize_slug("foo-bar") is None        # hyphen survives
    assert _normalize_slug("foo.bar") is None        # punctuation survives


# ---------------------------------------------------------------------
# Strategy skeleton — preserve parent decl modifiers (green #77/#78)
# ---------------------------------------------------------------------

def test_skeleton_preserves_noncomputable_modifier() -> None:
    """A `noncomputable def` parent's strategy skeleton keeps `noncomputable`,
    or the renamed `def s<id> := by sorry` stub compile-fails on 'mark it
    noncomputable' (agent_feedback green_theorem #77/#78)."""
    from Tooling.pipeline._skeleton import build_strategy_skeleton
    parent = ("import Mathlib\n\nnamespace P\n\n"
              "noncomputable def disk_rot (x : ℝ) : ℝ := by sorry\n\nend P\n")
    skel = build_strategy_skeleton(parent, parent_slug="disk_rot",
                                   sid_token="s99", namespace="P")
    assert skel is not None and "noncomputable def s99" in skel


def test_skeleton_plain_theorem_gets_no_modifier() -> None:
    from Tooling.pipeline._skeleton import build_strategy_skeleton
    parent = ("import Mathlib\n\nnamespace P\n\n"
              "theorem foo (n : ℕ) : n = n := by sorry\n\nend P\n")
    skel = build_strategy_skeleton(parent, parent_slug="foo",
                                   sid_token="s1", namespace="P")
    assert skel is not None and "theorem s1" in skel
    assert "noncomputable" not in skel


# ---------------------------------------------------------------------
# Slug-collision auto-suffix (`_resolve_slug_collisions`)
# ---------------------------------------------------------------------

def test_resolve_collisions_no_overlap_passes_through(tmp_path: Path) -> None:
    """No collision → resolved list mirrors input, rename_map empty."""
    from Tooling.pipeline.backward import _resolve_slug_collisions
    p1 = tmp_path / "new_alpha.lean"
    p2 = tmp_path / "new_beta.lean"
    sub_meta = [("alpha", p1), ("beta", p2)]
    resolved, rename_map = _resolve_slug_collisions(
        sub_meta, existing_slugs=set())
    assert resolved == [("alpha", "alpha", p1), ("beta", "beta", p2)]
    assert rename_map == {}


def test_resolve_collisions_appends_suffix_for_db_hit(
    tmp_path: Path,
) -> None:
    """Existing slug `foo` in DB → agent's `foo` becomes `foo_2`."""
    from Tooling.pipeline.backward import _resolve_slug_collisions
    p = tmp_path / "new_foo.lean"
    resolved, rename_map = _resolve_slug_collisions(
        [("foo", p)], existing_slugs={"foo"})
    assert resolved == [("foo", "foo_2", p)]
    assert rename_map == {"foo": "foo_2"}


def test_resolve_collisions_skips_taken_suffixes(tmp_path: Path) -> None:
    """`foo` and `foo_2` both taken → next free is `foo_3`."""
    from Tooling.pipeline.backward import _resolve_slug_collisions
    p = tmp_path / "new_foo.lean"
    resolved, rename_map = _resolve_slug_collisions(
        [("foo", p)], existing_slugs={"foo", "foo_2", "foo_3"})
    assert resolved == [("foo", "foo_4", p)]
    assert rename_map == {"foo": "foo_4"}


def test_resolve_collisions_within_batch_two_sub_goals(
    tmp_path: Path,
) -> None:
    """Two sub-goals in one batch both pick `foo` (filesystem-wise can't
    happen since two `new_foo.lean` writes overwrite, but the helper is
    defensive and handles it). Existing DB has `foo` already → first
    becomes `foo_2`, second becomes `foo_3`."""
    from Tooling.pipeline.backward import _resolve_slug_collisions
    p1 = tmp_path / "new_foo_a.lean"
    p2 = tmp_path / "new_foo_b.lean"
    resolved, rename_map = _resolve_slug_collisions(
        [("foo", p1), ("foo", p2)], existing_slugs={"foo"})
    assert resolved == [("foo", "foo_2", p1), ("foo", "foo_3", p2)]
    assert rename_map == {"foo": "foo_3"}  # last wins; both renames


def test_resolve_collisions_partial_collision_only_renames_overlap(
    tmp_path: Path,
) -> None:
    """One slug collides, the other doesn't — only the overlapping one
    gets a suffix. The non-colliding slug stays untouched."""
    from Tooling.pipeline.backward import _resolve_slug_collisions
    p1 = tmp_path / "new_taken.lean"
    p2 = tmp_path / "new_free.lean"
    resolved, rename_map = _resolve_slug_collisions(
        [("taken", p1), ("free", p2)], existing_slugs={"taken"})
    assert resolved == [("taken", "taken_2", p1), ("free", "free", p2)]
    assert rename_map == {"taken": "taken_2"}


# ---------------------------------------------------------------------
# Leading comment extraction (`_extract_leading_comments`) — Phase 6
# ---------------------------------------------------------------------

def test_extract_leading_comments_basic() -> None:
    src = (
        "-- foo: summary\n"
        "-- detail line\n"
        "import Mathlib\n"
        "theorem foo : True := trivial\n"
    )
    assert _extract_leading_comments(src) == (
        "-- foo: summary\n-- detail line\n"
    )


def test_extract_leading_comments_preserves_internal_blanks() -> None:
    src = (
        "-- foo: summary\n"
        "--\n"
        "-- ## Strategy\n"
        "-- We split into ...\n"
        "import Mathlib\n"
    )
    out = _extract_leading_comments(src)
    assert "-- ## Strategy" in out
    assert out.count("--\n") >= 1  # the bare `--` separator survives


def test_extract_leading_comments_captures_mathlib_doc_placement() -> None:
    """Agents commonly write the doc comment immediately above the
    theorem (after `namespace ...`), Mathlib-style — not at file top.
    The parser must catch both placements."""
    src = (
        "import Mathlib\n"
        "import Problems.p.Defs\n"
        "\n"
        "namespace Problems.p\n"
        "\n"
        "-- foo: summary\n"
        "-- detail line\n"
        "theorem foo : True := trivial\n"
        "\n"
        "end Problems.p\n"
    )
    out = _extract_leading_comments(src)
    assert out == "-- foo: summary\n-- detail line\n"


def test_extract_leading_comments_combines_top_and_doc_placements() -> None:
    """If an agent writes comments in BOTH positions (file top + just
    above the theorem), parser captures all of them in source order.
    Boilerplate (imports, namespace) and pure blanks in between are
    skipped silently."""
    src = (
        "-- file-top context note\n"
        "import Mathlib\n"
        "\n"
        "namespace Problems.p\n"
        "\n"
        "-- foo: summary right above the theorem\n"
        "theorem foo : True := trivial\n"
    )
    out = _extract_leading_comments(src)
    assert "-- file-top context note" in out
    assert "-- foo: summary right above the theorem" in out


def test_extract_leading_comments_ignores_inline_comments_inside_proof() -> None:
    """Comments INSIDE the proof body (after the `theorem` keyword) are
    not part of the annotation — the parser stops at the theorem."""
    src = (
        "-- legit annotation\n"
        "theorem foo : True := by\n"
        "  -- step 1: trivial closes it\n"
        "  trivial\n"
    )
    out = _extract_leading_comments(src)
    assert "-- legit annotation\n" in out
    assert "step 1" not in out


def test_extract_leading_comments_empty_when_no_comment_before_theorem() -> None:
    """No `--` lines anywhere before the first theorem → empty result."""
    src = "import Mathlib\nnamespace Problems.p\ntheorem foo : True := trivial\n"
    assert _extract_leading_comments(src) == ""


def test_extract_leading_comments_skips_leading_blank_lines() -> None:
    src = "\n\n-- foo: summary\nimport Mathlib\n"
    assert _extract_leading_comments(src) == "-- foo: summary\n"


# ---------------------------------------------------------------------
# Decline directive parsing (`_extract_decline_reason`) — Phase 6
# ---------------------------------------------------------------------

def test_extract_decline_too_hard() -> None:
    block = (
        "-- decline: too_hard\n"
        "-- Direct tactics don't converge; needs Backward.\n"
    )
    assert _extract_decline_reason(block) == "too_hard"


def test_extract_decline_parent_type_infeasible() -> None:
    block = (
        "-- decline: parent_type_infeasible\n"
        "-- ## Counterexample\n"
        "-- With s=(0,0) ...\n"
    )
    assert _extract_decline_reason(block) == "parent_type_infeasible"


def test_extract_decline_returns_none_for_non_decline() -> None:
    block = "-- foo: summary line\n-- detail\n"
    assert _extract_decline_reason(block) is None


def test_extract_decline_returns_none_for_empty() -> None:
    assert _extract_decline_reason("") is None


def test_extract_decline_tolerates_whitespace_around_directive() -> None:
    block = "--   decline:  too_hard  \n"
    assert _extract_decline_reason(block) == "too_hard"
