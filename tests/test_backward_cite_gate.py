"""Backward citation gate (`_resolve_cite_dependencies`).

Classifies cited siblings:
  - declared / proved → pass through
  - open/attempting/pending_strategist_review:
      - decomp path (allow_auto_link=True) → auto-link as sub-goal
      - leaf-bypass path (allow_auto_link=False) → reject
  - shelved/dead (soft/context terminals, dedupe does NOT block them):
      - decomp path → REVIVE: auto-link + flag for reopen-to-'open'
        (the citing strategy gives them a fresh live path to root)
      - leaf-bypass path → reject (can't tolerate transitive sorry)
  - disproved (hard terminal, counterexample, dedupe BLOCKS) → always
    reject (the one never-citable status)

Returns a 3-tuple `(auto_link, revive, err)` with `revive` ⊆ `auto_link`.

Auto-link path enables Strategist-orchestrated parallel tool building:
Backward strategy can cite an in-flight Forward, framework links it
into `strategy_subgoals`, and `strategies_ready_for_verify` blocks the
strategy from verifying until the cited goal proves. The revive path
(agent_feedback T8) additionally unblocks cascade-shelved leaves once a
later strategy organically needs them.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline.backward import _resolve_cite_dependencies
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_goal(conn: sqlite3.Connection, slug: str, *,
                 status: str) -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement="T", origin="backward", status=status,
    )


# ---------------------------------------------------------------------
# Always-accept cases (regardless of allow_auto_link)
# ---------------------------------------------------------------------

def test_accepts_when_cited_slug_is_declared_subgoal(
    conn: sqlite3.Connection,
) -> None:
    """Agent declares `new_helper.lean` AND imports it from patch.lean —
    that's the framework-injected sub-goal import. No reject."""
    patch = "import Problems.p.proofs.L_helper\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs={"helper"}, allow_auto_link=allow,
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_accepts_when_cited_slug_is_proved(
    conn: sqlite3.Connection,
) -> None:
    """Citing a proved sibling — soundness-safe library use."""
    _insert_goal(conn, "winding_number_int", status="proved")
    patch = "import Problems.p.proofs.L_winding_number_int\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_skips_unknown_slug(conn: sqlite3.Connection) -> None:
    """Cited slug doesn't match any goal — lake's `unknown identifier`
    will catch it. Citation gate doesn't double-reject."""
    patch = "import Problems.p.proofs.L_nonexistent\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_skips_cross_problem_imports(conn: sqlite3.Connection) -> None:
    """Imports targeting other problems are out of this gate's scope
    (cross-problem soundness invariants live elsewhere)."""
    _insert_goal(conn, "foo", status="open")
    patch = "import Problems.other.proofs.L_foo\n"  # different problem
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_skips_aliased_goal_row(conn: sqlite3.Connection) -> None:
    """alias_target_id IS NULL filter — aliased goals shouldn't be
    counted as the citable lemma; the canonical goal (alias_target_id
    IS NULL) is what gets imported and checked."""
    _insert_goal(conn, "real", status="proved")
    patch = "import Problems.p.proofs.L_real\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


# ---------------------------------------------------------------------
# Auto-link cases — decomp path (`allow_auto_link=True`)
# ---------------------------------------------------------------------

def test_decomp_auto_links_open_sibling(
    conn: sqlite3.Connection,
) -> None:
    """Decomp path: open sibling is auto-linked as a sub-goal so the
    strategy waits for it to prove. No rejection, no revival needed."""
    gid = _insert_goal(conn, "cauchy_simply_connected", status="open")
    patch = "import Problems.p.proofs.L_cauchy_simply_connected\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is None
    assert auto_link == {gid}
    assert revive == set()


def test_decomp_auto_links_attempting_and_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """`attempting` and `pending_strategist_review` are also auto-link-
    able — they're non-terminal, work-in-progress states, and need no
    revival (already dispatchable / under review)."""
    g1 = _insert_goal(conn, "foo", status="attempting")
    g2 = _insert_goal(conn, "bar", status="pending_strategist_review")
    patch = (
        "import Problems.p.proofs.L_foo\n"
        "import Problems.p.proofs.L_bar\n"
    )
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is None
    assert auto_link == {g1, g2}
    assert revive == set()


def test_decomp_revives_shelved_sibling(
    conn: sqlite3.Connection,
) -> None:
    """T8: shelved is a soft terminal that dedupe does NOT block, so
    citation revives it rather than rejecting. It lands in BOTH auto_link
    (linked as a sub-goal) and revive (caller reopens to 'open'). No error
    — the citing strategy gives it a fresh live path to root."""
    g_sh = _insert_goal(conn, "sh", status="shelved")
    patch = "import Problems.p.proofs.L_sh\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is None
    assert auto_link == {g_sh}
    assert revive == {g_sh}


def test_decomp_rejects_dead_sibling(
    conn: sqlite3.Connection,
) -> None:
    """'dead' = the statement is wrong AS STATED in its parent's
    decomposition (parent_needs_fix); the goals.status contract makes it
    never-Reopen. Citing it would re-attempt a known-wrong statement, so
    it is REJECTED (not revived) — the agent must re-declare the statement
    fresh as its own sub-goal stub under a corrected context."""
    _insert_goal(conn, "de", status="dead")
    patch = "import Problems.p.proofs.L_de\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is not None
    assert "de" in err
    assert "DEAD" in err or "dead" in err
    assert revive == set()


def test_decomp_rejects_disproved_sibling(
    conn: sqlite3.Connection,
) -> None:
    """`disproved` is the one hard terminal (a counterexample was found);
    dedupe BLOCKS it, so does citation. Reject with a 'disproved /
    different angle' hint — never revived."""
    _insert_goal(conn, "di", status="disproved")
    patch = "import Problems.p.proofs.L_di\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is not None
    assert "di" in err
    assert "DISPROVED" in err or "disproved" in err
    assert revive == set()


def test_decomp_mixes_proved_open_shelved_and_disproved(
    conn: sqlite3.Connection,
) -> None:
    """Mixed batch: proved skipped, open auto-linked, shelved revived,
    disproved rejected. A single disproved citation aborts the whole
    strategy (statement is false); the revivable ones are still
    collected (caller ignores on err)."""
    _insert_goal(conn, "good_proved", status="proved")
    g_open = _insert_goal(conn, "open_dep", status="open")
    g_sh = _insert_goal(conn, "shelved_dep", status="shelved")
    _insert_goal(conn, "false_dep", status="disproved")
    patch = (
        "import Problems.p.proofs.L_good_proved\n"
        "import Problems.p.proofs.L_open_dep\n"
        "import Problems.p.proofs.L_shelved_dep\n"
        "import Problems.p.proofs.L_false_dep\n"
    )
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
    )
    assert err is not None  # false_dep aborts the strategy
    assert "false_dep" in err
    # revivable/open ones still collected (caller ignores them on err)
    assert g_open in auto_link
    assert g_sh in auto_link and g_sh in revive


# ---------------------------------------------------------------------
# Leaf-bypass path (`allow_auto_link=False`) — same surface but rejects
# every non-proved cite (axiom probe at submit can't tolerate transitive
# sorry from a cited stub; revival is a decomp-path capability).
# ---------------------------------------------------------------------

def test_leafbypass_rejects_open_sibling(
    conn: sqlite3.Connection,
) -> None:
    """Leaf-bypass strategies run axiom probe at submit — they can't
    cite unproved siblings (the cited stub's `:= by sorry` would show
    up in the transitive axiom set). Reject with hint pointing at the
    decomp path's auto-link mechanism."""
    _insert_goal(conn, "open_dep", status="open")
    patch = "import Problems.p.proofs.L_open_dep\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=False,
    )
    assert err is not None
    assert "open_dep" in err
    assert "Leaf-bypass" in err or "decomp" in err.lower()
    assert revive == set()


def test_leafbypass_rejects_attempting_and_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """Same as open — any non-proved state rejects in leaf-bypass."""
    _insert_goal(conn, "foo", status="attempting")
    _insert_goal(conn, "bar", status="pending_strategist_review")
    patch = (
        "import Problems.p.proofs.L_foo\n"
        "import Problems.p.proofs.L_bar\n"
    )
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=False,
    )
    assert err is not None
    assert "foo" in err and "bar" in err
    assert revive == set()


def test_leafbypass_rejects_shelved_and_dead(
    conn: sqlite3.Connection,
) -> None:
    """Leaf-bypass can't revive — shelved/dead reject here even though
    the decomp path would revive them (no parallel-wait / decomposition
    to defer verification behind)."""
    _insert_goal(conn, "sh", status="shelved")
    _insert_goal(conn, "de", status="dead")
    patch = (
        "import Problems.p.proofs.L_sh\n"
        "import Problems.p.proofs.L_de\n"
    )
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=False,
    )
    assert err is not None
    assert "sh" in err and "de" in err
    assert revive == set()
