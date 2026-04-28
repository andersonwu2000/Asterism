"""P3 Acceptance tests #0a–#10.

Covers `docs/dev/phase3_cache.md ## Acceptance criteria`. Each class maps
to one AC. Real-lake-env items (AC #0a/#0b/#3/#5 partial) are skipped as
manual gates analogous to P2 #2a/#2b.

Most P3 acceptance items have unit tests in test_blocked_pipelines.py /
test_cascade.py / test_dedupe.py / test_search.py / test_scheduler.py;
this file exercises the same public APIs as a phase-level smoke gate so
that CI catches cross-cycle regressions on the full P3 contract.

AC #8 P2 regression coverage: verified indirectly — test_phase2_acceptance.py
runs green in the same CI suite, so the cascade-table refactor (C25) plus
all P3 changes introduced zero P2 regression. No aggregator class in this
file.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.stages.failure_archive import (
    IH_TRAP_SIMILARITY_THRESHOLD,
    archive_check,
    archive_ih_trap,
)
from Tooling.subsystems.blocked_pipelines import (
    block_pipeline,
    get_blocked_pipelines,
    is_blocked,
)


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_goal(conn, *, slug="g", problem="ex", question=None,
                  status="open", commit_state="live"):
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
        "question, commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"path/{slug}.lean", "root", "theorem", status,
         question, commit_state, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_pipeline(conn, *, pid="pipe-x", kind="Backward", target_id="0"):
    conn.execute(
        "INSERT OR IGNORE INTO pipelines "
        "(id, kind, runtime, target_id, target_kind, status, started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (pid, kind, "atomic", target_id, "Goal", "succeeded", _NOW),
    )
    conn.commit()
    return pid


def _insert_dead_attempt(conn, *, target_id, pipeline_kind, outcome,
                         pipeline_id="pipe-x", ts=None):
    _insert_pipeline(conn, pid=pipeline_id, kind=pipeline_kind)
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, pipeline_kind, "
        "outcome, reason_summary, ts) "
        "VALUES (?,?,?,?,?,?,?)",
        (str(target_id), "Goal", pipeline_id, pipeline_kind, outcome,
         f"reason for {outcome}", ts or _NOW),
    )
    conn.commit()


def _insert_strategy(conn, *, goal_id, similarity=None):
    conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, status, commit_state, "
        "parent_subgoal_max_similarity, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (goal_id, "path/s.lean", "proposed", "live", similarity, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ─────────────────────────────────────────────────────────────
# AC #0a / #0b: Demo D1 / D2 end-to-end — manual gates
# ─────────────────────────────────────────────────────────────


class TestAC0DemosManualGate:
    @pytest.mark.skip(reason="manual gate: D1 dedupe shared sub-Goal demo "
                              "needs real lake env + Mathlib + claude CLI")
    def test_d1_shared_subgoal(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: D2 IH-trap demo needs real lake "
                              "env + Mathlib + claude CLI")
    def test_d2_ih_trap_blocked(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #1: cache hit on repeat query (SEARCH_MOCK=record_calls)
# ─────────────────────────────────────────────────────────────


class TestAC1CacheHit:
    def test_real_cache_hit_path(self, db, tmp_path) -> None:
        """Spec AC #1: repeat query within TTL → 2nd call reads cache,
        no subprocess. Verified via subprocess.run mock + from_cache flag.

        (LOW-1 R3: removed the prior test_repeat_query_within_ttl_uses_cache
        that used SEARCH_MOCK=record_calls — record_calls bypasses the
        cache layer entirely, so the call counter wasn't an oracle for
        cache hit. test_real_cache_hit_path below is the real oracle.)"""
        from unittest.mock import MagicMock, patch

        from Tooling.subsystems.search import search

        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"results": [{"name": "x", "type": "T", "score": 0.5}]})
        fake.stderr = ""
        with patch("Tooling.subsystems.search.subprocess.run", return_value=fake):
            r1 = search("nat_add", scope="mathlib", kind="find_lemmas",
                        conn=db, lake_cwd=tmp_path)
            r2 = search("nat_add", scope="mathlib", kind="find_lemmas",
                        conn=db, lake_cwd=tmp_path)
        assert r1.from_cache is False
        assert r2.from_cache is True


# ─────────────────────────────────────────────────────────────
# AC #2: cache invalidation on goals INSERT/UPDATE
# ─────────────────────────────────────────────────────────────


class TestAC2CacheInvalidation:
    def _seed_cache_row(self, conn, *, query_hash, scope, mode):
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        conn.execute(
            "INSERT INTO search_cache "
            "(query_hash, scope, mode, results, expires_at) "
            "VALUES (?,?,?,?,?)",
            (query_hash, scope, mode, "[]", expires),
        )
        conn.commit()

    def test_finalize_goals_kills_local_goals_cache(self, db) -> None:
        self._seed_cache_row(db, query_hash="h1", scope="local_goals",
                             mode="find_lemmas")
        self._seed_cache_row(db, query_hash="h2", scope="dedupe", mode="dedupe")
        self._seed_cache_row(db, query_hash="h3", scope="mathlib",
                             mode="find_lemmas")

        writer = CommitWriter(db)
        gid = writer.begin("goals", "insert", {
            "problem": "ex", "slug": "g_inv", "lean_path": "p.lean",
            "origin": "root", "kind": "theorem", "status": "open",
        })
        writer.finalize("goals", gid, {})

        rows = db.execute(
            "SELECT scope, mode FROM search_cache"
        ).fetchall()
        scopes_modes = [(r[0], r[1]) for r in rows]
        # local_goals + dedupe killed; mathlib survives
        assert ("local_goals", "find_lemmas") not in scopes_modes
        assert ("dedupe", "dedupe") not in scopes_modes
        assert ("mathlib", "find_lemmas") in scopes_modes


# ─────────────────────────────────────────────────────────────
# AC #3: Dedupe Lean exe — manual gate
# ─────────────────────────────────────────────────────────────


class TestAC3DedupeLeanExeManualGate:
    @pytest.mark.skip(reason="manual gate: real isDefEq strict / iff_lite "
                              "comparisons need lake env. DEDUPE_MOCK paths "
                              "verified in test_dedupe.py.")
    def test_strict_alpha_equiv_hit(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: iff_lite simp/decide path needs "
                              "real lake env.")
    def test_iff_lite_hit(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #4: dedupe elab fail → NOVEL (容錯)
# ─────────────────────────────────────────────────────────────


class TestAC4DedupeElabFailNovel:
    def test_wrapper_passes_through_novel(self, db, tmp_path) -> None:
        """Spec AC #4 wrapper smoke gate: when dedupe.lean reports NOVEL
        (which it does on elab failure per spec §7.1 R3 fix), the Python
        wrapper returns outcome='novel'.

        This test verifies the wrapper's mock pass-through; the real
        elab-fail-on-sorry-candidate path requires lake env and is gated
        as a manual demo run (analogous to AC #3). cross-ref test_dedupe.py
        for fuller subprocess-mock coverage of dedupe.lean's stdout shape.
        """
        from Tooling.subsystems.dedupe import dedupe
        cand = tmp_path / "cand.lean"
        cand.write_text("theorem _c : True := sorry\n", encoding="utf-8")

        import os
        os.environ["DEDUPE_MOCK"] = "force_miss"
        try:
            result = dedupe(cand, [], conn=db)
        finally:
            del os.environ["DEDUPE_MOCK"]
        assert result.outcome == "novel"


# ─────────────────────────────────────────────────────────────
# AC #5: failure_replay drives prompt — partial coverage
# ─────────────────────────────────────────────────────────────


class TestAC5FailureReplayDrives:
    def test_failure_replay_returns_recent_dead_attempts(self, db) -> None:
        """Smoke: failure_replay stage returns up to K_digest recent rows."""
        from Tooling.stages.failure_replay import failure_replay
        gid = _insert_goal(db, slug="fr_g")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="exhausted", ts="2026-01-01T00:00:01")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:02")
        rows = failure_replay(db, gid, "Goal", k_digest=5)
        assert len(rows) == 2

    def test_prompt_embeds_dead_attempts_summary(self, db, tmp_path) -> None:
        """Spec AC #5 字面: Backward agent prompt must include dead_attempts
        summary on the third run. Verified by calling Backward._build_prompt
        directly with seeded dead_attempts (no LLM needed — spec line 124
        prompt-falldown test design)."""
        from unittest.mock import MagicMock
        from Tooling.pipelines.backward import Backward, BackwardConfig

        gid = _insert_goal(db, slug="fr_g_prompt", question="True")
        # Two prior failures the third run should "remember"
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="exhausted",
                              ts="2026-01-01T00:00:01")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:02")

        config = BackwardConfig(base_dir=str(tmp_path),
                                 lake_cwd=str(tmp_path))
        bw = Backward(db, MagicMock(), config)

        # failure_replay returns the recent dead_attempts (target_kind='Goal')
        rows = bw.failure_replay(gid)
        assert len(rows) == 2

        goal = {
            "id": gid, "problem": "ex", "slug": "fr_g_prompt",
            "question": "True",
        }
        prompt = bw._build_prompt(goal, rows)
        # Spec: "比對含 dead_attempts summary 字串" — the rows' reason fields
        # land in the prompt's {{DEAD_ATTEMPTS}} placeholder.
        assert "exhausted" in prompt
        assert "unproductive" in prompt


# ─────────────────────────────────────────────────────────────
# AC #6 + #6a: IH-trap special-case + N=5 generic
# ─────────────────────────────────────────────────────────────


class TestAC6IhTrapAndGeneric:
    def test_ih_trap_blocks_immediately(self, db) -> None:
        """Spec: 2 consecutive unproductive + similarity >= threshold → block
        before N=5."""
        gid = _insert_goal(db, slug="ih_g")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:01")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:02")
        _insert_strategy(db, goal_id=gid,
                          similarity=IH_TRAP_SIMILARITY_THRESHOLD + 0.05)

        blocked = archive_ih_trap(db, gid, "Backward")
        assert blocked is True
        assert is_blocked(db, gid, "Backward") is True

    def test_n5_generic_blocks(self, db) -> None:
        """Spec #6a: 5 exhausted Backward → block via generic N=5 path."""
        gid = _insert_goal(db, slug="n5_g")
        for i in range(5):
            _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                                  outcome="exhausted",
                                  ts=f"2026-01-01T00:00:{i:02d}")
        blocked = archive_check(db, gid, "Backward")
        assert blocked is True

    def test_two_rules_independent(self, db) -> None:
        """Spec #6a: IH-trap special-case 與通用 N=5 互不干擾。"""
        # IH-trap on one goal
        g1 = _insert_goal(db, slug="ih_only")
        for i in range(2):
            _insert_dead_attempt(db, target_id=g1, pipeline_kind="Backward",
                                  outcome="unproductive",
                                  ts=f"2026-01-01T00:00:{i:02d}")
        _insert_strategy(db, goal_id=g1, similarity=0.9)
        archive_ih_trap(db, g1, "Backward")
        assert is_blocked(db, g1, "Backward") is True

        # N=5 on a separate goal
        g2 = _insert_goal(db, slug="n5_only")
        for i in range(5):
            _insert_dead_attempt(db, target_id=g2, pipeline_kind="Backward",
                                  outcome="exhausted",
                                  ts=f"2026-01-01T00:00:{i:02d}")
        archive_check(db, g2, "Backward")
        assert is_blocked(db, g2, "Backward") is True

        # Cross-check: g1's block doesn't bleed into g2 status or vice versa
        assert is_blocked(db, g1, "Builder") is False
        assert is_blocked(db, g2, "Builder") is False


# ─────────────────────────────────────────────────────────────
# AC #7: blocked_pipelines BFS filter
# ─────────────────────────────────────────────────────────────


class TestAC7BlockedFilter:
    def test_bfs_skips_blocked_goal(self, db, tmp_path) -> None:
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="filter_g")
        block_pipeline(db, gid, "Backward")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        reactor._run_structural_refill()

        rows = db.execute(
            "SELECT kind FROM queue WHERE target_id = ?", (str(gid),)
        ).fetchall()
        assert all(r[0] != "Backward" for r in rows)


# ─────────────────────────────────────────────────────────────
# AC #8: cascade dispatch table — P2 acceptance regression check
# ─────────────────────────────────────────────────────────────


class TestAC8CascadeDispatchTable:
    def test_dispatch_table_present_and_complete(self) -> None:
        from Tooling.cascade import DISPATCH_TABLE, get_action
        # All P3 outcomes covered:
        for combo in [
            ("Builder", "proved"), ("Builder", "exhausted"),
            ("Builder", "hasSorry"), ("Backward", "success"),
            ("Backward", "exhausted"), ("Backward", "unproductive"),
        ]:
            assert get_action(*combo) is not None
        # Forward-compat field present:
        for action in DISPATCH_TABLE.values():
            assert action.target_ids == ()

    # AC #8 P2 regression: verified indirectly — test_phase2_acceptance.py
    # runs in the same CI suite; if the dispatch table refactor introduced
    # a regression, that file would fail. No aggregator class here.
    # (LOW-4 R3: removed the prior skip stub.)


# ─────────────────────────────────────────────────────────────
# AC #9: liveness check drops stale event
# ─────────────────────────────────────────────────────────────


class TestAC9LivenessCheck:
    def test_stale_dead_strategy_event_dropped(self, db, tmp_path) -> None:
        from Tooling.pipelines.builder import BuilderResult
        from Tooling.scheduler import Reactor, ReactorConfig

        gid = _insert_goal(db, slug="liveness_g")
        sid = _insert_strategy(db, goal_id=gid)
        with db:
            db.execute(
                "UPDATE strategies SET status='dead' WHERE id=?", (sid,),
            )

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db

        task = {"kind": "Builder", "target_id": str(sid)}
        is_stale = reactor._run_step1_stale_filter(
            task, BuilderResult(outcome="exhausted")
        )
        assert is_stale is True

        # Full handler skips downstream cascade
        reactor._handle_pipeline_finished(task, BuilderResult(outcome="exhausted"))
        # No additional shelve / dead writes (strategy already dead, goal stays open)
        status = db.execute(
            "SELECT status FROM goals WHERE id=?", (gid,)
        ).fetchone()[0]
        assert status == "open"


# ─────────────────────────────────────────────────────────────
# AC #10: in-memory cap removed (functional check)
# ─────────────────────────────────────────────────────────────


class TestAC10InMemoryCapRemoved:
    def test_persistent_block_survives_reactor_restart(self, db, tmp_path) -> None:
        """Spec functional check: P2 fixture expectation 'restart re-tries
        once' should now FAIL — restart sees persistent block + still skips."""
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="restart_persist")
        block_pipeline(db, gid, "Backward")

        r1 = Reactor(str(tmp_path / "asterism.db"),
                     ReactorConfig(base_dir=str(tmp_path)))
        r1.conn = db
        r1._run_structural_refill()
        rows1 = db.execute(
            "SELECT COUNT(*) FROM queue WHERE target_id = ? AND kind = 'Backward'",
            (str(gid),),
        ).fetchone()[0]
        assert rows1 == 0

        # Simulate restart: fresh Reactor instance reads persistent state
        r2 = Reactor(str(tmp_path / "asterism.db"),
                     ReactorConfig(base_dir=str(tmp_path)))
        r2.conn = db
        r2._run_structural_refill()
        rows2 = db.execute(
            "SELECT COUNT(*) FROM queue WHERE target_id = ? AND kind = 'Backward'",
            (str(gid),),
        ).fetchone()[0]
        assert rows2 == 0  # still skipped (persistent), not re-enqueued

    def test_failure_count_attribute_removed(self, tmp_path) -> None:
        """Reactor instance should not have _failure_count / _inc_failure_count."""
        from Tooling.scheduler import Reactor, ReactorConfig
        r = Reactor(str(tmp_path / "asterism.db"),
                    ReactorConfig(base_dir=str(tmp_path)))
        assert not hasattr(r, "_failure_count")
        assert not hasattr(r, "_inc_failure_count")
        assert not hasattr(r, "_get_failure_count")
