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

from Tooling.pipeline.backward import (_resolve_cite_dependencies,
                                       inject_missing_sibling_imports)
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
            workspace=Path.cwd(),
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
            workspace=Path.cwd(),
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_accepts_when_cited_slug_is_proved_alias(
    conn: sqlite3.Connection,
) -> None:
    """Citing a PROVED ALIAS sibling — the alias's `L_<slug>.lean` delegates
    to a byte-identical canonical (`apply <canonical>`, sorry-free), so it is
    exactly as citable as the canonical. Regression for the mayer_vietoris
    `mv_delta` block (2026-07-03): the cite gate misclassified a proved alias
    as an orphan stub because `classify_cited_slug` filtered out aliases."""
    canonical = _insert_goal(conn, "mv_delta_canonical", status="proved")
    alias = _insert_goal(conn, "mv_delta", status="proved")
    conn.execute("UPDATE goals SET alias_target_id = ? WHERE id = ?",
                 (canonical, alias))
    conn.commit()

    # Direct classify: alias resolves through to the canonical, reported citable.
    gid, status, orphan = db.classify_cited_slug(
        conn, problem="p", slug="mv_delta", workspace=Path.cwd())
    assert (gid, status, orphan) == (canonical, "proved", False)

    # End-to-end: citing the alias passes (no auto_link needed, no error).
    patch = "import Problems.p.proofs.L_mv_delta\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
            workspace=Path.cwd(),
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_alias_to_open_canonical_inherits_status(
    conn: sqlite3.Connection,
) -> None:
    """An alias to an OPEN canonical inherits the canonical's status (not a
    free pass): auto-link on the decomp path, reject on leaf-bypass — the
    same handling the open canonical itself would get."""
    canonical = _insert_goal(conn, "open_canonical", status="open")
    alias = _insert_goal(conn, "open_alias", status="proved")
    conn.execute("UPDATE goals SET alias_target_id = ? WHERE id = ?",
                 (canonical, alias))
    conn.commit()
    gid, status, orphan = db.classify_cited_slug(
        conn, problem="p", slug="open_alias", workspace=Path.cwd())
    assert (gid, status, orphan) == (canonical, "open", False)


def test_skips_unknown_slug(conn: sqlite3.Connection) -> None:
    """Cited slug matches no goal AND no file on disk — a genuine typo /
    cross-problem ref. lake's `unknown identifier`/`unknown module` will
    catch it; the gate passes through (does NOT double-reject). Contrast
    with `test_rejects_orphan_stub_file` where the file DOES exist."""
    patch = "import Problems.p.proofs.L_nonexistent\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
            workspace=Path.cwd(),
        )
        assert err is None
        assert auto_link == set()
        assert revive == set()


def test_rejects_cross_problem_imports(conn: sqlite3.Connection) -> None:
    """Citing another problem's node is NOT allowed — only same-problem
    siblings, Library, and Mathlib are citable. (Previously skipped, leaving
    lake to maybe build it.)"""
    _insert_goal(conn, "foo", status="open")
    patch = "import Problems.other.proofs.L_foo\n"  # different problem
    for allow in (True, False):
        _, _, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
            workspace=Path.cwd(),
        )
        assert err is not None
        assert "cross-problem" in err


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
            workspace=Path.cwd(),
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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
    )
    assert err is None
    assert auto_link == {g1, g2}
    assert revive == set()


def test_decomp_revives_cascade_shelved_sibling(
    conn: sqlite3.Connection,
) -> None:
    """T8: a CASCADE-shelved sibling (lost its last live path, NO ConfirmShelve
    decision targeting it) is a soft terminal that dedupe does NOT block, so
    citation revives it rather than rejecting. It lands in BOTH auto_link
    (linked as a sub-goal) and revive (caller reopens to 'open'). No error —
    the citing strategy gives it a fresh live path to root."""
    g_sh = _insert_goal(conn, "sh", status="shelved")
    patch = "import Problems.p.proofs.L_sh\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
        workspace=Path.cwd(),
    )
    assert err is None
    assert auto_link == {g_sh}
    assert revive == {g_sh}


def _insert_decision(conn: sqlite3.Connection, kind: str,
                     target_id: int | None) -> None:
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', ?, ?, ?, ?)",
        (kind, target_id, db.now(), db.now()),
    )
    conn.commit()


def test_decomp_links_but_does_not_revive_confirmshelve_parked(
    conn: sqlite3.Connection,
) -> None:
    """A ConfirmShelve-PARKED sibling (the latest decision targeting it is a
    ConfirmShelve) is deliberately held pending its injected prereqs. Citation
    still auto_links it (the citing strategy WAITS for it to prove via its own
    inject_batch_done re-engagement), but must NOT revive it — reopening early
    re-dispatches before prereqs exist → re-fail → re-shelve mini-spin."""
    g = _insert_goal(conn, "parked", status="shelved")
    _insert_decision(conn, "ConfirmShelve", g)   # latest action = ConfirmShelve
    patch = "import Problems.p.proofs.L_parked\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
        workspace=Path.cwd(),
    )
    assert err is None
    assert auto_link == {g}     # citing strategy still waits for it
    assert revive == set()      # but NOT reopened early


def test_decomp_revives_shelved_after_reengage_inject(
    conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve then a LATER Inject(target=goal) re-engaged it; if it is
    shelved again now (cascade, no new decision row), the latest targeting
    decision is that Inject, not the ConfirmShelve → NOT parked → revive."""
    g = _insert_goal(conn, "reeng", status="shelved")
    _insert_decision(conn, "ConfirmShelve", g)
    _insert_decision(conn, "Inject", g)          # later re-engagement
    patch = "import Problems.p.proofs.L_reeng\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs=set(), allow_auto_link=True,
        workspace=Path.cwd(),
    )
    assert err is None
    assert auto_link == {g}
    assert revive == {g}        # un-parked → revivable again


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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
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
        workspace=Path.cwd(),
    )
    assert err is not None
    assert "sh" in err and "de" in err
    assert revive == set()


# ---------------------------------------------------------------------
# Orphan stub — file on disk, no tracked goal (DB↔file drift). Citing it
# imports a sorry and silently fake-proves the citer (P13 root sorryAx via
# density_form_supp_lhs_slice). Reject on BOTH paths.
# ---------------------------------------------------------------------

def test_rejects_orphan_stub_file(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """`proofs/L_<slug>.lean` exists but no goal row tracks it = orphan
    stub (a sub-goal whose row never committed — e.g. a Backward killed
    mid-placement). lake imports it fine and its `sorry` only warns, so
    citing it would fake-prove the citer. Reject regardless of path."""
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "L_orphan_lemma.lean").write_text(
        "theorem orphan_lemma : True := by sorry\n", encoding="utf-8")
    patch = "import Problems.p.proofs.L_orphan_lemma\n"
    for allow in (True, False):
        auto_link, revive, err = _resolve_cite_dependencies(
            conn, problem="p", patch_text=patch,
            declared_slugs=set(), allow_auto_link=allow,
            workspace=tmp_path,
        )
        assert err is not None
        assert "orphan_lemma" in err
        assert "orphan" in err.lower()
        assert auto_link == set()
        assert revive == set()


def test_declared_orphan_slug_still_skips(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A slug the agent declares as its OWN `new_<slug>.lean` sub-goal in
    THIS commit is skipped before the orphan check — declaring it is
    exactly the prescribed fix, so it must not be rejected even though no
    goal row exists yet and a stub file is present."""
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "L_freshly_declared.lean").write_text(
        "theorem freshly_declared : True := by sorry\n", encoding="utf-8")
    patch = "import Problems.p.proofs.L_freshly_declared\n"
    auto_link, revive, err = _resolve_cite_dependencies(
        conn, problem="p", patch_text=patch,
        declared_slugs={"freshly_declared"}, allow_auto_link=True,
        workspace=tmp_path,
    )
    assert err is None
    assert auto_link == set() and revive == set()


# ---------------------------------------------------------------------
# Auto-inject missing proved-sibling imports + cross-problem reject
# ---------------------------------------------------------------------

def test_inject_adds_missing_proved_sibling_import(conn, tmp_path):
    _insert_goal(conn, "half_space_ftc", status="proved")
    conn.commit()
    patch = ("import Mathlib\n\nnamespace Problems.p\n"
             "theorem s1 : T := by exact half_space_ftc\nend Problems.p\n")
    new, added = inject_missing_sibling_imports(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
        workspace=tmp_path)
    assert added == ["half_space_ftc"]
    assert "import Problems.p.proofs.L_half_space_ftc" in new


def test_inject_skips_unproved_declared_and_already_imported(conn, tmp_path):
    _insert_goal(conn, "proved_unref", status="proved")   # not referenced
    _insert_goal(conn, "open_ref", status="open")          # referenced, unproved
    _insert_goal(conn, "declared_ref", status="proved")    # referenced, declared
    _insert_goal(conn, "imported_ref", status="proved")    # referenced, imported
    conn.commit()
    patch = ("import Mathlib\nimport Problems.p.proofs.L_imported_ref\n\n"
             "theorem s1 : T := by exact open_ref <;> exact declared_ref "
             "<;> exact imported_ref\n")
    new, added = inject_missing_sibling_imports(
        conn, problem="p", patch_text=patch,
        declared_slugs={"declared_ref"}, workspace=tmp_path)
    assert added == []
    assert new == patch  # untouched
