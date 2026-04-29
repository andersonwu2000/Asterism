"""P4 Acceptance tests #0a-#10 (Counterexample-deferred subset).

Covers `docs/dev/phase4_conjecture.md ## Acceptance criteria` to the
extent achievable with Counterexample pipeline deferred per
task.md ## 延後 cycles. ACs that strictly depend on Counterexample
witness verdict (or Counterexample-driven silver→gold upgrade) are
marked as @pytest.mark.skip with the deferral reason — they re-enable
when the Counterexample pipeline ships.

Coverage matrix:

  AC #0a Demo true_conj end-to-end           — manual gate (real lake env)
  AC #0b Demo false_conj end-to-end          — manual gate (real lake env)
  AC #1  three-line dispatch within 30s      — partial (Backward + Refuter
                                                 only; Counterexample deferred)
  AC #2  Counterexample silver verdict       — DEFERRED
  AC #3  Cancellation white-list             — covered (test_cancellation.py)
                                                 + acceptance-level dispatch
                                                 verification here
  AC #4  Refuter witness fetch from evidence — partial (witness slot
                                                 reserved + dual-mode prompt
                                                 per spike-013 D-13-1)
  AC #5  Silver→Gold upgrade                 — DEFERRED
  AC #5a silver-stuck stop-gap               — DEFERRED
  AC #6  Race silently-skip after classical  — DEFERRED
  AC #7a true_conj warm cache                — manual gate (timing)
  AC #7b true_conj cold cache                — manual gate (timing)
  AC #8  Counterexample unproductive blocks  — DEFERRED
  AC #9  Cascade fatal halt (dual-proved)    — covered (test_cascade_twin.py)
                                                 + restart recovery here
  AC #10 trust_set computational entry       — DEFERRED
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.cancellation import (
    CancellationVerdict,
    select_pipelines_to_cancel,
)
from Tooling.cascade import DISPATCH_TABLE, get_action
from Tooling.db.connect import connect, init_schema


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_goal(
    conn,
    *,
    slug: str = "g",
    problem: str = "p4_demo",
    kind: str = "conjecture",
    status: str = "open",
    twin_of: int | None = None,
    answer_data: dict | None = None,
) -> int:
    ad = json.dumps(answer_data) if answer_data else None
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
        "commit_state, twin_of, answer_data, depth, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, 'root', ?, ?, 'live', ?, ?, 0, ?, ?)",
        (problem, slug, f"path/{slug}.lean", kind, status, twin_of, ad,
         _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ─────────────────────────────────────────────────────────────
# AC #0a / #0b: Demo end-to-end — manual gates
# ─────────────────────────────────────────────────────────────


class TestAC0DemoManualGate:
    @pytest.mark.skip(reason="manual gate: AC #0a true_conj end-to-end "
                              "demo needs real lake env + Mathlib + claude CLI")
    def test_0a_true_conj_demo(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: AC #0b false_conj end-to-end "
                              "(refuted via Refuter→Builder ¬G classical, "
                              "Counterexample deferred so witness path skipped) "
                              "needs real lake env + Mathlib + claude CLI")
    def test_0b_false_conj_demo(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #1: three-line dispatch (Counterexample deferred → two-line)
# ─────────────────────────────────────────────────────────────


class TestAC1ThreeLineDispatch:
    """Spec AC #1: kind=conjecture goal入池 → 30s 內 atomic queue 出現
    Backward + Refuter + Counterexample 三項.

    With Counterexample deferred (task.md ## 延後 cycles), only Backward
    + Refuter fire. C31 BFS structural refill wires both.
    """

    def test_bfs_enqueues_backward_and_refuter(self, db, tmp_path) -> None:
        """In-process variant of AC #1: BFS structural refill on a
        conjecture goal enqueues both Backward and Refuter; Counterexample
        deferred per task.md ## 延後 cycles.

        P7 演習 refactor: Backward fallback gate requires a finished
        Solver attempt — pre-seed one so this AC test still validates
        the Backward+Refuter dispatch behavior.
        """
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="conj_dispatch", kind="conjecture")
        # Seed finished Solver to open Backward gate.
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, outcome, "
            "started_at, finished_at) VALUES "
            "(?, 'Solver', 'atomic', ?, 'Goal', 'failed', 'exhausted', "
            "'2026-04-29T00:00:00+00:00', '2026-04-29T00:00:01+00:00')",
            (f"seeded-solver-{gid}", str(gid)),
        )
        db.commit()

        cfg = ReactorConfig(base_dir=str(tmp_path), pool_size=1)
        reactor = Reactor(str(tmp_path / "test.db"), cfg)
        reactor.conn = db
        reactor._bfs_enqueue_backward()
        reactor._bfs_enqueue_refuter_for_conjecture()

        kinds = {
            row[0]
            for row in db.execute(
                "SELECT kind FROM queue WHERE target_id = ?", (str(gid),)
            ).fetchall()
        }
        assert "Backward" in kinds
        assert "Refuter" in kinds
        # Counterexample deferred → must NOT be enqueued
        assert "Counterexample" not in kinds

    def test_counterexample_dispatch_deferred(self, db, tmp_path) -> None:
        """No code path enqueues Counterexample for kind=conjecture goals
        in C31. (Verifies the deferral is real, not just unwritten.)"""
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="conj_no_ce", kind="conjecture")
        cfg = ReactorConfig(base_dir=str(tmp_path), pool_size=1)
        reactor = Reactor(str(tmp_path / "test.db"), cfg)
        reactor.conn = db
        reactor._run_structural_refill()
        ce_count = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Counterexample'"
        ).fetchone()[0]
        assert ce_count == 0


# ─────────────────────────────────────────────────────────────
# AC #2: Counterexample silver verdict — DEFERRED
# ─────────────────────────────────────────────────────────────


class TestAC2CounterexampleSilver:
    @pytest.mark.skip(reason="DEFERRED: Counterexample pipeline + silver "
                              "verdict + Library/Counterexamples json (task.md "
                              "## 延後 cycles)")
    def test_silver_verdict_writes_witness(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #3: Cancellation white-list — production shape verification
# ─────────────────────────────────────────────────────────────


class TestAC3CancellationWhitelist:
    """Spec AC #3: silver verdict 觸發後 pipelines table 上 G 的 Builder /
    其他 Counterexample 被 cancel、Refuter 仍 running.

    With Counterexample deferred, the silver-trigger sub-case is also
    deferred. C31 cancellation white-list still has the four conditions
    wired (cond 3 raises NotImplementedError); this acceptance verifies
    the cond 1 'goal_proved' production shape (Builder via strategies
    JOIN) — the most-used trigger in P4 conjecture flow.
    """

    def test_cond1_goal_proved_cancels_builder_via_strategy_join(
        self, db, tmp_path
    ) -> None:
        gid = _insert_goal(db, slug="ac3_g", kind="conjecture")
        with db:
            db.execute(
                "INSERT INTO strategies "
                "(id, goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, 'in_progress', 'live', ?)",
                (200, gid, "s.lean", _NOW),
            )
            # Builder targeting strategy 200 — Builder.target_kind='Strategy'
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, started_at) "
                "VALUES ('p_b', 'Builder', 'atomic', '200', 'Strategy', "
                "'running', ?)",
                (_NOW,),
            )
            # Backward targeting goal — target_kind='Goal'
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, started_at) "
                "VALUES ('p_bw', 'Backward', 'atomic', ?, 'Goal', "
                "'running', ?)",
                (str(gid), _NOW),
            )
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=gid)
        )
        ids = {r["id"] for r in result}
        assert ids == {"p_b", "p_bw"}

    def test_cond3_counterexample_silver_deferred_raises(self, db) -> None:
        with pytest.raises(NotImplementedError, match="Counterexample"):
            select_pipelines_to_cancel(
                db,
                CancellationVerdict(kind="counterexample_silver", goal_id=1),
            )


# ─────────────────────────────────────────────────────────────
# AC #4: Refuter witness fetch — dual-mode prompt + reserved slot
# ─────────────────────────────────────────────────────────────


class TestAC4RefuterWitnessFetch:
    """Spec AC #4: Refuter agent prompt 內含 evidence.counterexample_witness.

    With Counterexample deferred, no production silver verdict ever lands
    a witness in evidence; the witness slot is reserved per spike-013
    D-13-1 and the prompt template falls through to generic ¬G path on
    "(none)". This acceptance verifies (a) the prompt template has the
    EVIDENCE_WITNESS slot, and (b) Refuter._extract_witness_block correctly
    populates it when evidence is present.
    """

    def test_prompt_template_has_witness_slot(self, tmp_path) -> None:
        from Tooling.pipelines.refuter import Refuter, RefuterConfig
        from unittest.mock import MagicMock
        from Tooling.agent.provider import FallbackChain
        chain = MagicMock(spec=FallbackChain)
        cfg = RefuterConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        from Tooling.db.connect import connect as _connect
        from Tooling.db.connect import init_schema as _init
        c = _connect(":memory:")
        _init(c)
        r = Refuter(c, chain, cfg)
        template = r._load_prompt_template()
        assert "{{EVIDENCE_WITNESS}}" in template
        assert "Counterexample evidence" in template

    def test_witness_slot_filled_when_evidence_present(self, tmp_path) -> None:
        from Tooling.pipelines.refuter import Refuter, RefuterConfig
        from unittest.mock import MagicMock
        from Tooling.agent.provider import FallbackChain
        from Tooling.db.connect import connect as _connect
        from Tooling.db.connect import init_schema as _init
        c = _connect(":memory:")
        _init(c)
        chain = MagicMock(spec=FallbackChain)
        cfg = RefuterConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        r = Refuter(c, chain, cfg)
        ev = json.dumps({
            "counterexample_witness": {
                "witness_lean_expr": "(2 : Nat)",
                "witness_type": "Nat",
                "predicate_def": "myPred",
            }
        })
        prompt = r._build_prompt(
            {"problem": "p", "slug": "g", "question": "True", "evidence": ev},
            [],
        )
        assert "(2 : Nat)" in prompt
        assert "myPred" in prompt

    def test_witness_slot_none_for_no_evidence(self, tmp_path) -> None:
        from Tooling.pipelines.refuter import Refuter, RefuterConfig
        from unittest.mock import MagicMock
        from Tooling.agent.provider import FallbackChain
        from Tooling.db.connect import connect as _connect
        from Tooling.db.connect import init_schema as _init
        c = _connect(":memory:")
        _init(c)
        chain = MagicMock(spec=FallbackChain)
        cfg = RefuterConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        r = Refuter(c, chain, cfg)
        prompt = r._build_prompt(
            {"problem": "p", "slug": "g", "question": "True", "evidence": None},
            [],
        )
        assert "(none)" in prompt


# ─────────────────────────────────────────────────────────────
# AC #5 / #5a: silver→gold upgrade + silver-stuck stop-gap — DEFERRED
# ─────────────────────────────────────────────────────────────


class TestAC5SilverGoldUpgrade:
    @pytest.mark.skip(reason="DEFERRED: silver state requires Counterexample "
                              "witness verdict (task.md ## 延後 cycles); "
                              "silver→gold upgrade branch reserved in "
                              "_cascade_twin_to_refuted")
    def test_silver_to_gold_upgrade(self) -> None:
        pass


class TestAC5aSilverStuckStopGap:
    @pytest.mark.skip(reason="DEFERRED: silver-stuck stop-gap hard rule "
                              "depends on Counterexample writing silver "
                              "verdict (task.md ## 延後 cycles)")
    def test_silver_stuck_inject_refuter(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #6: race silently-skip — DEFERRED
# ─────────────────────────────────────────────────────────────


class TestAC6RaceSilentSkip:
    @pytest.mark.skip(reason="DEFERRED: race scenario needs Counterexample "
                              "silver writing while Refuter→Builder ¬G classical "
                              "completes; both depend on Counterexample "
                              "(task.md ## 延後 cycles). REFUTER_FAST_PATH env "
                              "still raises NotImplementedError per C29 R3.")
    def test_silver_skipped_after_classical(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #7: true_conj timing — manual gates
# ─────────────────────────────────────────────────────────────


class TestAC7TimingManualGate:
    @pytest.mark.skip(reason="manual gate: AC #7a/#7b wall-clock timing "
                              "needs real lake env (warm vs cold cache)")
    def test_7a_warm_cache_under_15min(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #8: Counterexample unproductive → blocked — DEFERRED
# ─────────────────────────────────────────────────────────────


class TestAC8CounterexampleUnproductiveBlocked:
    @pytest.mark.skip(reason="DEFERRED: Counterexample pipeline produces "
                              "unproductive outcome (task.md ## 延後 cycles)")
    def test_unproductive_writes_blocked_pipelines(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #9: Cascade fatal halt (dual-proved) — covered + extension
# ─────────────────────────────────────────────────────────────


class TestAC9CascadeFatalHalt:
    """Spec AC #9: CASCADE_FAULT=dual_proved → fatal event + scheduler halt
    + working dir / DB preserved.

    Core fatal-halt detection covered by test_cascade_twin.py
    TestDualProvedInvariantHalt. Acceptance-level adds:
      - dispatch table includes Refuter outcomes (P4 cascade extension)
      - CASCADE_FAULT helper raises CascadeFault for the three modes
    """

    def test_dispatch_table_extended_for_refuter(self) -> None:
        """P4 C30: cascade table grew from P3's 6 entries to 8 with
        Refuter success/exhausted dispatched."""
        assert ("Refuter", "success") in DISPATCH_TABLE
        assert ("Refuter", "exhausted") in DISPATCH_TABLE
        # P3 entries still present
        assert ("Builder", "proved") in DISPATCH_TABLE
        assert ("Backward", "success") in DISPATCH_TABLE

    def test_refuter_success_action_no_cascade_state_change(self) -> None:
        """Refuter success cascade is acknowledge-only — ¬G already
        inserted by Refuter.commit; structural refill picks it up."""
        action = get_action("Refuter", "success")
        assert action is not None
        assert "acknowledge_negation_goal" in action.side_effects

    def test_cascade_fault_dual_proved_helper_raises(self, monkeypatch) -> None:
        from Tooling.cascade import CascadeFault, check_cascade_fault
        monkeypatch.setenv("CASCADE_FAULT", "dual_proved")
        with pytest.raises(CascadeFault, match="dual_proved"):
            check_cascade_fault("dual_proved")

    def test_cascade_fault_unique_violation_reserved(self, monkeypatch) -> None:
        """unique_violation mode reserved name; helper raises so any
        future call site fail-loud rather than silent ignore."""
        from Tooling.cascade import CascadeFault, check_cascade_fault
        monkeypatch.setenv("CASCADE_FAULT", "unique_violation")
        with pytest.raises(CascadeFault, match="unique_violation"):
            check_cascade_fault("unique_violation")


# ─────────────────────────────────────────────────────────────
# AC #10: trust_set computational entry — DEFERRED
# ─────────────────────────────────────────────────────────────


class TestAC10TrustSetComputational:
    @pytest.mark.skip(reason="DEFERRED: computational trust entry written by "
                              "Counterexample silver commit (task.md ## "
                              "延後 cycles)")
    def test_silver_writes_computational_entry(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# Twin cascade smoke gate — sanity that C30 wiring lands here
# ─────────────────────────────────────────────────────────────


class TestTwinCascadeSmoke:
    """Acceptance-level smoke gate: C30 twin cascade (¬G proved → G refuted)
    fires on _update_goal_proved. Detailed behaviour tested in
    test_cascade_twin.py; this gate just confirms the wire-in survives
    P4 acceptance."""

    def test_neg_proved_flips_g_to_refuted(self, db, tmp_path) -> None:
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="g_smoke", kind="conjecture")
        # Pre-existing ¬G via raw insert (Refuter would do this in real run)
        with db:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, "
                "commit_state, twin_of, depth, created_at, updated_at) "
                "VALUES ('p4_demo', 'neg_g_smoke', 'path/neg.lean', "
                "'refuter_negation', 'theorem', 'open', 'live', ?, 0, "
                "?, ?)",
                (gid, _NOW, _NOW),
            )
            neg_id = db.execute(
                "SELECT id FROM goals WHERE slug='neg_g_smoke'"
            ).fetchone()[0]
            db.execute(
                "UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid)
            )

        cfg = ReactorConfig(base_dir=str(tmp_path), pool_size=1)
        r = Reactor(str(tmp_path / "test.db"), cfg)
        r.conn = db
        ad = json.dumps({
            "type": "classical",
            "lean_path": "path/neg.lean",
        })
        r._update_goal_proved(neg_id, ad, trust_set_json=None)

        g_row = db.execute(
            "SELECT status, answer_data FROM goals WHERE id = ?", (gid,)
        ).fetchone()
        assert g_row[0] == "refuted"
        ad_obj = json.loads(g_row[1])
        assert ad_obj["type"] == "classical"
        assert ad_obj["negation_goal_id"] == neg_id
