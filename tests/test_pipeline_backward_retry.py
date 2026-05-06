"""F53 — Same-session Backward retry (mirror of F33 for Builder).

When run_backward fails (lake_build_error etc.), the goal's
`backward_session_id` persists so the next dispatch resumes the
agent's session via `claude --resume` with the prior lake stderr
inlined as `retry_context`. Tests assert the session-id mechanics +
the timeout-clears-session safety net, mocking spawn_llm so no
actual claude/lake invocation happens.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", depth=0,
    )


def test_first_dispatch_mints_session_id_and_passes_to_spawn(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No prior session → run_backward mints a UUID, persists it,
    passes session_id + is_retry=False to spawn_llm."""
    gid = _seed_root_goal(tmp_path, conn)
    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124  # bail out via timeout path; we only care about call args

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw1",
    )
    assert captured["session_id"] is not None
    assert captured["is_retry"] is False
    assert captured["retry_context"] is None
    # On rc=124 (timeout) session is conservatively cleared
    assert db.get_backward_session_id(conn, gid) is None


def test_second_dispatch_reuses_session_with_retry_context(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prior session + a recorded Backward dead_attempt → second
    dispatch sets is_retry=True and inlines the prior lake stderr."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "saved-uuid")
    # Simulate a prior Backward dead_attempt with a lake error
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("pid-prior", "Backward", str(gid), "Goal",
         "failed", "failed", db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (gid, "Goal", "pid-prior", "lake_build_error",
         "error: L_main_sub_2.lean:13:41: expected token", db.now()),
    )
    conn.commit()

    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw2",
    )
    assert captured["session_id"] == "saved-uuid"
    assert captured["is_retry"] is True
    assert "expected token" in (captured["retry_context"] or "")


def test_stale_session_falls_back_to_fresh_uuid(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc=125 (stale session) → mint fresh UUID, recompile context,
    cold-spawn once. Net effect: session is replaced, not cleared."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "stale-uuid")
    seen = []

    def fake_spawn(**kw):
        seen.append((kw["session_id"], kw["is_retry"]))
        # First call: stale; second call: also fail but with fresh sid
        return 125 if len(seen) == 1 else 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-stale",
    )
    assert len(seen) == 2
    assert seen[0][0] == "stale-uuid"      # first try with saved sid
    assert seen[0][1] is True              # is_retry path
    assert seen[1][0] != "stale-uuid"      # fresh sid for cold restart
    assert seen[1][1] is False             # cold = is_retry False
    # rc=124 on the cold retry → session conservatively cleared
    assert db.get_backward_session_id(conn, gid) is None


def test_non_zero_non_timeout_keeps_session_id(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary rc≠0 (not 124, not 125) → keep session for next
    dispatch's --resume."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "warm-uuid")
    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 1)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-fail",
    )
    assert db.get_backward_session_id(conn, gid) == "warm-uuid"


def test_warm_retry_reuses_dead_strategy_id(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F53/A — warm retry must REUSE the prior dead strategy's id so
    the agent's session memory of the strategy patch's locked theorem
    name (`theorem s<X>` + `_strategy_s<X>.lean`) stays valid. Minting
    a fresh sX here would force the resumed agent's session-memory
    references to `s<X>` against a freshly minted s<Y> patch, breaking
    the F52 signature check.
    """
    gid = _seed_root_goal(tmp_path, conn)
    # Seed a prior dead strategy on this goal (the failed s<N>)
    rel = db.get_goal(conn, gid)["lean_path"]
    prior_sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel,
        created_by="pid-prior", proposal_md="prior", scratch_path="",
    )
    db.update_strategy_status(conn, prior_sid, "dead")
    db.set_backward_session_id(conn, gid, "warm-uuid")

    seen_skeletons = []

    def fake_spawn(**kw):
        # Capture the sid_token the framework wrote into patch.lean
        patch = (kw["attempts_dir"] / "patch.lean").read_text(encoding="utf-8")
        seen_skeletons.append(patch)
        return 1  # ordinary failure — keeps session for next retry

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-retry",
    )

    # Strategy id must be the prior dead one, not a fresh insert.
    rows = conn.execute(
        "SELECT id, status FROM strategies WHERE goal_id=? ORDER BY id",
        (gid,),
    ).fetchall()
    assert len(rows) == 1, f"expected reuse, got rows={list(rows)}"
    assert rows[0]["id"] == prior_sid
    # And the skeleton's theorem name uses the SAME sid token.
    assert f"theorem s{prior_sid}" in seen_skeletons[0]


def test_warm_retry_clears_stale_strategy_subgoals(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0-#3: when warm-retry resurrects a dead strategy that had
    committed sub-goal links in the prior cycle, those rows must be
    cleared so `strategies_ready_for_verify` doesn't falsely flag
    the resurrected strategy on stale subs."""
    gid = _seed_root_goal(tmp_path, conn)
    rel = db.get_goal(conn, gid)["lean_path"]
    prior_sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel,
        created_by="pid-prior", proposal_md="prior", scratch_path="",
    )
    db.update_strategy_status(conn, prior_sid, "dead")
    # Simulate the prior dead cycle having committed a subgoal link
    sub_gid = db.insert_goal(
        conn, problem="p", slug="ghost_sub",
        lean_path="Problems/p/proofs/L_ghost_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, sub_gid, "proved")
    db.link_subgoal(conn, strategy_id=prior_sid, subgoal_id=sub_gid, position=0)
    db.set_backward_session_id(conn, gid, "warm-uuid")

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 1)  # ordinary fail

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-warm",
    )

    # After reuse: stale link gone. Without the DELETE, this row
    # would survive the resurrect → ghost sub kept marking the
    # strategy verify-eligible whenever it was 'proposed'.
    links = conn.execute(
        "SELECT COUNT(*) AS n FROM strategy_subgoals WHERE strategy_id=?",
        (prior_sid,),
    ).fetchone()
    assert links["n"] == 0


def test_cold_dispatch_mints_fresh_strategy_id(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F53/A — when there's no active session (cold path), strategy_id
    is freshly minted as before. Reuse path is gated on is_retry."""
    gid = _seed_root_goal(tmp_path, conn)
    # Even if a stale dead strategy exists, no session means cold
    rel = db.get_goal(conn, gid)["lean_path"]
    stale_sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel,
        created_by="pid-old", proposal_md="", scratch_path="",
    )
    db.update_strategy_status(conn, stale_sid, "dead")
    # No backward_session_id → cold path
    assert db.get_backward_session_id(conn, gid) is None

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 124)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-cold",
    )
    rows = conn.execute(
        "SELECT id FROM strategies WHERE goal_id=? ORDER BY id",
        (gid,),
    ).fetchall()
    # Expect: stale + freshly-minted (different ids)
    assert len(rows) == 2
    assert rows[0]["id"] == stale_sid
    assert rows[1]["id"] != stale_sid


# ---------------------------------------------------------------------
# F55 — wrapper persists/clears partial PROPOSAL.md per outcome
# ---------------------------------------------------------------------

def _bw_drafts_path(tmp_path: Path, gid: int) -> Path:
    return tmp_path / "Problems" / "p" / ".drafts" / f"backward_g{gid}.md"


def test_backward_wrapper_persists_progress_note_after_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — main Backward spawn times out (rc=124). Framework runs a
    postmortem spawn that resumes the killed session and writes
    _progress.md with state + blockers. Wrapper persists _progress.md
    into .drafts/ so the next dispatch's Context.md surfaces it."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            (kw["attempts_dir"] / "_progress.md").write_text(
                "Kelly minimiser route, 4 sub-goals; blocked on the "
                "perpendicular-distance lemma name.",
                encoding="utf-8")
            return 0
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-timeout")
    draft = _bw_drafts_path(tmp_path, gid)
    assert draft.exists()
    body = draft.read_text(encoding="utf-8")
    assert "Kelly minimiser" in body
    assert "perpendicular-distance" in body


def test_backward_timeout_dispatches_postmortem_with_correct_args(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — on main-spawn timeout, framework calls spawn_llm a second
    time with is_postmortem=True, prompt_path pointing at
    backward_postmortem.md, and the same session_id as the killed
    main spawn (so --resume can revive its memory)."""
    gid = _seed_root_goal(tmp_path, conn)
    calls = []

    def fake_spawn(**kw):
        calls.append(kw)
        if kw.get("is_postmortem"):
            return 124  # don't bother writing — just inspect args
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-pm-args")
    assert len(calls) == 2  # main + postmortem
    main_call, pm_call = calls
    assert pm_call["is_postmortem"] is True
    assert pm_call["session_id"] == main_call["session_id"]
    assert pm_call["prompt_path"].name == "backward_postmortem.md"
    assert pm_call["kind"] == "backward"


def test_backward_wrapper_no_persist_when_no_postmortem_note(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the postmortem itself also times out (or returns no
    _progress.md), no draft is persisted — next dispatch cold-starts
    as it would have without F55. Best-effort design: no exception
    blocks the timeout flow."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            return 124  # postmortem also times out — no _progress.md
        return 124  # main + commit phase both time out
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-nodump")
    draft = _bw_drafts_path(tmp_path, gid)
    assert not draft.exists()




def test_backward_wrapper_clears_draft_on_goal_no_longer_open(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 review fix #2 — race-guard `goal_no_longer_open` means a
    sibling cascade already settled this goal; the in-flight PROPOSAL
    is moot. Clear the draft so a future re-decomposition (if the goal
    later reopens) doesn't get misled by stale carry-over."""
    gid = _seed_root_goal(tmp_path, conn)
    # Pre-seed a stale draft as if from a prior attempt
    draft = _bw_drafts_path(tmp_path, gid)
    draft.parent.mkdir(parents=True)
    draft.write_text("stale prior draft", encoding="utf-8")

    # Simulate a sibling having shelved the goal between dispatch and
    # post-spawn. We force this by mutating goal status before the
    # spawn returns.
    def fake_spawn_with_race(**kw):
        attempts = kw["attempts_dir"]
        # Phase 6 single-output: agent writes patch.lean with leading
        # comments + edits the F52 skeleton body. Add a sub-goal stub.
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        (attempts / "patch.lean").write_text(
            "-- s1: race test\n"
            + patch_text.replace(":= by sorry", ":= by trivial"),
            encoding="utf-8")
        import re
        m = re.search(r"theorem (s\d+)", patch_text)
        sid_token = m.group(1) if m else "s1"
        (attempts / f"new_sub_one.lean").write_text(
            "-- sub_one: race-test sub\n"
            "import Mathlib\nnamespace Problems.p\n"
            "theorem sub_one : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        # Race: between spawn return and the inner's status re-check
        # at the race guard, sibling shelved.
        db.update_goal_status(conn, gid, "shelved")
        conn.commit()
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn_with_race)
    monkeypatch.setattr(pipeline, "_lake_build_batch",
                        lambda ws, ts: (True, ""))

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-race")
    assert r.outcome == "failed"
    assert r.failure_reason == "goal_no_longer_open"
    # Wrapper should have CLEARED the stale draft, not overwritten it
    # with the moot in-flight PROPOSAL.
    assert not draft.exists()


# ---------------------------------------------------------------------
# Phase 6.5 — Backward leaf-bypass salvage
# ---------------------------------------------------------------------

def test_backward_leaf_bypass_promotes_zero_subgoal_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Backward agent writes patch.lean with a complete proof body
    and no `new_*.lean` sub-goal stubs, framework registers a 0-subgoal
    strategy (mirroring `_try_promote_sorry_free` at the strategy level).
    Verify housekeeping picks it up next tick. Symmetric escape to
    Builder's `decline: too_hard` — agent saying 'this is leaf-able,
    not decompose-able' through behavior rather than directive."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        # Edit F52 skeleton's body but emit no new_*.lean sub-goals.
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        patch_text = "-- main: trivial leaf proof\n" + patch_text.replace(
            ":= by sorry", ":= by trivial")
        (attempts / "patch.lean").write_text(patch_text, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build_batch",
                        lambda ws, ts: (True, ""))

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-leaf-bypass")
    assert r.outcome == "success"
    assert r.proposal_md.startswith("-- main: trivial leaf proof")

    # Strategy committed with scratch_path set, 0 strategy_subgoals rows.
    rows = conn.execute(
        "SELECT id, status, scratch_path, proposal_md FROM strategies "
        "WHERE goal_id = ?", (gid,)
    ).fetchall()
    assert len(rows) == 1
    s = rows[0]
    assert s["status"] == "proposed"
    assert s["scratch_path"].endswith(".lean")
    assert "trivial leaf proof" in s["proposal_md"]
    sub_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_subgoals WHERE strategy_id = ?",
        (s["id"],),
    ).fetchone()[0]
    assert sub_count == 0
    # Ready for Verify: vacuously satisfies the no-unproved-subs gate.
    assert any(s2["id"] == s["id"]
               for s2 in db.strategies_ready_for_verify(conn))


def test_backward_no_subs_with_sorry_body_still_parse_proposal_fail(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leaf-bypass requires a non-sorry body. Patch with `:= by sorry`
    and 0 sub-goals AND no decline directive is genuinely empty output —
    framework still rejects as parse_proposal_fail (the salvage triggers
    only when the agent over-delivered, not when they under-delivered)."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        # Add leading comment but leave body as sorry, no new_*.lean files.
        patch_text = "-- main: ...\n" + patch_text
        (attempts / "patch.lean").write_text(patch_text, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-empty")
    assert r.outcome == "failed"
    assert r.failure_reason == "parse_proposal_fail"
    assert "sorry body" in (r.failure_detail or "")
