"""manifest.parse — best-effort YAML frontmatter + markdown sections."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.state import manifest


def write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_full_manifest(tmp_path: Path) -> None:
    p = write(tmp_path / "wilson", "Manifest.md", """---
problem: wilson
axioms_whitelist:
  - propext
  - Quot.sound
forbidden_lemmas: [ZMod.wilsons_lemma]
---

# wilson

## Statement
∀ p : ℕ, p.Prime → True

## Entry kind
Backward

## Mathlib hints
- ZMod.val_natCast
- ZMod.val_neg_one

## Strategic notes
free-form text
""")
    m = manifest.parse(p)
    assert m.problem == "wilson"
    assert m.statement == "∀ p : ℕ, p.Prime → True"
    assert not hasattr(m, "entry_kind")  # Phase 2: field removed
    assert m.axioms_whitelist == ["propext", "Quot.sound"]
    assert m.forbidden_lemmas == ["ZMod.wilsons_lemma"]
    assert not hasattr(m, "mathlib_hints")  # retired 2026-07-08
    assert "free-form" in m.strategic_notes


def test_legacy_entry_kind_section_is_silently_ignored(tmp_path: Path) -> None:
    """Phase 2 removed `## Entry kind` from Manifest. Legacy Manifests
    carrying the section are silently tolerated — no parser warning, no
    attribute on the returned object. Strategist now handles initial
    routing via problems.bootstrap_done."""
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---

## Statement
T

## Entry kind
Builder
""")
    m = manifest.parse(p)
    assert m.statement == "T"
    assert not hasattr(m, "entry_kind")


def test_missing_statement_is_silent(tmp_path: Path, capsys) -> None:
    """`## Statement` section is now optional (canonical statement lives
    in Root.lean's theorem signature). Missing section → empty field,
    no warning."""
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---
""")
    m = manifest.parse(p)
    assert m.statement == ""
    err = capsys.readouterr().err
    assert "missing ## Statement" not in err


def test_problem_falls_back_to_dirname(tmp_path: Path) -> None:
    p = write(tmp_path / "wilson", "Manifest.md", """## Statement
T
""")
    m = manifest.parse(p)
    assert m.problem == "wilson"


def test_inline_list_with_quotes(tmp_path: Path) -> None:
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
axioms_whitelist: ['propext', "Quot.sound"]
---

## Statement
T
""")
    m = manifest.parse(p)
    assert m.axioms_whitelist == ["propext", "Quot.sound"]


# ---------------------------------------------------------------------
# defs_opens + inject_defs_opens — Defs.lean `open` propagation.
# These helpers exist because Lean 4 `import` does NOT propagate `open`
# clauses across files. Without framework-managed injection, every
# agent-authored .lean would have to remember to replay the opens
# itself — a fragile dependency that caused the four miniF2F-Valid
# mid-run repairs (aime_1997_p11, imo_1965_p1, imo_1966_p4,
# imo_1962_p4) in pilot v5.
# ---------------------------------------------------------------------


def _make_problem_dir(tmp_path: Path, problem: str,
                      defs_opens_lines: list[str]) -> Path:
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    body = "import Mathlib\n\n"
    for line in defs_opens_lines:
        body += f"open {line}\n"
    body += f"\nnamespace Problems.{problem}\n\nend Problems.{problem}\n"
    (pdir / "Defs.lean").write_text(body, encoding="utf-8")
    return pdir


def test_defs_opens_returns_top_level_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat", "Topology"])
    assert manifest.defs_opens(tmp_path, "wilson") == [
        "BigOperators Real Nat", "Topology",
    ]


def test_defs_opens_returns_empty_when_no_defs(tmp_path: Path) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    assert manifest.defs_opens(tmp_path, "wilson") == []


def test_defs_opens_skips_scope_limited_opens(tmp_path: Path) -> None:
    pdir = tmp_path / "Problems" / "wilson"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\n"
        "open Real\n"           # top-level → propagate
        "open Topology in\n"    # scope-limited → DO NOT propagate
        "theorem helper : True := trivial\n",
        encoding="utf-8",
    )
    assert manifest.defs_opens(tmp_path, "wilson") == ["Real"]


def test_inject_defs_opens_adds_missing_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat Topology Rat"])
    content = (
        "import Mathlib\n"
        "import Problems.wilson.Defs\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n\n"
        "end Problems.wilson\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    assert "open BigOperators Real Nat Topology Rat" in out
    assert "import Problems.wilson.Defs" in out
    # Open block should sit between imports and namespace.
    idx_import = out.index("import Problems.wilson.Defs")
    idx_open = out.index("open BigOperators")
    idx_ns = out.index("namespace Problems.wilson")
    assert idx_import < idx_open < idx_ns


def test_inject_defs_opens_idempotent(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson", ["Real"])
    content = (
        "import Mathlib\n\n"
        "open Real\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    # No new open should be inserted; content unchanged.
    assert out == content
    assert out.count("open Real") == 1


def test_inject_defs_opens_no_defs_returns_unchanged(
    tmp_path: Path,
) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    content = "import Mathlib\n\nnamespace Problems.wilson\n\nend\n"
    assert manifest.inject_defs_opens(content, problem="wilson",
                                      workspace=tmp_path) == content


def test_inject_defs_opens_preserves_existing_subset(
    tmp_path: Path,
) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators", "Real Nat Topology"])
    content = (
        "import Mathlib\n\n"
        "open BigOperators\n\n"  # already has this one
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    # `BigOperators` already present → no duplicate; `Real Nat Topology` added.
    assert out.count("open BigOperators") == 1
    assert "open Real Nat Topology" in out


# ---------------------------------------------------------------------
# ManifestCache — hot-reload on mtime change
# ---------------------------------------------------------------------

import os
import time as _time


def _write_manifest(path: Path, statement: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nproblem: p\n---\n\n## Statement\n" + statement + "\n",
        encoding="utf-8",
    )


def test_manifest_cache_hot_reload_on_mtime_change(tmp_path: Path) -> None:
    """User edits Manifest.md mid-run → next `cache[problem]` access
    re-parses and returns the new content. Pre-fix the daemon cached
    the startup parse; user edits were ignored until restart."""
    mpath = tmp_path / "Problems" / "p" / "Manifest.md"
    _write_manifest(mpath, "T_original")
    cache = manifest.ManifestCache(tmp_path)
    cache.load("p", "Problems/p/Manifest.md")
    assert cache["p"].statement == "T_original"

    # Edit + bump mtime explicitly (filesystems may not see sub-second
    # changes between successive writes; setting +2s guarantees stat
    # picks up the change without sleeping the test runner).
    _write_manifest(mpath, "T_edited")
    new_mtime = _time.time() + 2
    os.utime(mpath, (new_mtime, new_mtime))

    fresh = cache["p"]
    assert fresh.statement == "T_edited"


def test_manifest_cache_returns_cached_when_mtime_unchanged(
    tmp_path: Path,
) -> None:
    """No edit → no re-parse. Avoids per-spawn filesystem reads of the
    full Manifest body when nothing has changed."""
    mpath = tmp_path / "Problems" / "p" / "Manifest.md"
    _write_manifest(mpath, "T_stable")
    cache = manifest.ManifestCache(tmp_path)
    first = cache.load("p", "Problems/p/Manifest.md")
    second = cache["p"]
    # Same object identity — no re-parse, returned the cached instance.
    assert first is second


def test_manifest_cache_keeps_prior_when_reparse_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture,
) -> None:
    """If a mid-run edit introduces malformed YAML / sections that
    `parse` raises on, the cache logs the failure and keeps the prior
    successful parse. Daemon does not crash. mtime advances so we
    don't retry-fail every subsequent access."""
    mpath = tmp_path / "Problems" / "p" / "Manifest.md"
    _write_manifest(mpath, "T_good")
    cache = manifest.ManifestCache(tmp_path)
    cache.load("p", "Problems/p/Manifest.md")

    # Overwrite with content that breaks parse — _parse_frontmatter
    # tolerates many shapes; force a real Exception by deleting the
    # file so parse's read_text raises FileNotFoundError.
    mpath.unlink()
    new_mtime = _time.time() + 2
    # Recreate as a directory at the same path so stat() succeeds with
    # changed mtime but parse fails on read_text.
    placeholder = mpath.parent / "_placeholder"
    placeholder.write_text("x", encoding="utf-8")
    os.utime(placeholder, (new_mtime, new_mtime))
    # Simulate the file being replaced with a broken one by writing
    # then making it unreadable. Simpler: just point at a missing file
    # via the cache's resolved path.
    # Instead exercise the recovery: re-create with valid content but
    # bad YAML that breaks downstream parse expectations.
    _write_manifest(mpath, "T_replaced")
    os.utime(mpath, (new_mtime, new_mtime))
    # Monkeypatch parse to raise once to simulate transient parse fail.
    real_parse = manifest.parse
    calls = {"n": 0}
    def flaky_parse(p):
        calls["n"] += 1
        raise ValueError("simulated parse failure")
    # Use a private attribute swap.
    manifest.parse = flaky_parse  # type: ignore[assignment]
    try:
        out = cache["p"]
    finally:
        manifest.parse = real_parse  # type: ignore[assignment]
    # Returned the pre-edit cached manifest (T_good).
    assert out.statement == "T_good"
    captured = capsys.readouterr()
    assert "manifest-reload" in captured.out
    assert "parse failed" in captured.out


def test_manifest_cache_dict_compat(tmp_path: Path) -> None:
    """Quack-compatible with dict[str, Manifest] for the operations
    framework uses elsewhere (brief.write_for_all_problems iterates;
    dispatcher does `problem in manifests` guards)."""
    mpath_a = tmp_path / "Problems" / "a" / "Manifest.md"
    mpath_b = tmp_path / "Problems" / "b" / "Manifest.md"
    _write_manifest(mpath_a, "T_a")
    _write_manifest(mpath_b, "T_b")
    # Adjust problem name per loaded entry.
    mpath_a.write_text(
        "---\nproblem: a\n---\n\n## Statement\nT_a\n", encoding="utf-8")
    mpath_b.write_text(
        "---\nproblem: b\n---\n\n## Statement\nT_b\n", encoding="utf-8")
    cache = manifest.ManifestCache(tmp_path)
    cache.load("a", "Problems/a/Manifest.md")
    cache.load("b", "Problems/b/Manifest.md")
    assert "a" in cache
    assert "missing" not in cache
    assert len(cache) == 2
    assert set(cache) == {"a", "b"}
    assert sorted(cache.keys()) == ["a", "b"]
    items = dict(cache.items())
    assert items["a"].statement == "T_a"


def test_library_flag_true(tmp_path: Path) -> None:
    """`library: true` opts the Problem into Library-ization (M0)."""
    mfst = manifest.parse(write(tmp_path, "Manifest.md", """---
problem: optin
library: true
---
# optin

## Statement
True
"""))
    assert mfst.library is True


def test_library_flag_absent_defaults_false(tmp_path: Path) -> None:
    """Missing `library:` -> False (conservative: never auto-promote)."""
    mfst = manifest.parse(write(tmp_path, "Manifest.md", """---
problem: noflag
---
# noflag

## Statement
True
"""))
    assert mfst.library is False


def test_library_flag_explicit_false(tmp_path: Path) -> None:
    mfst = manifest.parse(write(tmp_path, "Manifest.md", """---
problem: optout
library: false
---
# optout

## Statement
True
"""))
    assert mfst.library is False


def test_library_flag_garbage_is_false(tmp_path: Path) -> None:
    """Unparseable value -> False, not a crash (typo must not opt in)."""
    mfst = manifest.parse(write(tmp_path, "Manifest.md", """---
problem: typo
library: maybe?
---
# typo

## Statement
True
"""))
    assert mfst.library is False


def test_signoff_flag_inverse_polarity(tmp_path: Path) -> None:
    """`signoff` is opt-OUT of the human gate: absent -> True, garbage
    -> True (a typo must pause, never skip sign-off), only an explicit
    false/no/0 opts out."""
    def parse_with(header_line: str) -> manifest.Manifest:
        return manifest.parse(write(tmp_path, "Manifest.md", f"""---
problem: sg
{header_line}
---
# sg

## Statement
True
"""))
    assert parse_with("library: false").signoff is True   # absent
    assert parse_with("signoff: maybe?").signoff is True  # garble → pause
    assert parse_with("signoff: FALSE").signoff is False
    assert parse_with("signoff: no").signoff is False
    assert parse_with("signoff: true").signoff is True


def test_library_flag_case_insensitive(tmp_path: Path) -> None:
    mfst = manifest.parse(write(tmp_path, "Manifest.md", """---
problem: caps
library: True
---
# caps

## Statement
True
"""))
    assert mfst.library is True


# ---------------------------------------------------------------------
# effective_axioms — THE whitelist derivation every gate consumes
# (2026-07-04 convention audit, finding 3: the empty-field semantics were
# re-decided at ≥6 call sites with three different meanings).
# ---------------------------------------------------------------------

def test_effective_axioms_set_field_passes_through() -> None:
    m = manifest.Manifest(problem="p", statement="s",
                          axioms_whitelist=["propext", "Custom.ax"])
    assert manifest.effective_axioms(m) == ["propext", "Custom.ax"]


def test_effective_axioms_strips_sorryAx() -> None:
    """Whitelist-edition sorryAx tripwire (self-audit 2026-07-12 §3-1c):
    no configuration may authorize an unproven proof — sorryAx is
    stripped at THE derivation chokepoint, and a sorryAx-only whitelist
    degrades to the framework defaults, never to an empty gate."""
    manifest._default_axioms_warned.clear()
    m = manifest.Manifest(problem="p_sry", statement="s",
                          axioms_whitelist=["propext", "sorryAx"])
    assert manifest.effective_axioms(m) == ["propext"]
    m2 = manifest.Manifest(problem="p_sry2", statement="s",
                           axioms_whitelist=["sorryAx"])
    wl2 = manifest.effective_axioms(m2)
    assert wl2 == list(manifest.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl2


def test_spawn_cmd_denies_user_file_writes() -> None:
    """Self-audit 2026-07-12 §3-1a: every spawn carries the
    --disallowedTools deny for Manifest.md / Defs.lean / Root.lean
    (Write + Edit). Source pin — the flag lives in the one cmd builder
    all agent kinds share."""
    src = (Path(__file__).resolve().parents[1]
           / "Tooling" / "llm" / "claude_cli.py").read_text(
               encoding="utf-8")
    assert '"--disallowedTools"' in src
    for f in ("Manifest.md", "Defs.lean", "Root.lean"):
        assert f'"Write(**/{f})"' in src, f
        assert f'"Edit(**/{f})"' in src, f


def test_spawn_isolates_operator_memory() -> None:
    """2026-07-13: Claude Code auto-memory is keyed by git repo root,
    so spawns cwd'd in Problems/<p>/ shared the OPERATOR's memory dir
    (bidirectional: solution leaks in, context injection out). Source
    pin for both layers — the env kill switch and the ~/.claude
    projects-subtree deny rules."""
    src = (Path(__file__).resolve().parents[1]
           / "Tooling" / "llm" / "claude_cli.py").read_text(
               encoding="utf-8")
    # env layer present at the claude spawn call site
    assert src.count('["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"') == 1
    # deny-rule layer wired into the spawn cmd
    assert "*_operator_state_deny_rules()," in src
    from Tooling.llm.claude_cli import _operator_state_deny_rules
    rules = _operator_state_deny_rules()
    assert len(rules) == 3
    for rule, kind in zip(rules, ("Read", "Write", "Edit")):
        assert rule.startswith(f"{kind}(//")
        assert rule.endswith("/.claude/projects/**)")


def test_effective_axioms_empty_falls_back_to_framework_default(
        capsys) -> None:
    """Absent field NEVER weakens a gate: framework default, warned once
    per problem (not once per gate call)."""
    manifest._default_axioms_warned.clear()
    m = manifest.Manifest(problem="p_eff", statement="s")
    wl = manifest.effective_axioms(m)
    assert wl == list(manifest.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl
    out = capsys.readouterr().out
    assert "framework default" in out
    manifest.effective_axioms(m)                     # second call: silent
    assert "framework default" not in capsys.readouterr().out


def test_effective_axioms_verify_reexport_is_same_object() -> None:
    from Tooling.quality import verify
    assert verify.FRAMEWORK_DEFAULT_AXIOMS is manifest.FRAMEWORK_DEFAULT_AXIOMS
