"""P2 Acceptance tests #0–#11.

Covers `docs/dev/phase2_decomposition.md ## Acceptance criteria` in order.
Each class maps to one acceptance criterion.

Mock strategy:
  - lake calls         → LAKE_MOCK env (P1 hook)
  - print axioms       → PRINT_AXIOMS_MOCK env (P1 hook)
  - Backward.run agent → BACKWARD_MOCK env (P2 hook, added in C18)
  - Builder agent      → patched at provider level when needed

Caveats:
  - #2a / #2b warm/cold cache wall-clock require real `lake env lean` +
    Mathlib; gated as manual orchestrator verification (skipped here).
  - #9 daemon idle CPU is a timing test; covered minimally as a smoke
    "daemon shuts down promptly on shutdown signal".

#0 demo subprocess is the single sanity gate per phase2 §Acceptance line 115.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.cli import cmd_db_recover, cmd_goal_add, cmd_goal_show, cmd_init, cmd_run
from Tooling.commit import CommitFault, CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.backward import Backward, BackwardConfig, BackwardResult
from Tooling.pipelines.builder import Builder, BuilderConfig, BuilderResult
from Tooling.scheduler import FatalError, Reactor, ReactorConfig
from Tooling.stages.validator import ValidatorError


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent.parent
_NOW = "2026-01-01T00:00:00+00:00"


def _make_db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    db_path = tmp_path / "asterism.db"
    conn = connect(db_path)
    init_schema(conn)
    return db_path, conn


def _args(**kwargs):
    """argparse Namespace; getattr defaults work (unlike MagicMock)."""
    return argparse.Namespace(**kwargs)


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    problem: str = "ex",
    slug: str = "g",
    lean_path: str | None = None,
    status: str = "open",
    kind: str = "theorem",
    depth: int | None = 0,
    question: str | None = None,
    commit_state: str = "live",
) -> int:
    if lean_path is None:
        lean_path = f"Problems/{problem}/Goals/_g_{slug}.lean"
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, depth, question, "
        "commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, lean_path, "root", kind, status, depth, question,
         commit_state, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_strategy(
    conn: sqlite3.Connection,
    goal_id: int,
    lean_path: str,
    status: str = "proposed",
    commit_state: str = "live",
) -> int:
    conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, status, commit_state, created_at) "
        "VALUES (?,?,?,?,?)",
        (goal_id, lean_path, status, commit_state, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _enqueue(conn: sqlite3.Connection, target_id: int | str, kind: str = "Backward") -> None:
    conn.execute(
        "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?,?,?,?)",
        (kind, str(target_id), 0, _NOW),
    )
    conn.commit()


def _link_subgoal(
    conn: sqlite3.Connection, strategy_id: int, subgoal_id: int, position: int = 0
) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?,?,?)",
        (strategy_id, subgoal_id, position),
    )
    conn.commit()


# ─────────────────────────────────────────────────────────────
# AC #0: Demo subprocess (init → goal add --spec → run --once → goal show)
# ─────────────────────────────────────────────────────────────


class TestAC0DemoSubprocess:
    """#0: Full P2 demo via subprocess.

    Combines LAKE_MOCK=proved + BACKWARD_MOCK=success_leaf + PRINT_AXIOMS_MOCK
    to exercise the entire init→goal_add(--spec)→run(--once)→goal_show chain
    without needing a real Lean install. This is the phase2 §Acceptance line
    115 single sanity gate.
    """

    def _cli_cmd(self) -> list[str]:
        asterism = shutil.which("asterism")
        if asterism:
            return [asterism]
        return [sys.executable, "-m", "Tooling.cli"]

    def _run(
        self, args: list[str], tmp_path: Path, extra_env: dict
    ) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT), **extra_env}
        return subprocess.run(
            self._cli_cmd() + args,
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Windows default cp950 chokes on `∀` in spec print
        )

    def test_demo_spec_to_proved(self, tmp_path: Path) -> None:
        env = {
            "LAKE_MOCK": "proved",
            "BACKWARD_MOCK": "success_leaf",
            "PRINT_AXIOMS_MOCK": "propext,Quot.sound,Classical.choice",
            # Force UTF-8 for subprocess stdout (Windows default cp950 chokes on `∀`)
            "PYTHONIOENCODING": "utf-8",
        }

        # 1. init
        r = self._run(["init", "--problem", "sg"], tmp_path, env)
        assert r.returncode == 0, f"init: {r.stderr}"
        assert (tmp_path / "Problems" / "sg" / "META.md").exists()

        # 2. goal add --spec  (P2 path; enqueues Backward)
        r = self._run([
            "goal", "add",
            "--problem", "sg",
            "--slug", "add_comm_demo",
            "--kind", "theorem",
            "--spec", "∀ m n : Nat, m + n = n + m",
        ], tmp_path, env)
        assert r.returncode == 0, f"goal add: {r.stderr}"
        assert "queued Backward" in r.stdout

        # 3. run --once
        r = self._run(["run", "--once"], tmp_path, env)
        assert r.returncode == 0, f"run: {r.stderr}"

        # 4. goal show G_root
        r = self._run(["goal", "show", "G_root"], tmp_path, env)
        assert r.returncode == 0, f"goal show: {r.stderr}"
        assert "proved" in r.stdout, f"expected 'proved' in: {r.stdout}"
        assert "classical" in r.stdout, f"expected 'classical' in: {r.stdout}"


# ─────────────────────────────────────────────────────────────
# AC #1: Agent scope isolation
# ─────────────────────────────────────────────────────────────


class TestAC1AgentScopeIsolation:
    """#1: Backward agent writing outside staging dir → stage failed → retry → exhausted.

    Phase2 spec: runtime detects out-of-scope writes; stage fails; retry up to
    max_retries then exhausted. The detection layer is the FallbackChain
    `scope_dirs` argument forwarded to provider; provider rejects out-of-scope.
    """

    def test_agent_chain_returns_none_propagates_to_exhausted(
        self, tmp_path: Path
    ) -> None:
        """When chain.run returns (None, 'exhausted') → Backward returns
        BackwardResult(outcome='exhausted'). Mirrors what FallbackChain does
        when provider rejects all retry attempts (out-of-scope write being
        one such failure mode handled inside provider)."""
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(
            conn, slug="g_iso", question="True",
            lean_path=str(tmp_path / "g.lean"),
        )
        chain = MagicMock()
        chain.run.return_value = (None, "exhausted")
        cfg = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        result = Backward(conn, chain, cfg).run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count >= 1


# ─────────────────────────────────────────────────────────────
# AC #2a / #2b: warm/cold cache wall-clock — manual gate
# ─────────────────────────────────────────────────────────────


class TestAC2WallClock:
    """#2a/2b require real `lake env lean` + Mathlib + claude CLI; gated as
    manual orchestrator demo verification per phase2 line 117/118."""

    @pytest.mark.skip(reason="manual gate: requires real lake env + Mathlib (warm cache < 5 min)")
    def test_warm_cache_under_5min(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: requires real lake env + Mathlib (cold cache < 20 min)")
    def test_cold_cache_under_20min(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #3: Cascade upward (sub-Goal proved → enqueue Builder for parent)
# ─────────────────────────────────────────────────────────────


class TestAC3CascadeUpward:
    """#3: When all sub-Goals of a Strategy become proved, structural refill
    enqueues Builder for that parent Strategy on the next reactor cycle.

    Tested via direct call to _structural_refill_strategies (invoked by daemon
    every 30s tick or post-pipeline_finished step 6).
    """

    def test_strategy_with_all_subgoals_proved_enqueued_for_builder(
        self, tmp_path: Path
    ) -> None:
        _, conn = _make_db(tmp_path)
        parent_g = _insert_goal(conn, slug="parent")
        sub_g = _insert_goal(conn, slug="sub", status="proved")
        # Parent strategy proposed (not yet built); sub-goal proved.
        strat = _insert_strategy(
            conn, parent_g, str(tmp_path / "p_strat.lean"), status="proposed"
        )
        _link_subgoal(conn, strat, sub_g)

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn

        # Run BFS-side structural refill
        reactor._run_structural_refill()

        # Builder for the parent strategy should be enqueued.
        rows = conn.execute(
            "SELECT kind, target_id FROM queue WHERE kind='Builder'"
        ).fetchall()
        assert (("Builder", str(strat))) in [(r[0], r[1]) for r in rows], \
            f"expected Builder enqueued for strategy {strat}; got {rows}"


# ─────────────────────────────────────────────────────────────
# AC #4: Multi-row commit TX recovery (Backward begin_batch + COMMIT_FAULT)
# ─────────────────────────────────────────────────────────────


class TestAC4MultiRowCommitTX:
    """#4: COMMIT_FAULT during Backward._commit batch → recover_scan deletes
    all pending rows (strategies + sub-goals + junction)."""

    def test_commit_fault_after_step1_leaves_no_partial_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, slug="g4", question="True",
                               lean_path=str(tmp_path / "g4.lean"))
        Path(tmp_path / "g4.lean").write_text("-- placeholder\n", encoding="utf-8")

        # Snapshot count before
        before_strats = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
        before_sgs = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE origin='backward'"
        ).fetchone()[0]

        # Force COMMIT_FAULT during batch finalize  (P1 hook respected by
        # CommitWriter for any begin_batch caller, including Backward._commit).
        monkeypatch.setenv("COMMIT_FAULT", "after_step1")

        chain = MagicMock()
        chain.run.return_value = (
            MagicMock(output=json.dumps({
                "subgoals": [{"slug": "sub_a", "statement": "Nat.zero = 0"}]
            })),
            "success",
        )
        cfg = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))

        # Patch validator + self_verify to bypass real Lean checks
        with patch("Tooling.pipelines.backward.validate", return_value=[]), \
             patch.object(Backward, "_self_verify_per_file",
                          new=lambda self, sgs: (True, sgs)):
            try:
                Backward(conn, chain, cfg).run(goal_id)
            except CommitFault:
                pass  # expected

        # recover_scan must wipe pending rows
        writer = CommitWriter(conn)
        writer.recover_scan()

        after_strats = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
        after_sgs = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE origin='backward'"
        ).fetchone()[0]
        junction = conn.execute("SELECT COUNT(*) FROM strategy_subgoals").fetchone()[0]

        assert after_strats == before_strats, "strategies row leaked past recovery"
        assert after_sgs == before_sgs, "backward sub-goal row leaked past recovery"
        assert junction == 0, "junction row leaked past recovery"


# ─────────────────────────────────────────────────────────────
# AC #5: Validator hypothesis carry
# ─────────────────────────────────────────────────────────────


class TestAC5ValidatorHypothesisCarry:
    """#5: Backward agent proposes a sub-Goal whose statement drops a parent
    hypothesis binder → validator returns errors → Backward retries from
    agent stage."""

    def test_validation_error_triggers_retry(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(
            conn, slug="g5",
            question="∀ (h : 0 < n), n ≠ 0",
            lean_path=str(tmp_path / "g5.lean"),
        )
        chain = MagicMock()
        # Same response twice — validator rejects both → exhausted.
        chain.run.return_value = (
            MagicMock(output=json.dumps({
                "subgoals": [{"slug": "miss_h", "statement": "n ≠ 0"}]
            })),
            "success",
        )
        cfg = BackwardConfig(
            base_dir=str(tmp_path), lake_cwd=str(tmp_path), max_retries=2
        )
        with patch(
            "Tooling.pipelines.backward.validate",
            return_value=[ValidatorError(
                check="hyp_carry",
                detail="sub-goal `miss_h` drops parent binder `h`",
            )],
        ):
            result = Backward(conn, chain, cfg).run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2  # two retries hit max → exhausted


# ─────────────────────────────────────────────────────────────
# AC #6: Trust set construction
# ─────────────────────────────────────────────────────────────


class TestAC6TrustSetConstruction:
    """#6: When cascade marks a Goal proved, build_trust_set runs
    `lake env lean -e '#print axioms ...'` and stores axiom names in
    goals.trust_set as lean_axiom entries."""

    def test_trust_set_populated_with_axiom_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "propext,Quot.sound,Classical.choice")

        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(
            conn, slug="g6_thm", question="True",
            lean_path=str(tmp_path / "g6.lean"),
        )
        Path(tmp_path / "g6.lean").write_text(
            "theorem g6_thm : True := trivial\n", encoding="utf-8"
        )
        # Write Problem META.md with classical axioms whitelist
        meta_dir = tmp_path / "Problems" / "ex"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "META.md").write_text(
            "---\nproblem_name: ex\naxioms:\n"
            "  - propext\n  - Quot.sound\n  - Classical.choice\n---\n",
            encoding="utf-8",
        )
        strat = _insert_strategy(
            conn, goal_id, str(tmp_path / "strat6.lean"), status="proposed"
        )

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn

        # Trigger cascade for proved Builder result
        reactor._cascade_builder(strat, BuilderResult(outcome="proved", tactic="trivial"))

        ts_json = conn.execute(
            "SELECT trust_set FROM goals WHERE id=?", (goal_id,)
        ).fetchone()[0]
        ts = json.loads(ts_json)
        assert isinstance(ts, list) and ts, f"trust_set empty: {ts_json}"
        names = {e["name"] for e in ts}
        assert names == {"propext", "Quot.sound", "Classical.choice"}, names
        assert all(e["kind"] == "lean_axiom" for e in ts)


# ─────────────────────────────────────────────────────────────
# AC #7: Accept rule reject
# ─────────────────────────────────────────────────────────────


class TestAC7AcceptRuleReject:
    """#7: META.md axioms whitelist excludes Classical.choice; theorem proves
    using Classical.choice → cascade reject; Goal stays attempting; emit
    dead_attempts row + ('control_signal', 'pause') on event_queue.
    """

    def test_reject_writes_dead_attempts_and_pauses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Theorem actually depends on Classical.choice but META whitelist drops it.
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "propext,Quot.sound,Classical.choice")

        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(
            conn, slug="g7_thm", question="True",
            lean_path=str(tmp_path / "g7.lean"),
        )
        Path(tmp_path / "g7.lean").write_text("-- stub\n", encoding="utf-8")
        meta_dir = tmp_path / "Problems" / "ex"
        meta_dir.mkdir(parents=True, exist_ok=True)
        # Note: Classical.choice deliberately removed
        (meta_dir / "META.md").write_text(
            "---\nproblem_name: ex\naxioms:\n  - propext\n  - Quot.sound\n---\n",
            encoding="utf-8",
        )
        strat = _insert_strategy(
            conn, goal_id, str(tmp_path / "strat7.lean"), status="proposed"
        )
        # Insert a Builder pipeline row so _record_accept_reject_dead_attempt
        # (which has FK to pipelines) can write the dead_attempts row.
        import uuid as _uuid
        pid = str(_uuid.uuid4())
        conn.execute(
            "INSERT INTO pipelines (id, kind, runtime, target_id, target_kind, "
            "status, started_at) VALUES (?,?,?,?,?,?,?)",
            (pid, "Builder", "atomic", str(strat), "Strategy", "succeeded", _NOW),
        )
        conn.commit()

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn

        reactor._cascade_builder(strat, BuilderResult(outcome="proved", tactic="exact Classical.choice _"))

        # 1. Goal still attempting (not proved)
        status = conn.execute(
            "SELECT status FROM goals WHERE id=?", (goal_id,)
        ).fetchone()[0]
        assert status != "proved", f"reject path must NOT mark proved; got {status}"

        # 2. dead_attempts row written
        rows = conn.execute(
            "SELECT reason_summary FROM dead_attempts WHERE target_id=?",
            (str(goal_id),),
        ).fetchall()
        assert any("trust_set" in r[0].lower() or "rejected" in r[0].lower()
                   for r in rows), f"no rejection dead_attempt: {rows}"

        # 3. pause control_signal emitted
        events = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())
        assert ("control_signal", "pause") in events, f"no pause emit: {events}"


# ─────────────────────────────────────────────────────────────
# AC #8: D_max bound (depth=12 → shelved)
# ─────────────────────────────────────────────────────────────


class TestAC8DMaxBound:
    """#8: structural refill UPDATEs depth>=12 Goals to shelved instead of
    enqueueing Backward."""

    def test_depth_12_goal_shelved_not_enqueued(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        deep_id = _insert_goal(
            conn, slug="deep", depth=12, status="open",
        )
        shallow_id = _insert_goal(
            conn, slug="shallow", depth=3, status="open",
            lean_path="Problems/ex/Goals/_g_shallow.lean",
        )

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn
        reactor._run_structural_refill()

        # deep_id → shelved
        deep_status = conn.execute(
            "SELECT status FROM goals WHERE id=?", (deep_id,)
        ).fetchone()[0]
        assert deep_status == "shelved", f"depth=12 should be shelved, got {deep_status}"

        # shallow_id → Backward enqueued
        kinds = [r[0] for r in conn.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(shallow_id),)
        ).fetchall()]
        assert "Backward" in kinds, f"shallow should be enqueued: {kinds}"

        # No Backward enqueued for deep
        deep_kinds = [r[0] for r in conn.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(deep_id),)
        ).fetchall()]
        assert "Backward" not in deep_kinds, f"deep should NOT be enqueued: {deep_kinds}"


# ─────────────────────────────────────────────────────────────
# AC #9: daemon idle → shutdown promptly (CPU idle is timing-sensitive,
#        substituted with a "shutdown latency under cap" smoke test)
# ─────────────────────────────────────────────────────────────


class TestAC9DaemonIdle:
    """#9: phase2 spec says reactor block on event_bus (no busy poll) AND
    respond to control_signal within 30s. The CPU-idle assertion is timing-
    sensitive in CI; we cover the latter (response-within-cap) instead."""

    def test_daemon_responds_to_shutdown_within_5s(
        self, tmp_path: Path
    ) -> None:
        db_path, _conn = _make_db(tmp_path)
        _conn.close()

        reactor = Reactor(str(db_path),
                          ReactorConfig(base_dir=str(tmp_path)))

        def _send_shutdown() -> None:
            time.sleep(0.5)
            reactor._event_queue.put(("control_signal", "shutdown"))

        t = threading.Thread(target=_send_shutdown, daemon=True)
        t.start()

        start = time.monotonic()
        reactor.run_daemon()
        elapsed = time.monotonic() - start
        t.join(timeout=2)

        # Phase2 spec: "30s 內回應". Tighter cap (5s) confirms get(timeout=2)
        # path actually wakes on signal rather than blocking until tick.
        assert elapsed < 5.0, f"daemon took {elapsed:.2f}s to shutdown"


# ─────────────────────────────────────────────────────────────
# AC #10: Model resolution two-layer (framework default + META.md override)
# ─────────────────────────────────────────────────────────────


class TestAC10ModelResolutionTwoLayer:
    """#10: META.md `models: { backward.agent: opus }` overrides framework
    default `sonnet` for the backward.agent stage. Strategist override (3rd
    layer) deferred to P7."""

    def test_meta_override_takes_effect(self, tmp_path: Path) -> None:
        from Tooling.agent.provider import ModelResolver
        from Tooling.meta import parse_meta

        meta_dir = tmp_path / "Problems" / "sg"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "META.md").write_text(
            "---\nproblem_name: sg\naxioms:\n"
            "  - propext\n  - Quot.sound\n  - Classical.choice\n"
            "models:\n  backward.agent: opus\n---\n",
            encoding="utf-8",
        )

        meta = parse_meta(meta_dir)
        resolver = ModelResolver(meta_models=meta.models)

        assert resolver.resolve("backward", "agent") == "opus"
        # Unspecified stage falls back to framework default
        assert resolver.resolve("builder", "tactic_llm") != "opus"

    def test_no_meta_override_uses_framework_default(self, tmp_path: Path) -> None:
        from Tooling.agent.provider import ModelResolver
        resolver = ModelResolver()
        # Phase2 §Config: backward.agent = sonnet, builder.tactic_llm = haiku
        assert resolver.resolve("backward", "agent") == "sonnet"
        assert resolver.resolve("builder", "tactic_llm") == "haiku"


# ─────────────────────────────────────────────────────────────
# AC #11: Stop-gap retry cap (in-memory)
# ─────────────────────────────────────────────────────────────


class TestAC11RetryStopGap:
    """#11: After N_block_after_failures=5 Backward exhausted attempts on the
    same Goal, structural refill skips that (Goal, Backward) tuple.

    P3 C25 update: in-memory _failure_count was removed; the canonical block
    source is now persistent goals.blocked_pipelines (C24). The acceptance
    behavior is the same — 5 failures → BFS skips — but the persistence
    semantics flipped (now survives restart instead of resetting).
    """

    def test_after_5_failures_bfs_skips_goal(self, tmp_path: Path) -> None:
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, slug="g11", status="open", depth=0)

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn

        # P3 C25: persistent block via goals.blocked_pipelines (was 5x
        # _inc_failure_count on the removed in-memory dict).
        block_pipeline(conn, goal_id, "Backward")

        reactor._run_structural_refill()

        kinds = [r[0] for r in conn.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(goal_id),)
        ).fetchall()]
        assert "Backward" not in kinds, f"should skip after block: {kinds}"

    def test_unblocked_goal_still_enqueued(self, tmp_path: Path) -> None:
        """P3 C25: dual to test_after_5_failures — unblocked goal still gets enqueued."""
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, slug="g11b", status="open", depth=0)

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = conn

        # No block applied
        reactor._run_structural_refill()

        kinds = [r[0] for r in conn.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(goal_id),)
        ).fetchall()]
        assert "Backward" in kinds, f"unblocked should enqueue: {kinds}"

    def test_block_persists_across_reactor_instances(self, tmp_path: Path) -> None:
        """P3 C25: persistent block survives scheduler restart. This is the
        semantics flip from P2 (in-memory reset on restart) → C24 persistent
        DB-backed block."""
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, slug="g11c", status="open", depth=0)

        r1 = Reactor(str(tmp_path / "asterism.db"),
                     ReactorConfig(base_dir=str(tmp_path)))
        r1.conn = conn
        block_pipeline(conn, goal_id, "Backward")

        # Fresh reactor: block persists in DB
        r2 = Reactor(str(tmp_path / "asterism.db"),
                     ReactorConfig(base_dir=str(tmp_path)))
        r2.conn = conn
        from Tooling.subsystems.blocked_pipelines import is_blocked
        assert is_blocked(conn, goal_id, "Backward") is True
        # BFS in r2 still skips the blocked goal
        r2._run_structural_refill()
        kinds = [row[0] for row in conn.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(goal_id),)
        ).fetchall()]
        assert "Backward" not in kinds
