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
from Tooling.state import db, intent as intent_mod


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mfst() -> intent_mod.ProblemIntent:
    return intent_mod.ProblemIntent(problem="p", charter="T")


def _insert_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES (?, ?, 1)", (name, db.now()),
    )
    conn.commit()


def _insert_root(conn: sqlite3.Connection, slug: str = "main") -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=f"P/{slug}.lean",
        statement="T", origin="root", depth=0,
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

def test_batch_done_wake_carries_the_review_dossiers(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """Owner design 2026-08-26 (wake merge): the review-discharge rule
    already FORCES a batch_done wake to rule on pending-review goals —
    it was ruling BLIND (the dossier was gated on the pending_review
    trigger). Every non-routine wake now carries every waiting goal's
    dossier, capped, with one-liners + lazy pointers beyond the cap;
    the routine survey stays dossier-free."""
    _insert_problem(conn)
    ids = []
    for i in range(_ctx_cap() + 2):
        gid = _insert_root(conn, slug=f"rev_{i}")
        conn.execute("UPDATE goals SET status='pending_strategist_review'"
                     " WHERE id=?", (gid,))
        ids.append(gid)
    conn.commit()
    attempts_dir = tmp_path / "_attempts_bd"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    text = out.read_text(encoding="utf-8")
    for i in range(_ctx_cap()):
        assert f"rev_{i}" in text, f"dossier for goal #{i} missing"
    assert "More goals awaiting your review" in text
    for gid in ids[_ctx_cap():]:
        assert f"g{gid}" in text, "overflow one-liner missing"
    # the routine survey is exempt from the discharge rule and from
    # the dossiers alike
    out2 = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    assert "More goals awaiting your review" not in out2.read_text(
        encoding="utf-8")


def _ctx_cap() -> int:
    return phase2_context._REVIEW_DOSSIER_CAP


def test_pending_review_surfaces_backward_shelve_proposal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" in text
    assert "agent_shelved" in text
    # The brief is the review's primary evidence and it rides the
    # companion WHOLE (2026-08-11). Inline it was head-truncated, and the
    # cap had already been raised 1500 -> 4000 once because it sliced
    # real proposals mid-signature — raising a cap only delays that, so
    # the cap is gone and the pointer replaces it.
    assert "PAST_DIRECT_ATTEMPTS.md" in text
    companion = (attempts_dir / "PAST_DIRECT_ATTEMPTS.md").read_text(
        encoding="utf-8")
    for needle in ("Needed Forward lemmas", "lineThrough", "perpFoot"):
        assert needle in companion, needle


def test_pending_review_surfaces_existing_strategy_content(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Existing strategies on this goal" in text
    assert f"s{sid}" in text
    assert "Kelly minimiser split" in text
    assert "status=`dead`" in text


def test_pending_review_walks_ancestor_chain_to_root(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=leaf,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Ancestor chain" in text
    assert "`mid`" in text
    assert "`main`" in text
    assert "(ROOT)" in text


def test_root_pending_review_marks_self_root_chain(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
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
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" not in text
    assert "### Existing strategies on this goal" not in text
    assert "### Ancestor chain" not in text
    assert "should not appear in routine context" not in text


def test_fresh_problem_routine_context_omits_review_sections(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """A fresh problem's non-review wake: bootstrap context, no review
    target. (Phase 6: first_launch retired; routine stands in.)"""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
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

    lines = phase2_context._section_active_goals(conn, workspace, "p")
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

    lines = phase2_context._section_active_goals(conn, workspace, "p")
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


def _seed_decision(conn: sqlite3.Connection, *, kind: str, outcome: str,
                   detail: str, problem: str = "p") -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, outcome_detail, created_at, updated_at)"
        " VALUES (?, 0, 'routine', ?, NULL, NULL, NULL, ?, NULL,"
        "         ?, ?, ?, ?)",
        (problem, kind, "{}", outcome, detail, ts, ts))
    conn.commit()
    return int(cur.lastrowid)


def test_recent_decisions_show_detail_whatever_the_outcome_is_called(
    conn: sqlite3.Connection,
) -> None:
    """The replay's WHY line used to fire only on outcomes named
    `failed:*`, and only that family follows the prefix convention.
    `paper_unfetchable` carries the entire Scholar report — identity,
    DOI, why no whitelisted copy exists — and was mute in all 17 rows
    on 2026-08-14, so a group read the silence as "the fetch never
    ran" and planned to spend a batch re-fetching it."""
    _insert_problem(conn)
    _seed_decision(
        conn, kind="FetchPaper", outcome="paper_unfetchable",
        detail="Identity resolved: T. P. Vaughan, EJC 23 (2002) 851-860."
               " No arXiv-class copy exists; only ScienceDirect, which is"
               " not on the fetch whitelist.")
    text = "\n".join(phase2_context._section_failure_replay(conn, "p"))
    assert "why:" in text
    assert "not on the fetch whitelist" in text


def test_a_long_outcome_detail_keeps_its_tail(
    conn: sqlite3.Connection,
) -> None:
    """Head truncation hides what the author put last, and Scholar puts
    the actionable half there: why it cannot be fetched, and the URL a
    human can open. This section has no companion file to fall back
    on, so the elision has to take the middle."""
    _insert_problem(conn)
    head = "IDENTITY " + "x" * 900
    tail = " best human URL: https://doi.org/10.1006/eujc.2002.0586"
    _seed_decision(conn, kind="FetchPaper", outcome="paper_unfetchable",
                   detail=head + tail)
    text = "\n".join(phase2_context._section_failure_replay(conn, "p"))
    assert "IDENTITY" in text, "lost the head"
    assert "10.1006/eujc.2002.0586" in text, "lost the tail"
    assert "……" in text, "expected a middle elision, not a cut end"


def test_recent_decisions_do_not_call_a_parked_step_dispatched(
    conn: sqlite3.Connection,
) -> None:
    """The replay's no-outcome arm read `[IN FLIGHT — dispatched, no
    result yet]` off an empty column. A step whose product the
    Strategist parked keeps that column empty for good (a shelved goal
    never settles its inject — P13 4284), so the replay told the
    Strategist a goal it had shelved was out with a worker."""
    _insert_problem(conn)
    gid = _seed_shelved_goal(conn, slug="g_parked")
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', NULL, 'b', NULL, '{}',"
        "         'batch-parked', ?, NULL, ?, ?)", (gid, ts, ts))
    conn.commit()
    text = "\n".join(phase2_context._section_failure_replay(conn, "p"))
    assert "IN FLIGHT" not in text, text
    assert "PARKED" in text, text


def test_batch_outcomes_filter_non_inject_and_flag_unattributed(
    conn: sqlite3.Connection,
) -> None:
    """2026-07-15: (a) non-Inject siblings sharing the wake's batch_id
    rendered as brief-less phantom 'step 0' rows — filtered; (b) a
    success step with no produced_goal_id (renamed/merged landing) now
    says so explicitly instead of omitting the landed line."""
    _insert_problem(conn)
    _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-mix",
        briefs=["## Deliver\n`brick_x` : stuff"], outcomes=["success"],
    )
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'EmitDirective', NULL, NULL,"
        "         'notes', '{}', 'batch-mix', 'committed', ?, ?)",
        (ts, ts))
    conn.commit()
    lines = phase2_context._section_inject_batch_outcomes(conn, "p")
    body = "\n".join(lines)
    assert "(1 steps)" in body            # EmitDirective row filtered out
    assert body.count("**step") == 1
    assert "nothing attributed to this step" in body  # NULL produced_goal


def test_inject_batch_done_surfaces_briefs_and_outcomes(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
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
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "why:" in text
    assert "extDerivWithin_apply" in text


def test_inject_batch_done_surfaces_landed_decl(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """Each completed step with a `produced_goal_id` shows the decl that
    actually landed (slug + status + statement) — kernel truth, so the
    Strategist stops guessing which decl a `success` step became
    (feedback 2026-07-04, the section's biggest complaint)."""
    _insert_problem(conn)
    _insert_root(conn)
    ids = _seed_inject_batch_done(
        conn, batch_id="batch-landed",
        briefs=["land the band augmentation bridge"], outcomes=["success"])
    gid = db.insert_goal(
        conn, problem="p", slug="band_aug_bridge",
        lean_path="Problems/p/proofs/L_band_aug_bridge.lean",
        statement="aug_band = aug_sphere ∘ band_iso", origin="forward",
        status="proved")
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id=? WHERE id=?",
        (gid, ids[0]))
    conn.commit()
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "landed: `band_aug_bridge` (status=proved)" in text
    assert "aug_band = aug_sphere ∘ band_iso" in text


def test_inject_batch_section_omitted_when_no_unack_batch(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """Without any unack batch, the section doesn't appear (defensive —
    rendering must not show stale data)."""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" not in text


def test_routine_trigger_shows_unack_batch_section(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "Batch `batch-Y" in text
    assert "lemma A" in text


def test_pending_review_trigger_shows_unack_batch_section(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Completed Inject batches" in text
    assert "Batch `batch-Z" in text


def test_inject_batch_section_omits_produced_lemma(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
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


def test_pending_reopens_fires_when_the_promised_helper_is_parked(
    conn: sqlite3.Connection,
) -> None:
    """A promise waits on work, and a parked helper is not work. The
    suppression read `outcome IS NULL` as "still in flight", but a
    helper whose own goal got shelved keeps that column NULL forever
    (P13 4284) — so the promise never came due and the parked goal that
    was waiting on it never surfaced again."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_promised")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-parked-helper",
        inject_outcomes=["success"],
    )
    helper = _seed_shelved_goal(conn, slug="g_helper")
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Inject', NULL, 'helper',"
        "         NULL, '{}', 'batch-parked-helper', ?, NULL, ?, ?)",
        (helper, ts, ts))
    conn.commit()
    body = "\n".join(phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done"))
    assert "g_promised" in body, body


def test_pending_reopens_waits_on_a_live_delegate(
    conn: sqlite3.Connection,
) -> None:
    """v35 seam (2026-08-06, live on the Frankl opener): a park waiting
    on a sub-group is a promise too. With only 'Inject' counted, the
    batch's mints resolving made the shelved goal surface as "due"
    while the Delegate (the actual wait target) was still open. A
    Delegate with outcome NULL suppresses surfacing; its terminal
    outcome (filled by the group's terminal transition) makes the
    promise due. A shelve batched with ONLY a Delegate is also a
    promise batch."""
    _insert_problem(conn)
    _insert_root(conn)
    ts = db.now()
    # Case A: mint landed, delegate still open → suppressed.
    g1 = _seed_shelved_goal(conn, slug="g_waits_group")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g1, batch_id="batch-dlg",
        inject_outcomes=["success"])
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, outcome, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Delegate', 'batch-dlg',"
        " NULL, '{}', ?, ?)", (ts, ts))
    conn.commit()
    assert phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done") == []
    # Group terminal → outcome filled → due, surfaces.
    conn.execute(
        "UPDATE strategist_decisions SET outcome='failed:returned'"
        " WHERE decision_kind='Delegate' AND batch_id='batch-dlg'")
    conn.commit()
    body = "\n".join(phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done"))
    assert "g_waits_group" in body
    # Case B: shelve batched with ONLY a Delegate is promise-bearing.
    g2 = _seed_shelved_goal(conn, slug="g_delegate_only")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " payload, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'ConfirmShelve', ?,"
        " 'batch-dlg2', 'success', '{}', ?, ?)", (str(g2), ts, ts))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, outcome, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Delegate', 'batch-dlg2',"
        " NULL, '{}', ?, ?)", (ts, ts))
    conn.commit()
    body2 = "\n".join(phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done"))
    assert "g_delegate_only" not in body2   # group live → waiting


def test_pending_reopens_suppresses_after_already_addressed(
    conn: sqlite3.Connection,
) -> None:
    """A re-ConfirmShelve is the Strategist's ANSWER to the surfaced
    promise, not a new promise (2026-07-14, goal 5941: every wake's
    decisions share one batch_id, so a terminal re-confirm co-batched
    with an unrelated forced-advance Inject used to read as a fresh
    pairing and re-arm this section forever). After the answer the
    goal never re-surfaces; only a Reopen starts a new promise cycle
    (brouwer g2771 re-ConfirmShelve x4 is also covered — the first
    surfacing is answered once)."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_addressed")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-first",
        inject_outcomes=["success"],
    )
    # Strategist answered the surfaced promise with a re-confirm; the
    # co-batched Inject is unrelated forced-advance work.
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="batch-second",
        inject_outcomes=["success"],
    )
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    assert "g_addressed" not in "\n".join(lines)


def test_pending_reopens_reopen_starts_a_new_promise_cycle(
    conn: sqlite3.Connection,
) -> None:
    """Reopen resets the promise clock: the first ConfirmShelve AFTER
    the goal's latest Reopen is a genuine new pairing and surfaces
    when its batch completes — even though older answered
    ConfirmShelves exist."""
    _insert_problem(conn)
    _insert_root(conn)
    g = _seed_shelved_goal(conn, slug="g_reshelved")
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="cycle1-promise",
        inject_outcomes=["success"],
    )
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="cycle1-answer",
        inject_outcomes=["success"],
    )
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Reopen', ?, NULL,"
        "         'new tools landed', '{}', 'cycle2-reopen', NULL, ?, ?)",
        (str(g), ts, ts),
    )
    conn.commit()
    _seed_confirmshelve_with_inject_batch(
        conn, goal_id=g, batch_id="cycle2-promise",
        inject_outcomes=["success"],
    )
    lines = phase2_context._section_pending_reopens(
        conn, "p", "inject_batch_done")
    body = "\n".join(lines)
    assert body.count("g_reshelved") == 1
    assert "cycle2-promise" in body or "g_reshelved" in body


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
    # 2026-07-13 (user wording): the header binds subtraction into the
    # definition of every update — agents add by default and never
    # subtract unless reminded.
    assert "Curate, don't accumulate" in body


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
    assert phase2_context._section_plan_note(conn, workspace, "p") == []


def test_plan_note_section_renders_and_warns_over_cap(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
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
    lines = phase2_context._section_plan_note(conn, workspace, "p")
    text = "\n".join(lines)
    assert "## Your plan note (private, cross-wake)" in text
    assert "serial plan: (i) x (ii) y" in text
    assert "past the useful size" not in text
    # over the soft cap → one warning line
    _drafts.plan_note_path(pdir).write_text(
        "x" * (_drafts.PLAN_NOTE_SOFT_CAP + 1), encoding="utf-8")
    text2 = "\n".join(phase2_context._section_plan_note(conn, workspace, "p"))
    assert "past the useful size" in text2

    # integration: the strategist compile carries the section
    attempts_dir = tmp_path / "_att_strat"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    assert "## Your plan note (private, cross-wake)" in out.read_text(
        encoding="utf-8")


def test_plan_note_is_lazy_when_attempts_dir_given(
    workspace: Path, conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """2026-08-04 operator ruling (#2 context growth source): with an
    attempts_dir the full note rides as `_plan_full.md` beside
    Context.md; inline keeps only the provenance line, the pointer,
    and the `SUSPECT:` lines. Without an attempts_dir (legacy callers)
    the full inline render stands."""
    from Tooling.pipeline import _drafts
    _insert_problem(conn)
    pdir = workspace / "Problems" / "p"
    (pdir / ".drafts").mkdir(parents=True, exist_ok=True)
    note = ("## Facts\n- lemma A proved (s12)\n"
            "- SUSPECT: the wall is only in the g=2 case\n"
            "long body " * 50)
    _drafts.plan_note_path(pdir).write_text(note, encoding="utf-8")
    att = tmp_path / "att"
    att.mkdir()
    text = "\n".join(phase2_context._section_plan_note(
        conn, workspace, "p", attempts_dir=att))
    companion = att / phase2_context.PLAN_NOTE_COMPANION
    assert companion.read_text(encoding="utf-8") == note
    assert "_plan_full.md" in text
    assert "SUSPECT: the wall is only in the g=2 case" in text
    assert "long body" not in text          # the bulk stays lazy
    assert "lemma A proved" not in text     # non-SUSPECT facts too


def test_plan_note_carries_framework_provenance(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The note is persisted right after the spawn — before the package
    gate / Adversary / commit decide whether that batch ships — so a
    discarded batch leaves a note asserting a state that never existed
    (07-29 SG: two wakes burned on forensics, and the agent's own
    workaround was a standing "do not trust your prior plan note"
    rule). The render carries the framework's record of what actually
    committed: batch id + Programme rev."""
    from Tooling.pipeline import _drafts
    from Tooling.state import programme
    _insert_problem(conn)
    _insert_root(conn)
    pdir = workspace / "Problems" / "p"
    (pdir / ".drafts").mkdir(parents=True, exist_ok=True)
    _drafts.plan_note_path(pdir).write_text(
        "State after batch 2 dispatch (Programme rev 2)",
        encoding="utf-8")

    # nothing committed yet → says so, so a phantom batch is visible
    text = "\n".join(phase2_context._section_plan_note(conn, workspace, "p"))
    assert "no batch committed" in text
    assert "no Programme rev" in text

    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, triggered_at_tick, trigger_kind, decision_kind,"
        "  batch_id, created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject', 'batch-1',"
        "         '2026-07-30T01:02:03Z', '2026-07-30T01:02:03Z')")
    programme.record_pass(
        conn, "p", "# T\n## Argument\na\n## Proof\np\n## Roadmap\nr\n",
        {"verdict": "pass"}, [], 0, "batch-1")
    conn.commit()
    text = "\n".join(phase2_context._section_plan_note(conn, workspace, "p"))
    assert "batch-1" in text and "Programme rev 1" in text


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
    # the roster moved to `## Active goals` (backlog item d, 2026-08-26)
    # — the forest surfaces through the counters here
    assert "1 open" in text


def test_tree_inline_lists_only_live_goals(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """2026-08-18 context diet: the 07-13 'exception list' premise
    (non-proved goals are a handful) broke on a mature descent tree —
    164 rows / 9KB, mostly a shelved graveyard that TREE.md's by-status
    sections already carry with ancestor paths. The inline list keeps
    only live statuses; the census survives in the counters and the
    pointer names the lazy home."""
    _insert_problem(conn)
    for slug, status in (
            ("g_open", "open"), ("g_att", "attempting"),
            ("g_rev", "pending_strategist_review"),
            ("g_shelved", "shelved"), ("g_dis", "disproved"),
            ("g_frozen", "frozen"), ("g_proved", "proved")):
        db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"P/L_{slug}.lean", statement="S",
                       origin="forward", status=status)
    text = "\n".join(
        phase2_context._section_tree_inline(conn, workspace, "p"))
    # Backlog item d (2026-08-26): the alive roster left this section
    # entirely — it was the byte-isomorphic twin of `## Active goals`
    # (the 08-24 autopsy's dominant "surfaces disagree" pair). Counters
    # keep the census; the pointer names the lazy home; NO slugs here.
    for s in ("g_open", "g_att", "g_rev",
              "g_shelved", "g_dis", "g_frozen", "g_proved"):
        assert f"`{s}`" not in text, s
    assert "1 shelved" in text and "1 disproved" in text, (
        "the counters must keep the full census")
    assert "1 open" in text
    assert "## Shelved" in text, "the pointer must name the lazy home"


def test_delivered_vs_briefed_is_not_decided_by_a_regex(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """User ruling 2026-08-07: no mechanical checking of natural
    language. "Did the worker deliver what I briefed" was decided by
    searching the brief's PROSE for the landed slug, so the framework's
    own convention — briefs name the file `L_<slug>`, the theorem lands
    as `<slug>` — cried RETARGETED on correct work (24 complaints in one
    run, each ordering the reader to diff a brick that matched). The
    scoreboard now states the facts (landed slug, status, whole
    signature, and where the whole brief is) and the Strategist judges."""
    _insert_problem(conn)
    _insert_root(conn)
    ids = _seed_inject_batch_done(
        conn, batch_id="batch-retgt",
        briefs=["## Need\ntheorem f_pos : 0 < f n s",
                "## Need\ntheorem g_mono : Monotone g"],
        outcomes=["success", "success"])
    for i, (slug, stmt) in enumerate(
            [("exists_fiber_count_eq", "∃ k, fiber k = f n s"),
             ("g_mono", "Monotone g")]):
        gid = db.insert_goal(
            conn, problem="p", slug=slug,
            lean_path=f"Problems/p/proofs/L_{slug}.lean",
            statement=stmt, origin="forward", status="proved")
        conn.execute(
            "UPDATE strategist_decisions SET produced_goal_id=? WHERE id=?",
            (gid, ids[i]))
    conn.commit()
    attempts_dir = tmp_path / "_attempts_retgt"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    # No verdict is manufactured either way — for the step whose brief
    # never names the landed slug, or for the one where it does.
    assert "RETARGETED" not in text
    assert "RENAMED" not in text
    # What the Strategist needs to judge IS there: both landed slugs
    # with their status, and a pointer to the untruncated briefs.
    assert "landed: `exists_fiber_count_eq`" in text
    assert "landed: `g_mono`" in text
    assert "BATCHES.md" in text


def test_batch_scoreboard_surfaces_recent_declines(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """2026-07-19 (b6_1 growth_exponent re-mint): a decline's math
    reasoning lived only in per-goal surfaces and a cousin branch
    re-invented the refuted statement. Declines newer than the last
    strategist decision now ride the batch scoreboard; the decline's
    proposal_md (the math) is the rendered text."""
    _insert_problem(conn)
    _insert_root(conn)
    _seed_inject_batch_done(
        conn, batch_id="batch-dcl", briefs=["b"], outcomes=["success"])
    gid = db.insert_goal(
        conn, problem="p", slug="growth_exp_flawed",
        lean_path="Problems/p/proofs/L_growth_exp_flawed.lean",
        statement="1 <= liminf ...", origin="backward", status="shelved")
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES ('pid-dcl', 'Backward',"
        " ?, 'Goal', 'failed', 'agent_declined', ?, ?)",
        (str(gid), db.now(), db.now()))
    conn.commit()
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-dcl",
        failure_reason="parent_needs_fix",
        failure_detail="backward declined: return_to_parent",
        proposal_md="-- decline: return_to_parent -- statement FALSE "
                    "without the gap hypothesis; counterexample g = 2^n")
    attempts_dir = tmp_path / "_attempts_dcl"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "Worker declines since your last wake" in text
    assert "counterexample g = 2^n" in text
    assert "growth_exp_flawed" in text


def test_a_decline_reaches_the_strategist_with_its_ask_intact(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """The head-truncated version cut at 250 characters against a
    measured median of 1,250, so 79% of declines arrived clipped — and
    clipped at the head, which holds the diagnosis, never the ask.
    Production 2026-08-11: a worker wrote 1,095 characters ending
    "please re-state this sub-goal with (hUW : …) added"; the
    Strategist got the first 250, stopping mid-expression."""
    _insert_problem(conn)
    _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="count_missing_hyp",
        lean_path="Problems/p/proofs/L_count_missing_hyp.lean",
        statement="3 <= s", origin="backward", status="shelved")
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES ('pid-hyp', 'Backward',"
        " ?, 'Goal', 'failed', 'agent_declined', ?, ?)",
        (str(gid), db.now(), db.now()))
    conn.commit()
    ask = ("Please re-state this sub-goal with (hUW : forall Y in U, "
           "Y subset W) added to the hypothesis list.")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-hyp",
        failure_reason="parent_needs_fix",
        failure_detail="backward declined: return_to_parent",
        proposal_md="-- decline: return_to_parent -- " + ("derivation. " * 60)
                    + ask)
    attempts_dir = tmp_path / "_attempts_hyp"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None)
    text = out.read_text(encoding="utf-8")
    assert ask in text                       # the ask, verbatim
    assert "elided" not in text              # ~800 chars: nothing dropped


def test_a_decline_past_the_budget_keeps_both_ends() -> None:
    """The writer side is unbounded, so the budget has to bite
    eventually — but it takes the derivation out of the middle, never
    the conclusion off the end."""
    body = "DIAGNOSIS. " + ("derivation. " * 400) + "THE ASK."
    out = phase2_context._elide_middle(
        body, phase2_context.DECLINE_INLINE_CHARS)
    assert out.startswith("DIAGNOSIS.")
    assert out.endswith("THE ASK.")
    assert "elided" in out
    assert len(out) <= phase2_context.DECLINE_INLINE_CHARS


def test_the_decline_budget_covers_the_measured_distribution() -> None:
    """Chosen against 196 real declines: median 1,250, p90 2,348. A
    budget under p90 would put the common case back in the elided
    branch, which is where this bug lived."""
    assert phase2_context.DECLINE_INLINE_CHARS >= 2000


def test_a_normalized_slug_rename_is_narrated_by_nobody(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """The RENAMED marker went out with RETARGETED (user ruling
    2026-08-07: no mechanical checking of natural language). It was the
    kinder half of the same regex — reading a brief's prose to guess
    whether `isPerfectCube` and `is_perfect_cube` are the same intent —
    and a guess is exactly what the Strategist is there to make. The
    facts it needs stay: what landed, and where the whole brief is."""
    _insert_problem(conn)
    _insert_root(conn)
    ids = _seed_inject_batch_done(
        conn, batch_id="batch-rename",
        briefs=["## Need\nMint `isPerfectCube` as the anchor def"],
        outcomes=["success"])
    gid = db.insert_goal(
        conn, problem="p", slug="is_perfect_cube",
        lean_path="Problems/p/proofs/L_is_perfect_cube.lean",
        statement="Prop", origin="forward", status="proved")
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id=? WHERE id=?",
        (gid, ids[0]))
    conn.commit()
    attempts_dir = tmp_path / "_attempts_rename"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None)
    text = out.read_text(encoding="utf-8")
    assert "RENAMED" not in text
    assert "RETARGETED" not in text
    assert "landed: `is_perfect_cube`" in text


def test_outcome_line_reads_full_signature_for_def(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """07-29 (C): the DB statement for a def is its RESULT TYPE (`Prop`)
    — arity is invisible and fueled the verdict war. The outcome line
    must read the full signature off the landed file when reachable."""
    _insert_problem(conn)
    _insert_root(conn)
    ids = _seed_inject_batch_done(
        conn, batch_id="batch-sig",
        briefs=["## Need\nanchor def `is_cube`"], outcomes=["success"])
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True, exist_ok=True)
    full = "def is_cube (n : ℕ) : Prop := ∃ k, n = k ^ 3"
    (pdir / "L_is_cube.lean").write_text(
        "namespace Problems.p\n" + full + "\nend Problems.p\n",
        encoding="utf-8")
    gid = db.insert_goal(
        conn, problem="p", slug="is_cube",
        lean_path="Problems/p/proofs/L_is_cube.lean",
        statement="Prop", origin="forward", status="proved", kind="def")
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id=? WHERE id=?",
        (gid, ids[0]))
    conn.commit()
    attempts_dir = tmp_path / "_attempts_sig"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None)
    text = out.read_text(encoding="utf-8")
    assert full in text


def test_section_programme_proof_renders_current_rev(
    conn: sqlite3.Connection,
) -> None:
    """07-30 audit item 4: the mint context carries the Programme's
    `## Proof` so intake's falsification check has a source independent
    of the brief (written by the same Strategist whose transcription
    slips it exists to catch). The header always renders — "(none yet)"
    pre-bootstrap, mirroring the FORBIDDEN_LEMMAS precedent."""
    from Tooling.state import programme
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)",
        (db.now(),))
    conn.commit()
    out = phase2_context._section_programme_proof(conn, "p")
    assert out[0] == "## Programme Proof"
    assert "(none yet)" in out[1]
    body = ("# Rev one\n\n## Argument\n\nBecause.\n\n"
            "## Proof\n\nThe argued mathematics body.\n\n"
            "## Roadmap\n\n1. next\n")
    programme.record_pass(conn, "p", body, verdict={}, dialogue=[],
                          rounds=0, batch_id=None)
    out = phase2_context._section_programme_proof(conn, "p")
    assert out[0].startswith("## Programme Proof (rev 1")
    assert any("The argued mathematics body." in ln for ln in out)


def test_ingest_gate_states_the_ordering_cost_ungated(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The ordering advice used to render only for a `frozen` root — so
    on b6_1 (07-30) it never appeared, and its wording forbade a
    same-batch root Inject, which #123 made legal and efficient (the
    commit gate registers a wait edge; the root's assembly landed and
    parked on two edges). It now renders for any unproved root and
    states the real cost instead of a prohibition: a citer dispatched
    before its citees cannot read their exact statements."""
    _insert_problem(conn)
    _insert_root(conn)
    text = "\n".join(phase2_context._section_ingest_gate(conn, "p"))
    assert "Land a goal's cited prerequisites before dispatching it" in text
    assert "pin their exact signatures in the brief" in text
    # retired pipeline vocabulary is gone from every strategist surface
    assert "Backward" not in text and "Builder" not in text


def test_ingest_gate_states_the_axiom_gate_once_reachable(
    workspace: Path, conn: sqlite3.Connection, mfst: intent_mod.ProblemIntent,
) -> None:
    """The exit gate must not ask for a certification it also hides.

    `.lake/build` is outside the Strategist's readable roots, so the one
    wake that has to certify the Manifest's axiom obligation could only
    grep sources for `sorry` and left a `SUSPECT:` line on its own
    `Ingest` (2026-08-02 feedback). The probe it wanted has already run —
    `#print axioms <= whitelist` IS the definition of `proved` here — so
    the section states that instead, and only once Ingest is reachable."""
    _insert_problem(conn)
    root = _insert_root(conn)
    mfst.axioms_whitelist = ["propext", "Classical.choice"]
    # Root unproved: this is the "unavailable" note, not the certification.
    blocked = "\n".join(
        phase2_context._section_ingest_gate(conn, "p", intent=mfst))
    assert "Axiom certification" not in blocked

    db.update_goal_status(conn, root, "proved")
    conn.commit()
    text = "\n".join(
        phase2_context._section_ingest_gate(conn, "p", intent=mfst))
    assert "## Axiom certification (already machine-checked)" in text
    assert "`propext`" in text and "`Classical.choice`" in text
    assert "not expected to re-run the probe" in text


def test_strategist_surfaces_carry_no_retired_pipeline_names(
    workspace: Path, conn: sqlite3.Connection, mfst: intent_mod.ProblemIntent,
    tmp_path: Path,
) -> None:
    """v33 hard-wired every Inject to the Formalizer, but the
    strategist-facing text kept teaching `Inject(Backward|Builder ...)`
    and "no Backward/Builder/Forward worker in flight" — and the
    b6_1 Programme rev1 duly planned for a "Backward worker" that does
    not exist. The decision object still tolerates a `pipeline` field,
    so nothing failed loudly; only a pin keeps it gone."""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_att_vocab"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=None,
    ).read_text(encoding="utf-8")
    for dead in ("Inject(Backward", "Inject(Builder", "Inject(Forward)",
                 "Backward/Builder"):
        assert dead not in out, dead


def test_batch_outcomes_go_lazy_instead_of_truncating(
    workspace: Path, conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The brief and the worker's reply move to `BATCHES.md`, whole.

    Inline they were cut at 1200 bytes, and briefs run 1.2-9.5KB — the cut
    landed mid-sentence, once on the exact line the Adversary had
    criticised (2026-08-02). Lazily loaded there is nothing to truncate
    (operator ruling), which is the pattern CATALOG / LESSONS / PAST_*
    already use. The scoreboard stays inline: it is what cannot be
    re-derived from a file."""
    _insert_problem(conn)
    _insert_root(conn)
    long_brief = "Roadmap: the brick\n## Need\n" + ("x" * 4000) + "\nTAILMARK"
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id, outcome,"
        " outcome_detail, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', ?, '{}', 'b-lazy',"
        "         'success', ?, ?, ?)",
        (long_brief, "why " + ("y" * 4000) + " REPLYMARK",
         db.now(), db.now()))
    conn.commit()

    attempts = tmp_path / "_att_lazy"
    attempts.mkdir()
    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", attempts_dir=attempts))

    companion = attempts / phase2_context.BATCHES_COMPANION
    assert companion.exists()
    body = companion.read_text(encoding="utf-8")
    # whole, both halves, no ellipsis
    assert "TAILMARK" in body and "REPLYMARK" in body
    # the inline section points at it and does NOT carry the bodies
    assert phase2_context.BATCHES_COMPANION in text
    assert "TAILMARK" not in text and "REPLYMARK" not in text
    assert len(text) < 1200, f"scoreboard should stay small:\n{text}"


def test_batch_outcomes_still_render_without_an_attempts_dir(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """No companion to write → the old inline shape, so a caller that
    cannot host a file still gets the record rather than nothing."""
    _insert_problem(conn)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', 'INLINEMARK', '{}',"
        "         'b-inline', 'success', ?, ?)", (db.now(), db.now()))
    conn.commit()
    text = "\n".join(
        phase2_context._section_inject_batch_outcomes(conn, "p"))
    assert "INLINEMARK" in text


def test_workers_receive_conventions_on_both_dispatch_paths(
    workspace: Path, conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """RS-B: the Conventions section reaches BOTH worker shapes.

    Goal jobs resolve through the goal's owning group; mints resolve
    through the Inject decision's authoring group. The mint path matters
    doubly: the old directive was never in the mint section list at all
    — SLC's namespace convention was briefed, unfollowed, and retired as
    'unfollowed' while a brick died on exactly that gap."""
    from Tooling.state import programme, groups
    from Tooling.agent import context as worker_context
    _insert_problem(conn)
    top = groups.ensure_top_group(conn, "p")
    programme.record_pass(
        conn, "p",
        "# T\n## Argument\na\n## Proof\np\n## Roadmap\nr\n"
        "## Conventions\nNEVER nest a namespace\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)

    # Mint path: decision row carries the authoring group.
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, brief, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', ?, '## Need\nx', '{}',"
        " ?, ?)", (top, db.now(), db.now()))
    did = int(cur.lastrowid)
    conn.commit()
    lines = phase2_context._section_conventions_for_decision(conn, "p", did)
    text = "\n".join(lines)
    assert "NEVER nest a namespace" in text

    # Goal-job path: goal → owning group → same conventions.
    gid = _insert_root(conn)
    lines2 = worker_context._section_strategist_directive(
        conn, "p", goal_id=gid)
    assert "NEVER nest a namespace" in "\n".join(lines2)


def test_what_a_step_left_lands_in_the_companion_not_the_scoreboard(
    workspace: Path, conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """`outcome` records how the worker EXITED. The Strategist is told to
    read the scoreboard mechanically, and the two are routinely opposite:
    2026-08-11 a step labelled `failed:dead` had left a `proposed`
    strategy with one brick proved and one open child, so the wake
    "re-dispatched work that already landed and missed leaves that were
    ready" and every fact it acted on came from re-reading TREE.md.

    The artifacts go to the LAZY layer, not inline: they are re-derivable
    by reading the DB or the tree, which is this companion's admission
    criterion, and the Context was slimmed the session before."""
    _insert_problem(conn)
    _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="parent_brick",
        lean_path="Problems/p/proofs/L_parent_brick.lean",
        statement="P", origin="backward", status="attempting")
    sub_ok = db.insert_goal(
        conn, problem="p", slug="child_landed",
        lean_path="Problems/p/proofs/L_child_landed.lean",
        statement="A", origin="backward", status="proved")
    sub_open = db.insert_goal(
        conn, problem="p", slug="child_open",
        lean_path="Problems/p/proofs/L_child_open.lean",
        statement="B", origin="backward", status="open")
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'pid-x', ?)", (gid, db.now()))
    sid = int(cur.lastrowid)
    conn.executemany(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, ?)", [(sid, sub_ok, 0), (sid, sub_open, 1)])
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id, outcome,"
        " produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', 'b', '{}', 'b-art',"
        "         'failed:dead', ?, ?, ?)", (gid, db.now(), db.now()))
    conn.commit()

    attempts = tmp_path / "_att_art"
    attempts.mkdir()
    inline = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", attempts_dir=attempts))
    companion = (attempts / phase2_context.BATCHES_COMPANION).read_text(
        encoding="utf-8")

    # the artifacts the label hides are in the companion...
    assert "what it left" in companion
    assert f"s{sid}" in companion and "proposed" in companion
    assert "child_landed" in companion and "1/2 sub-goals proved" in companion
    assert "child_open" in companion
    # ...and the scoreboard did not grow to carry them
    assert "child_landed" not in inline
    assert "what it left" not in inline


def test_a_step_with_no_strategy_adds_nothing() -> None:
    """No artifacts, no header — an empty section is worse than none in a
    file the agent pays to open."""
    import sqlite3 as _sq
    c = _sq.connect(":memory:")
    c.row_factory = _sq.Row
    c.execute("CREATE TABLE strategies (id INTEGER PRIMARY KEY, goal_id INT,"
              " status TEXT)")
    row = {"produced_goal_id": 99}

    class _R(dict):
        def keys(self):
            return super().keys()

    assert phase2_context._step_artifact_lines(c, _R(row)) == []
    assert phase2_context._step_artifact_lines(
        c, _R({"produced_goal_id": None})) == []


# ---------------------------------------------------------------------
# Adjudication history (owner design 2026-08-25) — one sentence per
# ruling inline, full text lazily loaded, cited waiters named.
# ---------------------------------------------------------------------

def _insert_ruling(conn: sqlite3.Connection, *, target_id: int,
                   group_id: int, kind: str = "ConfirmShelve",
                   reason: str = "") -> None:
    # one top group per problem (partial unique index) — ruling groups
    # hang under a fixed top so several can coexist
    conn.execute(
        "INSERT OR IGNORE INTO groups (id, problem, charter, status,"
        " created_at, updated_at) VALUES (1, 'p', '', 'active', ?, ?)",
        (db.now(), db.now()))
    conn.execute(
        "INSERT OR IGNORE INTO groups (id, problem, parent_group_id,"
        " charter, status, created_at, updated_at)"
        " VALUES (?, 'p', 1, '', 'active', ?, ?)",
        (group_id, db.now(), db.now()))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, reason,"
        " payload, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', ?, ?, ?, ?, '{}', ?, ?)",
        (kind, group_id, target_id, reason, db.now(), db.now()))
    conn.commit()


def test_pending_review_surfaces_adjudication_history(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """The review roulette (110/210 union_closed goals re-adjudicated
    by >=2 blind groups): the reviewer gets ONE SENTENCE per past
    ruling inline (never the full text — owner call), the full rulings
    in the lazy ADJUDICATIONS.md, and the live citation waiters a park
    would strand."""
    _insert_problem(conn)
    root = _insert_root(conn)
    long_tail = "The rest of the ruling is a long second sentence " * 20
    _insert_ruling(conn, target_id=root, group_id=501,
                   reason="Park until the census lands. " + long_tail)
    _insert_ruling(conn, target_id=root, group_id=505, kind="Inject")
    # a live strategy on another goal CITES the reviewed goal
    other = _insert_root(conn, slug="citer")
    sid = _insert_strategy(conn, other)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
        " position, link_kind) VALUES (?, ?, 0, 'cited')", (sid, root))
    conn.commit()

    attempts_dir = tmp_path / "_attempts_adj"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Adjudication history on this goal" in text
    assert "grp501 parked it: Park until the census lands." in text
    assert "grp505 re-dispatched it" in text
    # one sentence only — the long tail must NOT ride THIS section
    # (other sections, e.g. the recent-decisions self-feedback, have
    # their own rendering rules)
    start = text.index("### Adjudication history on this goal")
    end = text.find("##", start + 4)
    section = text[start:end if end > 0 else len(text)]
    assert "long second sentence" not in section
    assert "ADJUDICATIONS.md" in text
    # the cited waiter is named, with the conduction consequence
    assert f"s{sid} under goal {other}" in text
    # the lazy file carries the FULL ruling
    adj = (attempts_dir / "ADJUDICATIONS.md").read_text(encoding="utf-8")
    assert f"## g{root} main" in adj
    assert "long second sentence" in adj


def test_a_human_ruling_is_not_rendered_as_a_group_ruling(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """§3.2: the adjudication record exists so a reviewer answers the
    LAST ruling instead of rediscovering it — which requires knowing who
    made it. A human park is the one ruling a group may not simply
    overturn, so rendering it as `grp<N>` (the group the command was
    filed under) hands the reviewer a peer's opinion where a person's
    decision stands. Both the inline history and the full companion say
    so."""
    _insert_problem(conn)
    root = _insert_root(conn)
    _insert_ruling(conn, target_id=root, group_id=501,
                   reason="Park until the census lands.")
    conn.execute(
        "UPDATE strategist_decisions SET actor = 'human',"
        " trigger_kind = 'human', reason = 'Owner: stop this line.'"
        " WHERE target_id = CAST(? AS TEXT)", (root,))
    conn.commit()

    attempts_dir = tmp_path / "_attempts_human_adj"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    start = text.index("### Adjudication history on this goal")
    end = text.find("##", start + 4)
    section = text[start:end if end > 0 else len(text)]
    assert "grp501" not in section
    assert "the human parked it" in section
    adj = (attempts_dir / "ADJUDICATIONS.md").read_text(encoding="utf-8")
    assert "grp501" not in adj
    assert "human" in adj


def test_strategist_context_points_at_adjudications(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """Every strategist wake gets the two-line pointer (and the file)
    whenever any goal carries a park ruling — parking/reviving without
    reading the record is the roulette this exists to end."""
    _insert_problem(conn)
    g = _insert_root(conn)
    _insert_ruling(conn, target_id=g, group_id=496, reason="Parked: X.")
    attempts_dir = tmp_path / "_attempts_ptr"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Adjudication history (park rulings)" in text
    assert (attempts_dir / "ADJUDICATIONS.md").exists()


def test_active_goals_roster_is_bounded_with_catalog_pointer(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """User backlog item d (2026-08-26): the full alive roster left the
    per-turn context — counts + the newest tail stay inline, the rest
    lives in CATALOG.md's `## Alive goals` (machine-written beside the
    Context every wake). Small problems keep the full list; the twin
    roster in `## TREE` is gone (the 08-24 autopsy's dominant
    'surfaces disagree' pair)."""
    _insert_problem(conn)
    _insert_root(conn)
    for i in range(40):
        db.insert_goal(conn, problem="p", slug=f"g{i:03d}",
                       lean_path=f"P/g{i:03d}.lean", statement="T",
                       origin="backward")
    attempts_dir = tmp_path / "_attempts_ag"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
    )
    text = out.read_text(encoding="utf-8")
    assert "## Active goals" in text
    assert "41 alive" in text
    assert "`g039`" in text                      # newest tail inline
    assert "`g000`" not in text                  # old bulk is lazy
    assert "Alive goals" in text and "CATALOG.md" in text
    # the TREE section keeps counters + pointer, no twin roster
    start = text.index("## TREE")
    tree = text[start:text.index("##", start + 4)]
    assert "Counters:" in tree
    assert "`g039`" not in tree




# ─── After a discarded cycle: the judge's rebuttal, never the draft ───
#
# 2026-08-30, group 504: the successor of an 11-round discard saw one
# line ("draft not shown") plus its own plan note — its belief, not the
# judge's refutation — and re-argued the same route for five more rounds
# (75 min, 830k tokens) before landing the two ConfirmShelves the audit
# asked for. Owner ruling: the rebuttals may be shown; the draft stays
# withheld (design §3). Last round inline, every round lazy-loaded.

def _reject_after_pass(conn):
    from Tooling.state import programme
    programme.record_pass(conn, "p", "# Pass\n\n## Argument\n\nfine\n",
                          {"verdict": "pass"}, [], 0, "b1")
    programme.record_rejection(
        conn, "p", "# Dead draft\n\n## Argument\n\nSECRET-DRAFT-TEXT\n",
        [{"round": 1, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 1] first-round objection"]},
         {"round": 3, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 2] the fatal objection"]}],
        3, discard_reason="adversary rebuttal",
        discard_channel="strategist_proposal_rejected")
    conn.commit()


def test_discarded_cycle_shows_the_judges_last_rebuttal_and_a_lazy_history(
        workspace: Path, mfst, tmp_path: Path) -> None:
    conn = db.connect()
    db.init_schema(conn)
    _insert_problem(conn)
    _insert_root(conn)
    _reject_after_pass(conn)
    attempts_dir = tmp_path / "_attempts_rej"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst)
    text = out.read_text(encoding="utf-8")
    assert "### Previous proposal rejected" in text
    assert "the fatal objection" in text, "the round that killed it is inline"
    assert "first-round objection" not in text, "earlier rounds are lazy-loaded"
    assert "SECRET-DRAFT-TEXT" not in text, "never the draft (design §3)"
    assert "REJECTED.md" in text, "the pointer to the full history"
    comp = (attempts_dir / "REJECTED.md").read_text(encoding="utf-8")
    assert "first-round objection" in comp and "the fatal objection" in comp
    assert "SECRET-DRAFT-TEXT" not in comp


def test_no_discard_no_rebuttal_surface(workspace: Path, mfst,
                                        tmp_path: Path) -> None:
    from Tooling.state import programme
    conn = db.connect()
    db.init_schema(conn)
    _insert_problem(conn)
    _insert_root(conn)
    programme.record_pass(conn, "p", "# Pass\n\n## Argument\n\nfine\n",
                          {"verdict": "pass"}, [], 0, "b1")
    conn.commit()
    attempts_dir = tmp_path / "_attempts_ok"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="inject_batch_done",
        attempts_dir=attempts_dir, workspace=workspace, intent=mfst)
    text = out.read_text(encoding="utf-8")
    assert "Previous proposal rejected" not in text
    assert not (attempts_dir / "REJECTED.md").exists()


def test_owner_notes_reach_every_strategist_wake(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent, tmp_path: Path,
) -> None:
    """The notes a person writes under `_docs/user/` (HID §1.2/§3.6)
    were readable by every seat and announced to none: the Context said
    only that `_docs/` is where the papers are. Every Strategist wake
    renders the roster — the judge gets it too, because its projection
    copies this same Context.md verbatim."""
    _insert_problem(conn)
    from Tooling.state import project_docs as _pd
    _pd.write(workspace, "p", "user/split_note.md",
              "# SPLIT: abundance across a cut\n\nbody\n")
    attempts_dir = tmp_path / "_attempts_notes"
    attempts_dir.mkdir()
    for trigger in ("inject_batch_done", "pending_review", "routine"):
        out = phase2_context.compile_strategist_context(
            conn, problem="p", trigger_kind=trigger,
            attempts_dir=attempts_dir, workspace=workspace, intent=mfst,
        )
        text = out.read_text(encoding="utf-8")
        assert "## Owner's notes" in text, trigger
        assert "Problems/p/_docs/user/split_note.md" in text, trigger
        assert "SPLIT: abundance across a cut" in text, trigger
        assert "\nbody\n" not in text, trigger


def test_strategist_stats_name_every_section_they_measure(
    workspace: Path, conn: sqlite3.Connection,
    mfst: intent_mod.ProblemIntent,
) -> None:
    """The telemetry zips `section_names` with `sections`, so one
    missing name shifts every label after it onto the wrong section and
    drops the last section from the total (2026-09-03: `adjudications`
    was never named — 17 names against 18 sections — so `charter`
    onward were mislabelled and the Lesson KB fell off the total: 16434
    B reported for an 18975 B Context.md). Both halves must stay
    paired on every trigger: nothing in the degradation ledger, and the
    total must account for every byte of Context.md below its title."""
    import json
    from Tooling.core import degraded
    from Tooling.state import kb
    _insert_problem(conn)
    _insert_root(conn)
    # the routine wake's LAST section — the one a short name list drops
    kb.add_lesson(conn, problem="p", title="a recipe", body="body",
                  provenance="t:1")
    for trigger in ("routine", "inject_batch_done", "pending_review"):
        attempts_dir = workspace / ".attempts" / f"pipe-{trigger}"
        attempts_dir.mkdir(parents=True)
        out = phase2_context.compile_strategist_context(
            conn, problem="p", trigger_kind=trigger,
            attempts_dir=attempts_dir, workspace=workspace, intent=mfst)
        text = out.read_text(encoding="utf-8")
        assert "context_stats_name_mismatch" not in degraded.snapshot(
            workspace), trigger
        stats = json.loads((attempts_dir / "_context_stats.json").read_text(
            encoding="utf-8"))
        # parts = [title, ""] + every section line, joined with "\n":
        # the recorded total (len(line)+1 per line) is exactly the file
        # minus its title line, so a dropped section shows up here.
        title = text.split("\n", 1)[0]
        assert stats["total_bytes"] == len(text) - len(title) - 1, trigger
