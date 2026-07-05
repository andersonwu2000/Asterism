"""Phase 2 — Strategist Context.md compilation.

Covers `phase2_context.compile_strategist_context` review_context
surfacing (Phase 2 §2.2 spec). The take-5 SG regression came from the
pending_review section missing three signals the spec required:
failure reason summary, existing strategy content, and ancestor chain.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.agent import phase2_context
from Tooling.state import db, manifest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _insert_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES (?, '', ?, 1)", (name, db.now()),
    )
    conn.commit()


def _insert_root(conn: sqlite3.Connection, slug: str = "main") -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=f"P/{slug}.lean",
        statement="T", origin="root", depth=0, entry_kind="Backward",
    )


def _insert_strategy(conn: sqlite3.Connection, goal_id: int,
                     proposal_md: str = "",
                     status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, ?, 'test', ?)",
        (goal_id, status, proposal_md, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _link_subgoal(conn: sqlite3.Connection, *, strategy_id: int,
                  subgoal_id: int, position: int = 0) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, ?)", (strategy_id, subgoal_id, position),
    )
    conn.commit()


def _insert_dead_attempt(conn: sqlite3.Connection, *, target_id: int,
                         failure_reason: str, proposal_md: str,
                         failure_detail: str = "",
                         target_kind: str = "Goal",
                         pipeline_id: str = "pid-x") -> int:
    # dead_attempts.pipeline_id FK -> pipelines.id; seed a row first.
    conn.execute(
        "INSERT OR IGNORE INTO pipelines (id, kind, target_id, target_kind,"
        " status, outcome, started_at, finished_at)"
        " VALUES (?, 'Backward', ?, ?, 'failed', 'failed', ?, ?)",
        (pipeline_id, str(target_id), target_kind, db.now(), db.now()),
    )
    cur = conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, proposal_md, artifacts, ts)"
        " VALUES (?, ?, ?, ?, ?, ?, '', ?)",
        (str(target_id), target_kind, pipeline_id, failure_reason,
         failure_detail, proposal_md, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# Pending-review enrichment — the take-5 SG bug surface
# ---------------------------------------------------------------------

def test_pending_review_surfaces_backward_shelve_proposal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Regression — SG take 5: Backward agent declined with a detailed
    shelve brief (5 missing Forward lemmas listed in dead_attempts.
    proposal_md). Pre-fix Context.md hid this from Strategist, which
    then Reopen'd with a redundant directive that asked for exactly the
    missing lemmas as if they existed. After fix, the agent's brief
    appears verbatim under '### Recent failed attempts'."""
    _insert_problem(conn)
    root = _insert_root(conn)
    backward_brief = (
        "-- decline: shelve\n"
        "-- ## Missing scaffolding for Kelly's proof\n"
        "-- Needed Forward lemmas:\n"
        "-- 1. lineThrough\n"
        "-- 2. perpFoot\n"
        "-- 3. perpDistSq\n"
    )
    _insert_dead_attempt(
        conn, target_id=root, failure_reason="agent_shelved",
        failure_detail="backward declined: shelve",
        proposal_md=backward_brief,
    )

    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" in text
    assert "agent_shelved" in text
    assert "Needed Forward lemmas" in text
    assert "lineThrough" in text
    assert "perpFoot" in text


def test_pending_review_surfaces_existing_strategy_content(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Spec §2.2 review_context: '既有 strategy 內容'. Strategist needs
    to know what decomposition was tried before deciding Reopen with
    directive vs Inject Forward."""
    _insert_problem(conn)
    root = _insert_root(conn)
    sid = _insert_strategy(
        conn, root,
        proposal_md="Tried Kelly minimiser split; sub_a, sub_b.",
        status="dead",
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Existing strategies on this goal" in text
    assert f"s{sid}" in text
    assert "Kelly minimiser split" in text
    assert "status=`dead`" in text


def test_pending_review_walks_ancestor_chain_to_root(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Spec §2.2 review_context: 'ancestor 鏈'. Walk subgoal → parent
    strategy → strategy.goal_id upward until origin='root'."""
    _insert_problem(conn)
    root = _insert_root(conn, slug="main")
    s_root = _insert_strategy(conn, root, status="proposed")
    mid = db.insert_goal(
        conn, problem="p", slug="mid", lean_path="P/mid.lean",
        statement="MidStmt", origin="backward", depth=1,
    )
    _link_subgoal(conn, strategy_id=s_root, subgoal_id=mid)
    s_mid = _insert_strategy(conn, mid, status="proposed")
    leaf = db.insert_goal(
        conn, problem="p", slug="leaf", lean_path="P/leaf.lean",
        statement="LeafStmt", origin="backward", depth=2,
    )
    _link_subgoal(conn, strategy_id=s_mid, subgoal_id=leaf)

    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=leaf,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Ancestor chain" in text
    assert "`mid`" in text
    assert "`main`" in text
    assert "(ROOT)" in text


def test_root_pending_review_marks_self_root_chain(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """A root goal pending-reviewed has no upward chain. Section emits a
    'self is root' note so Strategist sees the placeholder rather than
    missing the section entirely."""
    _insert_problem(conn)
    root = _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Ancestor chain" in text
    assert "self" in text or "root" in text


# ---------------------------------------------------------------------
# Other triggers leave new sections out
# ---------------------------------------------------------------------

def test_routine_trigger_omits_review_sections(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """T1 routine trigger: review-specific sections (failure brief,
    existing strategies, ancestor chain) must not appear — they target
    one goal and would be noise outside T2."""
    _insert_problem(conn)
    root = _insert_root(conn)
    _insert_dead_attempt(
        conn, target_id=root, failure_reason="agent_shelved",
        proposal_md="should not appear in routine context",
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" not in text
    assert "### Existing strategies on this goal" not in text
    assert "### Ancestor chain" not in text
    assert "should not appear in routine context" not in text


def test_fresh_problem_routine_context_omits_review_sections(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """A fresh problem's non-review wake: bootstrap context, no review
    target. (Phase 6: first_launch retired; routine stands in.)"""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" not in text
    assert "### Existing strategies on this goal" not in text
    assert "### Ancestor chain" not in text


# ---------------------------------------------------------------------
# `_section_active_goals` alive-set filter — replaces downward
# `cascade_shelve_descendants` (removed once shelved became reopenable +
# auto-detach landed). Strategist must NOT see open/attempting orphans
# of dead-strategy branches as actionable candidates.
# ---------------------------------------------------------------------

def test_active_goals_filters_by_status_only(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """`## Active goals` lists every non-terminal goal in the problem
    (`open` / `attempting` / `pending_strategist_review`). Descendants
    of a dead chain are cascade-shelved at the data layer (see
    `dispatcher._cascade_shelve_descendants`), so their `status='shelved'`
    already excludes them — no view-level filter needed. This test
    pre-seeds an orphan with status='shelved' explicitly to mirror the
    post-cascade state."""
    _insert_problem(conn)
    root = db.insert_goal(
        conn, problem="p", slug="main", lean_path="P/main.lean",
        statement="T", origin="root",
    )
    # Simulate a fully cascade-shelved orphan (the state the framework
    # converges on when its parent chain dies):
    dead_strat = _insert_strategy(conn, root, status="dead")
    orphan = db.insert_goal(
        conn, problem="p", slug="orphan", lean_path="P/orphan.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, orphan, "shelved")
    _link_subgoal(conn, strategy_id=dead_strat, subgoal_id=orphan)
    # Live sub under live strategy — appears.
    live_strat = _insert_strategy(conn, root, status="proposed")
    live_sub = db.insert_goal(
        conn, problem="p", slug="live_sub", lean_path="P/live_sub.lean",
        statement="T", origin="backward",
    )
    _link_subgoal(conn, strategy_id=live_strat, subgoal_id=live_sub)

    lines = phase2_context._section_active_goals(conn, "p")
    text = "\n".join(lines)
    assert "`main`" in text
    assert "`live_sub`" in text
    # Shelved orphan: excluded by status filter (status='shelved' is
    # not in the active-status set).
    assert "`orphan`" not in text


def test_active_goals_includes_detached_orphan(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """When Strategist Reopens an orphan sub-goal, `detached=1` is set
    so BFS can dispatch it standalone. `_section_active_goals` must
    surface detached goals too (their parent chain is dead but the
    framework's auto-detach mechanism made them independently alive)."""
    _insert_problem(conn)
    root = db.insert_goal(
        conn, problem="p", slug="main", lean_path="P/main.lean",
        statement="T", origin="root",
    )
    dead_strat = _insert_strategy(conn, root, status="dead")
    # Orphan that got Reopened → detached=1
    detached_orphan = db.insert_goal(
        conn, problem="p", slug="detached_orphan",
        lean_path="P/detached_orphan.lean",
        statement="T", origin="backward",
    )
    db.set_goal_detached(conn, detached_orphan, True)
    _link_subgoal(conn, strategy_id=dead_strat, subgoal_id=detached_orphan)

    lines = phase2_context._section_active_goals(conn, "p")
    text = "\n".join(lines)
    assert "`detached_orphan`" in text


# ---------------------------------------------------------------------
# Phase 2.5 — inject_batch_done section
# ---------------------------------------------------------------------

def _seed_inject_batch_done(conn: sqlite3.Connection, *, problem: str = "p",
                            batch_id: str, briefs: list[str],
                            outcomes: list[str]) -> list[int]:
    ts = db.now()
    ids: list[int] = []
    for i, (b, o) in enumerate(zip(briefs, outcomes)):
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, brief, reason,"
            " payload, batch_id, outcome, created_at, updated_at)"
            " VALUES (?, 0, 'pending_review', 'Inject', NULL, ?, NULL,"
            "         ?, ?, ?, ?, ?)",
            (problem, b,
             '{"pipeline":"Forward","step_index":' + str(i)
                + ',"batch_size":' + str(len(briefs)) + '}',
             batch_id, o, ts, ts),
        )
        ids.append(int(cur.lastrowid))
    conn.commit()
    return ids


def test_inject_batch_done_surfaces_briefs_and_outcomes(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """trigger_kind='inject_batch_done' Context surfaces each completed
    batch's brief + outcome per step. Strategist needs the per-step
    outcome to decide: all success → Reopen, partial fail → Inject
    more / ConfirmShelve."""
    _insert_problem(conn)
    _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-X",
        briefs=["land lineThrough", "land perpFoot", "land perpDistSq"],
        outcomes=["success", "failed:lake_build_error", "success"],
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "Batch `batch-X" in text
    assert "land lineThrough" in text
    assert "land perpFoot" in text
    assert "land perpDistSq" in text
    assert "success" in text
    assert "lake_build_error" in text


def test_inject_batch_done_surfaces_outcome_detail_why(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """#4 — the completed-batch section shows a decline's `## Why`
    (`outcome_detail`) so the Strategist sees WHY its brief was declined,
    not just the coarse `failed:agent_declined` enum."""
    _insert_problem(conn)
    _insert_root(conn)
    ids = _seed_inject_batch_done(
        conn, batch_id="batch-why",
        briefs=["land foo_bridge"], outcomes=["failed:agent_declined"])
    conn.execute(
        "UPDATE strategist_decisions SET outcome_detail = ? WHERE id = ?",
        ("agent declined (library_sufficient): Mathlib's "
         "extDerivWithin_apply already covers it", ids[0]))
    conn.commit()
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "why:" in text
    assert "extDerivWithin_apply" in text


def test_inject_batch_section_omitted_when_no_unack_batch(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Without any unack batch, the section doesn't appear (defensive —
    rendering must not show stale data)."""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" not in text


def test_routine_trigger_shows_unack_batch_section(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Routine trigger (or any other non-inject_batch_done trigger)
    MUST surface unack batch outcomes — otherwise a Strategist invoked
    between batch completion and the queued inject_batch_done dispatch
    advances `last_strategist_at` without seeing the batch (race; see
    `_section_inject_batch_outcomes` docstring)."""
    _insert_problem(conn)
    _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-Y",
        briefs=["lemma A", "lemma B"],
        outcomes=["success", "success"],
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "Batch `batch-Y" in text
    assert "lemma A" in text


def test_pending_review_trigger_shows_unack_batch_section(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Same race-avoidance for pending_review: a T2 Strategist
    invocation must see batches that completed since the last commit."""
    _insert_problem(conn)
    root = _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-Z",
        briefs=["b1", "b2"], outcomes=["success", "success"],
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "Batch `batch-Z" in text


def test_inject_batch_section_omits_produced_lemma(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Batch section deliberately does NOT attribute Forward lemmas to
    specific batch steps. Goals don't carry decision_id; attribution
    by problem + created_at can't disambiguate batch steps (would
    misattribute multiple lemmas to the earliest step). Strategist
    reads `## Library` / `## TREE` for what landed."""
    _insert_problem(conn)
    _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-W",
        briefs=["b1", "b2"], outcomes=["success", "success"],
    )
    # Add two Forward lemmas that would tempt the old heuristic to
    # misattribute both to batch step 0.
    db.insert_goal(
        conn, problem="p", slug="forward_a", lean_path="P/forward_a.lean",
        statement="A", origin="forward", depth=0,
    )
    db.insert_goal(
        conn, problem="p", slug="forward_b", lean_path="P/forward_b.lean",
        statement="B", origin="forward", depth=0,
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "produced:" not in text


# ---------------------------------------------------------------------
# _section_pending_reopens — batch-scoped surfacing (brouwer 2026-05-22 G2)
# ---------------------------------------------------------------------

def _seed_shelved_goal(conn: sqlite3.Connection, *, slug: str,
                       problem: str = "p") -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, gid, "shelved")
    return gid


def _seed_confirmshelve_with_inject_batch(
    conn: sqlite3.Connection, *, problem: str = "p",
    goal_id: int, batch_id: str, inject_outcomes: list[str | None],
    cs_reason: str = "deferred; injecting follow-up brick",
) -> int:
    """Seed one ConfirmShelve(goal_id) + N Inject(Forward) rows sharing
    `batch_id`. `inject_outcomes` length controls N (None means still
    in-flight, str means terminal). Returns the ConfirmShelve row id.
    """
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES (?, 0, 'inject_batch_done', 'ConfirmShelve', ?, NULL, ?, '{}', ?,"
        "         NULL, ?, ?)",
        (problem, str(goal_id), cs_reason, batch_id, ts, ts),
    )
    cs_id = int(cur.lastrowid)
    for i, oc in enumerate(inject_outcomes):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, brief, reason,"
            " payload, batch_id, outcome, created_at, updated_at)"
            " VALUES (?, 0, 'inject_batch_done', 'Inject', NULL, ?, NULL,"
            "         ?, ?, ?, ?, ?)",
            (problem, f"## Need\nbrick {i}",
             '{"pipeline":"Forward","step_index":' + str(i) + '}',
             batch_id, oc, ts, ts),
        )
    conn.commit()
    return cs_id


def test_pending_reopens_surfaces_promised_goal_when_batch_complete(
    conn: sqlite3.Connection,
) -> None:
    """Happy path — ConfirmShelve(G) + Inject batch shipped together,
    all Injects landed → G surfaces with the promised batch's
    completion summary."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_shelved")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-promised",
        inject_outcomes=["success", "success"],
    )
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    body = "\n".join(lines)
    assert "## Pending reopen-promises" in body
    assert "g_shelved" in body


def test_pending_reopens_suppresses_when_promised_batch_inflight(
    conn: sqlite3.Connection,
) -> None:
    """Inject batch still has a row with outcome=NULL → the promise
    hasn't landed yet; don't surface the goal."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_pending")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-inflight",
        inject_outcomes=["success", None],  # one still in flight
    )
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    assert lines == []


def test_pending_reopens_suppresses_after_already_addressed(
    conn: sqlite3.Connection,
) -> None:
    """Once Strategist has emitted a later ConfirmShelve/Reopen on the
    same goal, the previously-promised batch is "addressed"; don't
    re-surface (brouwer g2771 re-ConfirmShelve x4 incident)."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_addressed")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-first",
        inject_outcomes=["success"],
    )
    # Strategist already considered + re-shelved with a fresher batch.
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-second",
        inject_outcomes=["success"],
    )
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    body = "\n".join(lines)
    # The fresher (batch-second) WAS the latest CS — and its batch is
    # complete — so it should surface; but the original "batch-first"
    # surfacing must not. Single appearance only.
    assert body.count("g_addressed") == 1


def test_pending_reopens_skips_legacy_cs_with_null_batch_id(
    conn: sqlite3.Connection,
) -> None:
    """Pre-fix ConfirmShelve rows have batch_id=NULL (no link to
    promised Injects). Such rows can't surface because the promise
    can't be reconstructed; the goal stays shelved until a fresher
    ConfirmShelve binds it to a batch. Documents intentional
    forward-only behavior — no retro-fix for legacy data."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_legacy")
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'ConfirmShelve', ?, NULL,"
        "         'old', '{}', NULL, NULL, ?, ?)",
        (str(g), ts, ts),
    )
    conn.commit()
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    assert lines == []


def test_pending_reopens_skips_batch_with_only_confirmshelve_reopen(
    conn: sqlite3.Connection,
) -> None:
    """A ConfirmShelve+Reopen pair (no Inject) carries no follow-up
    promise to wait on, so surfacing makes no sense even when the
    batch_id is set."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_no_inject")
    ts = db.now()
    # ConfirmShelve in batch, no Inject sibling.
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'ConfirmShelve', ?, NULL,"
        "         'r', '{}', 'batch-no-inj', NULL, ?, ?)",
        (str(g), ts, ts),
    )
    conn.commit()
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    assert lines == []


def test_pending_reopens_skipped_on_non_inject_batch_done_trigger(
    conn: sqlite3.Connection,
) -> None:
    """Other trigger kinds (routine / pending_review / first_launch)
    skip this section entirely — the inject_batch_done gate is what
    makes "promised batch completion" semantically meaningful."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_skip")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-X",
        inject_outcomes=["success"],
    )
    for trig in ("routine", "pending_review"):
        assert phase2_context._section_pending_reopens(conn, "p", trig) == []


# ---------------------------------------------------------------------
# B-2 — _section_stall_warning (structural-deadlock signal)
# ---------------------------------------------------------------------

def test_stall_warning_surfaces_when_no_open_goal_no_inflight(
    conn: sqlite3.Connection,
) -> None:
    """Root attempting, no open goals, queue empty → stall warning
    section surfaces."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "attempting")
    # Make a non-open goal so we exercise the "no open goal" branch
    other = db.insert_goal(
        conn, problem="p", slug="other",
        lean_path="P/proofs/L_other.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, other, "attempting")

    lines = phase2_context._section_stall_warning(conn, "p")
    body = "\n".join(lines)
    assert "## Framework stalled" in body
    assert "Noop` is not appropriate" in body


def test_stall_warning_surfaces_when_open_goal_orphaned(
    conn: sqlite3.Connection,
) -> None:
    """Regression (P13 2026-06-13): an open goal reachable ONLY through a
    DEAD strategy (never the alive seed) is not dispatchable, so the
    problem IS stalled and the warning MUST surface. The pre-fix raw
    `status='open'` probe masked this, so T4 fired Strategists that saw no
    warning and Noop-confirmed into a livelock. Now both T4
    (`db.problems_stalled`) and this section share `db.is_problem_stalled`
    (reachable-open), so they agree."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "attempting")
    orph = db.insert_goal(
        conn, problem="p", slug="orph",
        lean_path="P/proofs/L_orph.lean", statement="T", origin="backward",
    )
    dead_s = _insert_strategy(conn, root, status="dead")
    _link_subgoal(conn, strategy_id=dead_s, subgoal_id=orph)

    lines = phase2_context._section_stall_warning(conn, "p")
    assert "## Framework stalled" in "\n".join(lines)


def test_stall_warning_silent_when_reachable_open_goal_exists(
    conn: sqlite3.Connection,
) -> None:
    """A non-root open goal reachable via a 'proposed' strategy IS
    dispatchable → no stall, no warning (the in-flight/dispatchable
    counterpart to the orphaned case above)."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "attempting")
    child = db.insert_goal(
        conn, problem="p", slug="child",
        lean_path="P/proofs/L_child.lean", statement="T", origin="backward",
    )
    live_s = _insert_strategy(conn, root, status="proposed")
    _link_subgoal(conn, strategy_id=live_s, subgoal_id=child)

    assert phase2_context._section_stall_warning(conn, "p") == []


def test_stall_warning_silent_when_open_goal_exists(
    conn: sqlite3.Connection,
) -> None:
    """An open goal means BFS can dispatch — no stall, no warning."""
    _insert_problem(conn)
    _insert_root(conn)
    db.insert_goal(
        conn, problem="p", slug="open_one",
        lean_path="P/proofs/L_open_one.lean", statement="T",
        origin="backward",
    )

    assert phase2_context._section_stall_warning(conn, "p") == []


def test_stall_warning_silent_when_backward_in_queue(
    conn: sqlite3.Connection,
) -> None:
    """In-flight Backward via queue means a dispatch is imminent — no
    stall."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "attempting")
    other = db.insert_goal(
        conn, problem="p", slug="other",
        lean_path="P/proofs/L_other.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, other, "attempting")
    db.enqueue(conn, kind="Backward", target_id=str(other),
               target_kind="Goal", priority=2, problem="p")

    assert phase2_context._section_stall_warning(conn, "p") == []


def test_stall_warning_shown_when_root_proved_but_not_ingested(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 — a proved root with no committed Ingest IS stalled when
    idle (the wake that commits Ingest), so the warning must surface;
    the shared predicate keeps this section in lockstep with T4."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "proved")

    assert phase2_context._section_stall_warning(conn, "p") != []


def test_stall_warning_silent_when_ingested(
    conn: sqlite3.Connection,
) -> None:
    """Committed Ingest (`ingested_at` set) is the problem terminal
    state — never stalled, no warning."""
    _insert_problem(conn)
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "proved")
    db.set_problem_ingested(conn, "p")

    assert phase2_context._section_stall_warning(conn, "p") == []


def test_current_directive_section_silent_when_unset(
    conn: sqlite3.Connection,
) -> None:
    """No directive → no section. Strategist Context.md stays compact."""
    _insert_problem(conn)
    assert phase2_context._section_current_directive(conn, "p") == []


def test_current_directive_section_surfaces_existing_body(
    conn: sqlite3.Connection,
) -> None:
    """When directive is set, Strategist Context.md surfaces it under
    `## Current standing directive` so Strategist can diff-update it
    on the next routine wake instead of overwriting blindly.

    Worker Context.md (separate code path,
    `context._section_strategist_directive`) already surfaces directive
    to workers; this test covers the Strategist-side mirror. Each
    Strategist invocation is a fresh agent session — without this
    section the agent has no memory of what it (or a prior wake) wrote.
    """
    _insert_problem(conn)
    db.set_problem_strategist_directive(
        conn, "p",
        "## Mathlib hints\n- Module.End.exists_eigenvalue\n- Basis.card_eq_finrank")

    lines = phase2_context._section_current_directive(conn, "p")
    body = "\n".join(lines)
    assert "## Current standing directive" in body
    assert "Module.End.exists_eigenvalue" in body
    assert "rolling curated document" in body


def test_current_directive_section_silent_when_only_whitespace(
    conn: sqlite3.Connection,
) -> None:
    """Whitespace-only directive treated as empty — no noise section."""
    _insert_problem(conn)
    db.set_problem_strategist_directive(conn, "p", "   \n\n  ")
    assert phase2_context._section_current_directive(conn, "p") == []


# ---------------------------------------------------------------------
# Plan note — the Strategist's private cross-wake section (2026-07-05)
# ---------------------------------------------------------------------

def test_plan_note_section_absent_when_no_note(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    assert phase2_context._section_plan_note(workspace, "p") == []


def test_plan_note_section_renders_and_warns_over_cap(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Present note → private section in the STRATEGIST context; a note
    past the soft cap gets exactly one warning line (nothing harder —
    the rewrite discipline lives in the prompt, user call 2026-07-05).
    Worker contexts never render this section (they read .drafts only
    via their own progress-note slots)."""
    from Tooling.pipeline import _drafts
    _insert_problem(conn)
    _insert_root(conn)
    pdir = workspace / "Problems" / "p"
    (pdir / ".drafts").mkdir(parents=True, exist_ok=True)
    _drafts.plan_note_path(pdir).write_text("serial plan: (i) x (ii) y",
                                            encoding="utf-8")
    lines = phase2_context._section_plan_note(workspace, "p")
    text = "\n".join(lines)
    assert "## Your plan note (private, cross-wake)" in text
    assert "serial plan: (i) x (ii) y" in text
    assert "past the useful size" not in text
    # over the soft cap → one warning line
    _drafts.plan_note_path(pdir).write_text(
        "x" * (_drafts.PLAN_NOTE_SOFT_CAP + 1), encoding="utf-8")
    text2 = "\n".join(phase2_context._section_plan_note(workspace, "p"))
    assert "past the useful size" in text2

    # integration: the strategist compile carries the section
    attempts_dir = tmp_path / "_att_strat"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    assert "## Your plan note (private, cross-wake)" in out.read_text(
        encoding="utf-8")


def test_tree_inline_keeps_pure_nl_forest(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Phase 7 regression (~8 strategist reports): the fallback test
    `"no root goal" in body` also matched tree.py's pure-NL forest header,
    DISCARDING the whole deliverable-forest render on every wake. A
    pure-NL problem with goals must surface its forest, not the
    '(TREE.md not yet generated)' stub."""
    _insert_problem(conn)
    db.insert_goal(conn, problem="p", slug="brick_a",
                   lean_path="P/L_brick_a.lean", statement="A",
                   origin="forward", depth=0)
    lines = phase2_context._section_tree_inline(conn, workspace, "p")
    text = "\n".join(lines)
    assert "(TREE.md not yet generated)" not in text
    assert "brick_a" in text
