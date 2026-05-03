"""Pure functions in pipeline.py — no DB, no filesystem (mostly)."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline import (
    _is_sorry_stub,
    _replace_proof_body,
    _grep_forbidden,
    _extract_statement,
    _lean_path_to_module,
    _slug_from_filename,
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
# F17 — auto-inject `import Mathlib` when lemma file lacks any import
# ---------------------------------------------------------------------

def test_ensure_import_mathlib_prepends_when_no_imports() -> None:
    """Haiku-style output: no import line at all. Must be patched."""
    from Tooling.pipeline import _ensure_import_mathlib
    src = (
        "namespace Problems.x\n\n"
        "theorem foo : Nat.factorial 1 % 2 = 1 := by sorry\n\n"
        "end Problems.x\n"
    )
    out = _ensure_import_mathlib(src)
    assert out.startswith("import Mathlib\n")
    assert "namespace Problems.x" in out


def test_ensure_import_mathlib_passthrough_when_specific_import() -> None:
    """Model intentionally chose a specific import — leave it alone."""
    from Tooling.pipeline import _ensure_import_mathlib
    src = (
        "import Mathlib.Data.Nat.Factorial.Basic\n\n"
        "namespace Problems.x\n"
        "theorem foo : True := trivial\n"
        "end Problems.x\n"
    )
    assert _ensure_import_mathlib(src) == src


def test_ensure_import_mathlib_passthrough_when_umbrella_already() -> None:
    """Already has `import Mathlib`: don't double-inject."""
    from Tooling.pipeline import _ensure_import_mathlib
    src = "import Mathlib\n\nnamespace X\nend X\n"
    assert _ensure_import_mathlib(src) == src


def test_ensure_import_mathlib_anchored_to_line_start() -> None:
    """`import` appearing inside a comment is not a real import — the
    regex anchors `^import\\s` to start-of-line via re.MULTILINE."""
    from Tooling.pipeline import _ensure_import_mathlib
    src = (
        "-- this comment mentions import Mathlib but isn't a directive\n"
        "namespace X\n"
        "theorem t : True := trivial\n"
        "end X\n"
    )
    out = _ensure_import_mathlib(src)
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
# F34 — TACTIC_TRY_LIST contains the expected fast-path closers
# ---------------------------------------------------------------------

def test_tactic_try_list_contains_existing_closers() -> None:
    """Original 10 tactics still present (regression guard)."""
    from Tooling.pipeline import TACTIC_TRY_LIST
    for t in ["rfl", "simp", "decide", "trivial", "omega",
              "linarith", "nlinarith", "norm_num", "simp_all", "aesop"]:
        assert t in TACTIC_TRY_LIST, f"missing {t!r}"


def test_tactic_try_list_contains_new_domain_closers() -> None:
    """F34 additions for cast / algebraic / positivity / decision."""
    from Tooling.pipeline import TACTIC_TRY_LIST
    for t in ["norm_cast", "push_cast", "ring", "ring_nf",
              "field_simp", "positivity", "grind"]:
        assert t in TACTIC_TRY_LIST, f"missing {t!r}"


def test_tactic_try_list_orders_cheap_before_heavy() -> None:
    """Cheap tactics (rfl, decide) must precede heavy search (aesop,
    grind) so the fast-path bails on the first hit before paying
    the search-tactic startup."""
    from Tooling.pipeline import TACTIC_TRY_LIST
    rfl_idx = TACTIC_TRY_LIST.index("rfl")
    aesop_idx = TACTIC_TRY_LIST.index("aesop")
    grind_idx = TACTIC_TRY_LIST.index("grind")
    assert rfl_idx < aesop_idx
    assert rfl_idx < grind_idx


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


def test_signature_prefix_missing_returns_empty() -> None:
    from Tooling.pipeline import _signature_prefix
    assert _signature_prefix("def foo := 0", "foo") == ""


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
    `def g := @ns.s5`, there's no `theorem g` to copy from."""
    from Tooling.pipeline import _build_strategy_skeleton
    parent = (
        "import Mathlib\nnamespace Problems.p\n\n"
        "def g := @Problems.p.s5\n\n"
        "end Problems.p\n"
    )
    sk = _build_strategy_skeleton(
        parent, parent_slug="g", sid_token="s9", namespace="Problems.p")
    assert sk is None


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
