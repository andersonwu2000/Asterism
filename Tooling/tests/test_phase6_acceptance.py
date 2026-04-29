"""P6 Acceptance tests #0a / #0b / #0c (manual gates) + #1-#11.

Mapping to phase6_library.md ## Acceptance criteria:

  AC #0a Demo A+B end-to-end (cross-Problem import)        — manual gate
  AC #0b Demo C end-to-end (single-Problem reject)         — manual gate
  AC #0c Demo D end-to-end (cross-Problem axiom reject +
         manual problem pause + cascade skip)              — manual gate
  AC #1  Multi-Problem reactor BFS                         — covered
  AC #1a Multi-Problem stress (5 Problems × 3 roots)       — manual gate
  AC #2  Library/Theorems promotion                        — covered (smoke)
  AC #3  Cross-Problem import via Library                   — manual gate
  AC #4a Axiom check pass                                   — covered
  AC #4b Axiom check reject                                 — covered
  AC #5  Per-Problem proved.lean covers all origins        — covered (smoke)
  AC #6  First-write-wins                                   — covered (smoke)
  AC #7  Promotion fail revert (LIBRARY_BUILD_FAULT=1)      — covered
  AC #8  Library reindex migration                          — covered
  AC #9  Library.whitelist filters RH-dependent             — covered
  AC #10 schedulers liveness w/ --bypass-startup-check      — covered
  AC #11 scheduler force-clear rescue                       — covered (CLI smoke)

The covered tests here are summary-only — most go through the
existing per-cycle test files (test_library_promotion, test_cli_c44,
test_scheduler_c44, test_library_c45). This module is the spec-mapped
roll-up gate so phase 6 sign-off has a single in-process target.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling.cli import (
    cmd_library_check_deps,
    cmd_library_reindex,
    cmd_problem_pause,
    cmd_scheduler_force_clear,
)
from Tooling.db.connect import connect, init_schema
from Tooling.library.check_deps import check_axiom_coverage
from Tooling.library.promotion import promote_to_library
from Tooling.library.reindex import reindex_library
from Tooling.scheduler import FatalError, Reactor, ReactorConfig


_NOW = "2026-01-01T00:00:00+00:00"


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "asterism.db"
    conn = connect(p)
    init_schema(conn)
    conn.close()
    return p


def _write_meta(base: Path, problem: str, axioms: list[str]) -> None:
    p_dir = base / "Problems" / problem
    p_dir.mkdir(parents=True, exist_ok=True)
    body = "---\n"
    body += f"problem_name: {problem}\n"
    body += "axioms:\n"
    for a in axioms:
        body += f"  - {a}\n"
    body += "---\n"
    (p_dir / "META.md").write_text(body, encoding="utf-8")


def _seed_open_goal(conn: sqlite3.Connection, problem: str, slug: str) -> int:
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, depth, created_at, updated_at) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'open', 'live', 0, ?, ?)",
            (problem, slug, f"path/{slug}.lean", _NOW, _NOW),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_proved_classical(
    conn: sqlite3.Connection,
    *,
    problem: str,
    slug: str,
    axiom_names: list[str] | None = None,
    lean_path: str | None = None,
) -> int:
    """Insert a proved classical Goal qualifying for Library promotion."""
    axiom_names = axiom_names or ["propext"]
    ts = json.dumps([{"kind": "lean_axiom", "name": n} for n in axiom_names])
    ad = json.dumps({
        "type": "classical",
        "lean_path": f"Problems/{problem}/Goals/g/{slug}.lean",
    })
    # lean_path must be UNIQUE; default uses problem+slug+rowid suffix
    if lean_path is None:
        suffix = conn.execute(
            "SELECT IFNULL(MAX(id), 0) + 1 FROM goals"
        ).fetchone()[0]
        lean_path = f"path/{problem}_{slug}_{suffix}.lean"
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, trust_set, created_at, updated_at) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'proved', 'live', "
            "?, ?, ?, ?)",
            (
                problem, slug, lean_path,
                ad, ts, _NOW, _NOW,
            ),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ─────────────────────────────────────────────────────────────
# Manual gates (real lake required)
# ─────────────────────────────────────────────────────────────


class TestManualGates:
    @pytest.mark.skip(reason="manual gate: AC #0a Demo A+B end-to-end requires "
                              "real lake env + claude CLI + cross-Problem build "
                              "(see phase6_library.md ## Demo)")
    def test_0a_demo_a_b_cross_problem(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: AC #0b Demo C requires real lake env "
                              "(see phase6_library.md ## Demo)")
    def test_0b_demo_c_single_problem_reject(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: AC #0c Demo D requires real lake env "
                              "+ user-driven `asterism problem pause` step "
                              "(see phase6_library.md ## Demo)")
    def test_0c_demo_d_cross_problem_axiom_reject(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: AC #1a stress test 5 Problems × 3 "
                              "roots × 30 min real run (phase6_library.md AC#1a)")
    def test_1a_multi_problem_stress(self) -> None:
        pass

    @pytest.mark.skip(reason="manual gate: AC #3 cross-Problem import via "
                              "Library lemma + Backward find_lemmas via search "
                              "(library scope) — needs real lake")
    def test_3_cross_problem_import(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #1 — Multi-Problem reactor BFS
# ─────────────────────────────────────────────────────────────


class TestMultiProblemBFS:
    def test_bfs_enqueues_backward_for_each_problem(self, db_path, tmp_path):
        """A single Reactor structural-refill tick enqueues attack
        pipelines for open Goals from multiple Problems.

        P7 演習 refactor: first attack is Solver, not Backward. AC's
        meaningful invariant is "BFS visits each Problem"; the kind is
        secondary. Assert Solver attack is queued for both Problems.
        """
        conn = connect(db_path)
        try:
            g_a = _seed_open_goal(conn, "alpha", "g1")
            g_b = _seed_open_goal(conn, "beta", "g2")

            reactor = Reactor(
                str(db_path),
                ReactorConfig(base_dir=str(tmp_path)),
            )
            reactor.conn = conn
            reactor._run_structural_refill()

            queue = conn.execute(
                "SELECT kind, target_id FROM queue ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        # Expect Solver for both goals, one row each (Backward only fires
        # after Solver finishes — see _bfs_enqueue_solver / _bfs_enqueue_backward).
        solvers = [t for k, t in queue if k == "Solver"]
        assert str(g_a) in solvers
        assert str(g_b) in solvers


# ─────────────────────────────────────────────────────────────
# AC #2 + #5 + #6 — Promotion smoke (already covered in
# test_library_promotion; this is a single roll-up confirmation)
# ─────────────────────────────────────────────────────────────


class TestPromotionRollup:
    def test_classical_with_whitelist_axioms_promotes(self, db_path, tmp_path):
        """AC#2 + #5: classical proved with whitelist trust_set lands in
        both Library/Theorems/proved.lean and Problems/<p>/proved.lean +
        library_index INSERT."""
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="alpha", slug="add_comm",
                axiom_names=["propext"],
            )
            with patch.dict(
                os.environ, {"LIBRARY_VERIFY_NOOP": "1"}, clear=False,
            ):
                result = promote_to_library(conn, gid, tmp_path)
            assert result.library_theorems_appended is True
            assert result.per_problem_appended is True
            assert result.library_index_inserted is True
            # File checks
            lt = (tmp_path / "Library" / "Theorems" / "proved.lean").read_text(
                encoding="utf-8"
            )
            assert "alpha.add_comm" in lt
            pp = (tmp_path / "Problems" / "alpha" / "proved.lean").read_text(
                encoding="utf-8"
            )
            assert "alpha.add_comm" in pp
        finally:
            conn.close()

    def test_first_write_wins_blocks_duplicate_append(self, db_path, tmp_path):
        """AC#6: second promote with same lib_name does NOT append + emits
        the library_index_first_write_wins event."""
        conn = connect(db_path)
        try:
            g1 = _seed_proved_classical(
                conn, problem="alpha", slug="dup",
            )
            with patch.dict(
                os.environ, {"LIBRARY_VERIFY_NOOP": "1"}, clear=False,
            ):
                promote_to_library(conn, g1, tmp_path)
            # Second proved goal with same problem + slug (manual: this
            # only happens for hand-injected DB rows; the second row would
            # otherwise hit the unique constraint).
            g2 = _seed_proved_classical(
                conn, problem="alpha", slug="dup",
            )
            events: list[tuple[str, dict]] = []
            with patch.dict(
                os.environ, {"LIBRARY_VERIFY_NOOP": "1"}, clear=False,
            ):
                r2 = promote_to_library(
                    conn, g2, tmp_path,
                    emit_event=lambda k, p: events.append((k, p)),
                )
            assert r2.library_theorems_appended is False
            assert any(
                p.get("rule") == "library_index_first_write_wins"
                for _, p in events
            )
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #4a / #4b — Axiom-coverage check
# ─────────────────────────────────────────────────────────────


class TestAxiomCoverage:
    def test_4a_pass_when_axioms_match(self, db_path, tmp_path):
        _write_meta(tmp_path, "consumer", ["propext"])
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="src", slug="thm",
                axiom_names=["propext"],
            )
            with conn:
                conn.execute(
                    "INSERT INTO library_index "
                    "(layer, name, path, source_root_id, committed_at) "
                    "VALUES ('Theorems', 'src.thm', 'p', ?, ?)",
                    (gid, _NOW),
                )
            result = check_axiom_coverage(conn, tmp_path)
            assert result.violations == []
        finally:
            conn.close()

    def test_4b_reject_when_consumer_lacks_axiom(self, db_path, tmp_path):
        _write_meta(tmp_path, "consumer", ["propext"])  # missing Quot.sound
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="src", slug="thm",
                axiom_names=["propext", "Quot.sound"],
            )
            with conn:
                conn.execute(
                    "INSERT INTO library_index "
                    "(layer, name, path, source_root_id, committed_at) "
                    "VALUES ('Theorems', 'src.thm', 'p', ?, ?)",
                    (gid, _NOW),
                )
            result = check_axiom_coverage(conn, tmp_path)
            assert len(result.violations) == 1
            v = result.violations[0]
            assert v.consumer_problem == "consumer"
            assert "Quot.sound" in v.missing
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #7 — Promotion fail revert via LIBRARY_BUILD_FAULT
# ─────────────────────────────────────────────────────────────


class TestPromotionFailRevert:
    def test_library_build_fault_triggers_revert(self, db_path, tmp_path):
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="alpha", slug="fail_thm",
            )
            with patch.dict(
                os.environ, {"LIBRARY_BUILD_FAULT": "1"}, clear=False,
            ):
                result = promote_to_library(conn, gid, tmp_path)
            assert result.reverted is True
            # library_index row removed
            count = conn.execute(
                "SELECT COUNT(*) FROM library_index"
            ).fetchone()[0]
            assert count == 0
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #8 — reindex migration
# ─────────────────────────────────────────────────────────────


class TestLibraryReindex:
    def test_reindex_inserts_pre_existing_proved_lean_lines(
        self, db_path, tmp_path,
    ):
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="legacy", slug="thm",
            )
        finally:
            conn.close()
        # Hand-write a proved.lean line as if from pre-P6 promotion
        path = tmp_path / "Library" / "Theorems" / "proved.lean"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"theorem legacy.thm := Problems.legacy.Goals.{gid}_thm.thm\n",
            encoding="utf-8",
        )
        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
            assert "legacy.thm" in result.inserted
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #9 — Library.whitelist filters RH-dependent goals
# ─────────────────────────────────────────────────────────────


class TestWhitelistFilter:
    def test_rh_dependent_skipped_for_library_theorems(self, db_path, tmp_path):
        """A goal whose trust_set contains a non-whitelist axiom (e.g.
        riemann_hypothesis) is excluded from Library/Theorems/proved.lean
        but still lands in the per-Problem proved.lean."""
        conn = connect(db_path)
        try:
            gid = _seed_proved_classical(
                conn, problem="rh_consequences", slug="needs_rh",
                axiom_names=["propext", "riemann_hypothesis"],
            )
            with patch.dict(
                os.environ, {"LIBRARY_VERIFY_NOOP": "1"}, clear=False,
            ):
                result = promote_to_library(conn, gid, tmp_path)
            # Per-Problem yes, Library no
            assert result.per_problem_appended is True
            assert result.library_theorems_appended is False
            assert (
                tmp_path / "Library" / "Theorems" / "proved.lean"
            ).exists() is False or "rh_consequences" not in (
                tmp_path / "Library" / "Theorems" / "proved.lean"
            ).read_text(encoding="utf-8")
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #10 — schedulers liveness rejects double instance
# ─────────────────────────────────────────────────────────────


class TestSchedulerLiveness:
    def test_second_instance_rejected_when_first_alive(self, db_path, tmp_path):
        conn = connect(db_path)
        try:
            fresh = datetime.now(timezone.utc).isoformat()
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 1, ?, ?)",
                    (fresh, fresh),
                )
            # Without bypass: register raises
            r = Reactor(
                str(db_path),
                ReactorConfig(base_dir=str(tmp_path),
                              bypass_startup_check=False),
            )
            r.conn = conn
            with pytest.raises(FatalError):
                r._register_scheduler()
        finally:
            conn.close()

    def test_bypass_does_not_override_liveness(self, db_path, tmp_path):
        """AC#10 字面: 「liveness check 仍正常擋」. Bypass flag does NOT
        let a second instance through when the first is alive."""
        conn = connect(db_path)
        try:
            fresh = datetime.now(timezone.utc).isoformat()
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 1, ?, ?)",
                    (fresh, fresh),
                )
            r = Reactor(
                str(db_path),
                ReactorConfig(base_dir=str(tmp_path),
                              bypass_startup_check=True),
            )
            r.conn = conn
            with pytest.raises(FatalError):
                r._register_scheduler()
            # First instance row preserved
            count = conn.execute(
                "SELECT COUNT(*) FROM schedulers"
            ).fetchone()[0]
            assert count == 1
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# AC #11 — scheduler force-clear rescue path
# ─────────────────────────────────────────────────────────────


class TestForceClearRescue:
    def test_force_clear_clears_stale_row(self, db_path, capsys):
        conn = connect(db_path)
        try:
            stale = (
                datetime.now(timezone.utc) -
                __import__("datetime").timedelta(seconds=600)
            ).isoformat()
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 1, ?, ?)",
                    (stale, stale),
                )
        finally:
            conn.close()
        cmd_scheduler_force_clear(_args(force=False), db_path=db_path)
        out = capsys.readouterr().out
        assert "deleted 1" in out
        conn = connect(db_path)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM schedulers"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0
