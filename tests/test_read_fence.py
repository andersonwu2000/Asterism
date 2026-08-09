"""The per-spawn READ fence (#162, user ruling 2026-08-10).

One list of operator-private subtrees, rendered by two backends. The
list itself is `envelope.read_deny_roots`; agy turns it into
`read_file(...)` deny rules, claude into `spawn_guard` denials.

Why it has to be BOTH: the exposure was written up as agy-specific for a
week and never was — `spawn_guard._whitelist()` returned the whole repo
root, so a claude spawn could open `docs/internal/` and the live DB just
as freely. A fence on one provider is a fence on the provider we happen
to use less.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling.llm import antigravity_cli as agy
from Tooling.llm import envelope, spawn_guard


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace with problems at BOTH depths — the real tree has
    `Problems/sylvester_gallai` and `Problems/NumberTheory/cube_e2e`."""
    for rel in ("Problems/Combinatorics/union_closed",
                "Problems/Combinatorics/other_combi",
                "Problems/NumberTheory/cube_e2e",
                "Problems/sylvester_gallai",
                "Library", "Papers", "docs/internal", ".asterism/backups"):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    (tmp_path / "asterism.db").write_bytes(b"")
    return tmp_path


def _roots(workspace: Path, problem: str) -> "list[str]":
    return [str(p) for p in envelope.read_deny_roots(
        workspace, workspace / "Problems" / problem)]


# ---------------------------------------------------------------- list

def test_private_subtrees_are_denied(workspace: Path) -> None:
    roots = _roots(workspace, "Combinatorics/union_closed")
    for name in ("docs", ".asterism", "asterism.db"):
        assert str(workspace / name) in roots, name


def test_library_and_papers_stay_readable(workspace: Path) -> None:
    """Both are surfaces the framework hands out on purpose — the
    CATALOG cites Library by name and the scholar loop reads Papers."""
    roots = _roots(workspace, "Combinatorics/union_closed")
    assert str(workspace / "Library") not in roots
    assert str(workspace / "Papers") not in roots


def test_other_problems_denied_at_every_depth(workspace: Path) -> None:
    """Problems sit at mixed depth, so the walk has to deny siblings at
    each level: a same-domain neighbour AND a top-level one."""
    roots = _roots(workspace, "Combinatorics/union_closed")
    assert str(workspace / "Problems" / "Combinatorics" / "other_combi") in roots
    assert str(workspace / "Problems" / "sylvester_gallai") in roots
    assert str(workspace / "Problems" / "NumberTheory") in roots


def test_the_spawns_own_problem_is_never_denied(workspace: Path) -> None:
    """The failure this guards against is silent on agy (status stays
    SUCCESS, the response is empty), so a fence that blinds a legitimate
    spawn reads exactly like a lazy agent."""
    for problem in ("Combinatorics/union_closed", "sylvester_gallai"):
        roots = _roots(workspace, problem)
        own = workspace / "Problems" / problem
        assert not any(str(own) == r or str(own).startswith(r + "\\")
                       or str(own).startswith(r + "/") for r in roots), problem


def test_unknown_problem_dir_denies_nothing_extra(workspace: Path) -> None:
    """A spawn whose problem_dir is not under `Problems/` (paper_index
    lives in `Papers/<pid>`) must not have every problem denied — err
    toward working, never toward a blind spawn."""
    roots = envelope.read_deny_roots(workspace, workspace / "Papers" / "p1")
    assert not any("Problems" in str(r) for r in roots)


# ------------------------------------------------------- agy rendering

def test_agy_renders_the_same_list_as_deny_rules(workspace: Path) -> None:
    spec = SimpleNamespace(
        write_roots=(workspace / ".attempts" / "pid",),
        mcp_config_path=None,
        read_deny_roots=envelope.read_deny_roots(
            workspace, workspace / "Problems" / "sylvester_gallai"))
    rendered = agy._spawn_permissions(spec, workspace)["permissions"]
    assert f"read_file({workspace})" in rendered["allow"]
    for root in spec.read_deny_roots:
        assert f"read_file({root})" in rendered["deny"], root


# ------------------------------------------------ spawn_guard (claude)

def test_guard_denies_a_read_inside_a_private_subtree(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(spawn_guard.READ_DENY_ROOTS_ENV,
                       str(workspace / "docs"))
    reason = spawn_guard.check(
        "Read", {"file_path": str(workspace / "docs" / "internal" / "S.md")},
        str(workspace))
    assert reason and "operator-private" in reason


def test_guard_denies_a_search_rooted_above_a_private_subtree(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prefix check passes `Grep(path=<repo>)` — and the grep prints
    the private files anyway. A search path is a root, not a target."""
    monkeypatch.setenv(spawn_guard.READ_DENY_ROOTS_ENV,
                       str(workspace / "docs"))
    reason = spawn_guard.check("Grep", {"path": str(workspace)},
                               str(workspace))
    assert reason and "would search" in reason


def test_guard_denies_the_same_read_through_bash(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fencing the file tools and leaving `cat` open is the shape that
    nearly cost the write fence."""
    monkeypatch.setenv(spawn_guard.READ_DENY_ROOTS_ENV,
                       str(workspace / "docs"))
    target = workspace / "docs" / "internal" / "S.md"
    reason = spawn_guard.check("Bash", {"command": f"cat {target}"},
                               str(workspace))
    assert reason and "operator-private" in reason


def test_guard_allows_the_spawns_own_files(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    own = workspace / "Problems" / "sylvester_gallai"
    monkeypatch.setenv(spawn_guard.READ_DENY_ROOTS_ENV, str(workspace / "docs"))
    assert spawn_guard.check("Read", {"file_path": str(own / "Root.lean")},
                             str(own)) is None
    assert spawn_guard.check("Grep", {"path": str(own)}, str(own)) is None


def test_guard_without_the_env_denies_nothing(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual / legacy spawns keep the old behaviour, matching the write
    fence's fallback — the fence arrives with the envelope or not at
    all."""
    monkeypatch.delenv(spawn_guard.READ_DENY_ROOTS_ENV, raising=False)
    assert spawn_guard.check(
        "Read", {"file_path": str(workspace / "docs" / "internal" / "S.md")},
        str(workspace)) is None
