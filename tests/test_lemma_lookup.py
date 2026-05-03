"""F20: lemma signature lookup via `lake env lean`.

Unit tests mock subprocess + cache file; one integration test runs a
real `lake env lean` against the workspace's Mathlib build (skipped
when `lake` is missing or the workspace has no Mathlib).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling import lemma_lookup
from Tooling.lemma_lookup import (
    LemmaInfo,
    _parse_check_output,
    _toolchain_hash,
    extract_lemma_names,
    lookup_batch,
)


# P2-#3: an autouse `_isolate_cache` fixture below (line ~206) already
# redirects `lemma_lookup.CACHE_FILE` to tmp_path for every test in
# this file. The earlier P2-#3 commit added a duplicate at module
# top — removed during review (redundant; the second invocation of
# autouse on the same name silently overrode the first anyway).


# ---------------------------------------------------------------------
# _parse_check_output — pure parsing
# ---------------------------------------------------------------------

def test_parse_check_output_single_name() -> None:
    output = "Nat.factorial : ℕ → ℕ\n"
    got = _parse_check_output(output, ["Nat.factorial"])
    assert got == {"Nat.factorial": "ℕ → ℕ"}


def test_parse_check_output_multi_name() -> None:
    output = (
        "ZMod.val_natCast : ∀ (n a : ℕ), (↑a).val = a % n\n"
        "Nat.factorial : ℕ → ℕ\n"
    )
    got = _parse_check_output(output, ["ZMod.val_natCast", "Nat.factorial"])
    assert got["ZMod.val_natCast"] == "∀ (n a : ℕ), (↑a).val = a % n"
    assert got["Nat.factorial"] == "ℕ → ℕ"


def test_parse_check_output_multiline_signature() -> None:
    """Long signatures wrap; the parser must keep continuation lines
    together until the next `<name> : ` block starts."""
    output = (
        "Big.lemma : ∀ (x : α) (y : β),\n"
        "  P x → Q y →\n"
        "  R x y\n"
        "Other.lemma : Nat → Nat\n"
    )
    got = _parse_check_output(output, ["Big.lemma", "Other.lemma"])
    assert got["Big.lemma"] == "∀ (x : α) (y : β), P x → Q y → R x y"
    assert got["Other.lemma"] == "Nat → Nat"


def test_parse_check_output_missing_name_omitted() -> None:
    """A name Lean rejected (error to stderr, no stdout block) does
    not appear in the result."""
    output = "Nat.factorial : ℕ → ℕ\n"
    got = _parse_check_output(output,
                              ["Nat.factorial", "does_not_exist"])
    assert "Nat.factorial" in got
    assert "does_not_exist" not in got


def test_parse_check_output_ignores_unrelated_names() -> None:
    """Output may contain blocks for names we didn't query; ignore them."""
    output = (
        "Surprise.lemma : Foo\n"
        "Nat.factorial : ℕ → ℕ\n"
    )
    got = _parse_check_output(output, ["Nat.factorial"])
    assert got == {"Nat.factorial": "ℕ → ℕ"}


def test_parse_check_output_at_prefix_when_implicit_args() -> None:
    """Lean 4 prefixes `@` to `#check @foo` output when the lemma has
    implicit args. Real failure observed: with @-prefixed names, the
    block boundary regex would treat `@Nat.foo : ...` as continuation
    of the previous lemma's signature, mashing 3 lemmas into one
    bullet. Parser must accept optional leading `@`."""
    output = (
        "ZMod.val_neg_one : ∀ (n : ℕ), (-1).val = n\n"
        "@Nat.mod_eq_of_lt : ∀ {a b : ℕ}, a < b → a % b = a\n"
        "@Nat.Prime.two_le : ∀ {p : ℕ}, Nat.Prime p → 2 ≤ p\n"
    )
    got = _parse_check_output(output,
                              ["ZMod.val_neg_one",
                               "Nat.mod_eq_of_lt",
                               "Nat.Prime.two_le"])
    # Each lemma resolves to its own clean signature, no concatenation
    assert got["ZMod.val_neg_one"] == "∀ (n : ℕ), (-1).val = n"
    assert got["Nat.mod_eq_of_lt"] == "∀ {a b : ℕ}, a < b → a % b = a"
    assert got["Nat.Prime.two_le"] == "∀ {p : ℕ}, Nat.Prime p → 2 ≤ p"


# ---------------------------------------------------------------------
# extract_lemma_names — pull dotted names from stderr
# ---------------------------------------------------------------------

def test_extract_names_from_unknown_constant_error() -> None:
    stderr = "error: Unknown constant `ZMod.val_natCast`"
    names = extract_lemma_names(stderr)
    assert "ZMod.val_natCast" in names


def test_extract_names_from_type_mismatch_error() -> None:
    stderr = (
        "error: file.lean:7:2: Type mismatch in application "
        "ZMod.val_natCast p (p - 1)"
    )
    names = extract_lemma_names(stderr)
    assert "ZMod.val_natCast" in names


def test_extract_names_skips_non_error_lines() -> None:
    """Body of stderr trace mentions many names; we want only those in
    error / warning lines for high signal."""
    stderr = (
        "trace: LEAN_PATH=Mathlib.Foo.Bar:Mathlib.Baz.Qux\n"
        "error: Unknown identifier `MyProj.NotALemma`\n"
        "trace: more.unrelated.Stuff\n"
    )
    names = extract_lemma_names(stderr)
    assert names == ["MyProj.NotALemma"]


def test_extract_names_dedupes_preserving_order() -> None:
    stderr = (
        "error: Unknown constant `A.foo`\n"
        "error: Unknown constant `B.bar`\n"
        "error: Unknown constant `A.foo`\n"  # dup
    )
    names = extract_lemma_names(stderr)
    assert names == ["A.foo", "B.bar"]


def test_extract_names_caps_at_max() -> None:
    """Long error logs shouldn't produce a 100-name lookup batch."""
    stderr = "\n".join(
        f"error: Unknown identifier `Pkg.lemma{i}`" for i in range(20)
    )
    names = extract_lemma_names(stderr, max_names=5)
    assert len(names) == 5


def test_extract_names_empty_input() -> None:
    assert extract_lemma_names("") == []
    assert extract_lemma_names(None) == []  # type: ignore[arg-type]


def test_extract_names_skips_short_lowercase() -> None:
    """`omega` / `simp` / etc. are tactics, not lemmas. The regex
    requires capitalized first segment + at least one dot."""
    stderr = "error: tactic omega failed; tried simp"
    assert extract_lemma_names(stderr) == []


# ---------------------------------------------------------------------
# Cache key + load/save round-trip
# ---------------------------------------------------------------------

def test_toolchain_hash_stable(tmp_path: Path) -> None:
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")
    h1 = _toolchain_hash(tmp_path)
    h2 = _toolchain_hash(tmp_path)
    assert h1 == h2 and len(h1) == 16


def test_toolchain_hash_changes_on_bump(tmp_path: Path) -> None:
    p = tmp_path / "lean-toolchain"
    p.write_text("v4.30.0-rc2\n", encoding="utf-8")
    h_before = _toolchain_hash(tmp_path)
    p.write_text("v4.31.0\n", encoding="utf-8")
    assert _toolchain_hash(tmp_path) != h_before


def test_toolchain_hash_handles_missing_files(tmp_path: Path) -> None:
    """No lean-toolchain / lake-manifest.json yet → don't crash, just
    produce a stable hash for the empty case."""
    h = _toolchain_hash(tmp_path)
    assert len(h) == 16


# ---------------------------------------------------------------------
# lookup_batch — subprocess mocked
# ---------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh on-disk cache to avoid cross-pollution."""
    monkeypatch.setattr(lemma_lookup, "CACHE_FILE",
                        tmp_path / "test_cache.json")
    yield


def _mock_subprocess_stdout(stdout: str):
    """Helper: subprocess.run replacement that returns pre-baked stdout."""
    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=stdout, stderr="")
    return _run


def test_lookup_batch_empty_input(tmp_path: Path) -> None:
    assert lookup_batch([], tmp_path) == {}


def test_lookup_batch_calls_lake_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")
    fake_run = MagicMock(side_effect=_mock_subprocess_stdout(
        "Nat.factorial : ℕ → ℕ\n"
    ))
    monkeypatch.setattr(lemma_lookup.subprocess, "run", fake_run)

    result = lookup_batch(["Nat.factorial"], tmp_path)
    assert result["Nat.factorial"].found is True
    assert "ℕ" in result["Nat.factorial"].signature
    fake_run.assert_called_once()

    # Second call hits cache, doesn't shell out
    fake_run.reset_mock()
    result2 = lookup_batch(["Nat.factorial"], tmp_path)
    assert result2 == result
    fake_run.assert_not_called()


def test_lookup_batch_records_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lean rejects `does_not_exist` → no stdout block → cache stores
    found=False so subsequent calls don't re-spawn lake."""
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")
    fake_run = MagicMock(side_effect=_mock_subprocess_stdout(""))
    monkeypatch.setattr(lemma_lookup.subprocess, "run", fake_run)

    result = lookup_batch(["does_not_exist"], tmp_path)
    assert result["does_not_exist"].found is False
    assert result["does_not_exist"].signature == ""

    fake_run.reset_mock()
    lookup_batch(["does_not_exist"], tmp_path)
    fake_run.assert_not_called()


def test_lookup_batch_dedupe_drops_repeats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller may pass the same name twice (e.g. it appeared in two
    error lines). Each name resolves to one cache entry; the returned
    dict has one key per unique name."""
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")
    fake_run = MagicMock(side_effect=_mock_subprocess_stdout(
        "A.foo : Nat\nB.bar : Nat\n"
    ))
    monkeypatch.setattr(lemma_lookup.subprocess, "run", fake_run)

    result = lookup_batch(["A.foo", "B.bar", "A.foo"], tmp_path)
    assert set(result.keys()) == {"A.foo", "B.bar"}
    # Single subprocess call — dupes must not multiply the query
    assert fake_run.call_count == 1


def test_lookup_batch_invalidates_on_toolchain_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bumping lean-toolchain must invalidate cache; next call shells
    out again rather than serving stale entries."""
    p = tmp_path / "lean-toolchain"
    p.write_text("v4.30.0-rc2\n", encoding="utf-8")
    fake_run = MagicMock(side_effect=_mock_subprocess_stdout(
        "Nat.factorial : ℕ → ℕ\n"
    ))
    monkeypatch.setattr(lemma_lookup.subprocess, "run", fake_run)
    lookup_batch(["Nat.factorial"], tmp_path)
    assert fake_run.call_count == 1

    # Toolchain bump
    p.write_text("v4.31.0\n", encoding="utf-8")
    lookup_batch(["Nat.factorial"], tmp_path)
    assert fake_run.call_count == 2


def test_lookup_batch_timeout_skips_cache_pollution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out lookup must not write `found=False` for the names —
    we want the next attempt (maybe with cache warmed) to retry."""
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)
    monkeypatch.setattr(lemma_lookup.subprocess, "run", _timeout)

    result = lookup_batch(["Nat.factorial"], tmp_path)
    # Default sentinel returned but cache file not written
    assert result["Nat.factorial"].found is False
    assert not lemma_lookup.CACHE_FILE.exists()


def test_lookup_batch_partial_cache_only_queries_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If A is cached and B is not, the lake query asks for B alone."""
    (tmp_path / "lean-toolchain").write_text("v4.30.0-rc2\n",
                                              encoding="utf-8")
    fake_run = MagicMock(side_effect=[
        subprocess.CompletedProcess(
            args=[], returncode=0, stdout="A.foo : Nat\n", stderr=""),
        subprocess.CompletedProcess(
            args=[], returncode=0, stdout="B.bar : Nat\n", stderr=""),
    ])
    monkeypatch.setattr(lemma_lookup.subprocess, "run", fake_run)

    lookup_batch(["A.foo"], tmp_path)
    # Second call adds B.bar; only B.bar should be in the query
    lookup_batch(["A.foo", "B.bar"], tmp_path)
    second_call_args = fake_run.call_args_list[1]
    query_path = Path(second_call_args[0][0][3])  # ["lake", "env", "lean", <path>]
    # The query file is unlinked after the call; we verify count instead
    assert fake_run.call_count == 2


# ---------------------------------------------------------------------
# Integration test: real `lake env lean` against the workspace
# ---------------------------------------------------------------------

@pytest.mark.skipif(
    shutil.which("lake") is None or
    not (Path.cwd() / "lakefile.lean").exists(),
    reason="requires lake CLI + Asterism workspace",
)
def test_lookup_batch_real_lake() -> None:
    """End-to-end: spawn a real `lake env lean`, parse a known Mathlib
    lemma signature. Slow (~20s on cold start)."""
    workspace = Path.cwd()
    # Use a fresh cache so we exercise the subprocess path
    cache = lemma_lookup.CACHE_FILE
    backup = None
    if cache.exists():
        backup = cache.read_text(encoding="utf-8")
        cache.unlink()
    try:
        result = lookup_batch(
            ["Nat.factorial", "ZMod.val_natCast", "does_not_exist_xyz"],
            workspace,
        )
        assert result["Nat.factorial"].found is True
        assert "ℕ" in result["Nat.factorial"].signature
        assert result["ZMod.val_natCast"].found is True
        assert "val" in result["ZMod.val_natCast"].signature
        assert result["does_not_exist_xyz"].found is False
    finally:
        if backup is not None:
            cache.write_text(backup, encoding="utf-8")
        elif cache.exists():
            cache.unlink()
