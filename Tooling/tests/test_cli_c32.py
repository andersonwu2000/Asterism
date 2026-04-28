"""Tests for P4 C32 CLI extensions: goal show twin/silver-or-gold + conjecture mode."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from Tooling.cli import (
    cmd_goal_add,
    cmd_goal_show,
)
from Tooling.db.connect import connect, init_schema


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


def _seed_goal(
    db_path: Path,
    *,
    slug: str = "g",
    kind: str = "theorem",
    status: str = "open",
    twin_of: int | None = None,
    answer_data: dict | None = None,
    blocked: list[str] | None = None,
) -> int:
    conn = connect(db_path)
    try:
        ad = json.dumps(answer_data) if answer_data else None
        bp = json.dumps(blocked) if blocked else None
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, twin_of, answer_data, blocked_pipelines, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ex", slug, f"path/{slug}.lean", "root", kind, status, "live",
             twin_of, ad, bp, _NOW, _NOW),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# goal show — twin display
# ---------------------------------------------------------------------------


class TestGoalShowTwin:
    def test_twin_of_displayed(self, db_path, capsys):
        gid = _seed_goal(db_path, slug="g_twin")
        neg_id = _seed_goal(
            db_path, slug="neg_g_twin",
            kind="theorem", twin_of=gid,
        )
        # Bidirectional: G's twin_of also points to neg
        conn = connect(db_path)
        try:
            with conn:
                conn.execute("UPDATE goals SET twin_of=? WHERE id=?",
                             (neg_id, gid))
        finally:
            conn.close()

        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert f"twin_of:   G{neg_id}" in out
        assert "neg_g_twin" in out

    def test_no_twin_omits_twin_line(self, db_path, capsys):
        gid = _seed_goal(db_path, slug="g_solo")
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "twin_of:" not in out

    def test_twin_dangling_pointer_displays_missing(self, db_path, capsys):
        """If twin_of points to a goal that doesn't exist (rare DB
        recovery scenario), goal show shows <missing>."""
        gid = _seed_goal(db_path, slug="g_dangle")
        # Use raw UPDATE bypassing FK to simulate dangling
        conn = connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            with conn:
                conn.execute("UPDATE goals SET twin_of=999 WHERE id=?", (gid,))
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "twin_of:   G999 <missing>" in out


# ---------------------------------------------------------------------------
# goal show — silver/gold verdict_strength
# ---------------------------------------------------------------------------


class TestGoalShowVerdictStrength:
    def test_classical_shows_gold(self, db_path, capsys):
        gid = _seed_goal(
            db_path, slug="g_gold", status="proved",
            answer_data={"type": "classical", "lean_path": "path.lean"},
        )
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "verdict_strength: gold (classical proof)" in out

    def test_witness_shows_silver(self, db_path, capsys):
        gid = _seed_goal(
            db_path, slug="g_silver_w", status="refuted",
            answer_data={"type": "witness", "witness": "n=2"},
        )
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "verdict_strength: silver (witness-only" in out

    def test_construction_shows_silver(self, db_path, capsys):
        gid = _seed_goal(
            db_path, slug="g_silver_c", status="proved",
            answer_data={"type": "construction", "score": 0.95},
        )
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "verdict_strength: silver (construction-only" in out

    def test_no_answer_data_no_strength_line(self, db_path, capsys):
        gid = _seed_goal(db_path, slug="g_open", status="open")
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "verdict_strength" not in out


# ---------------------------------------------------------------------------
# goal show — blocked_pipelines
# ---------------------------------------------------------------------------


class TestGoalShowBlocked:
    def test_blocked_displayed(self, db_path, capsys):
        gid = _seed_goal(
            db_path, slug="g_blocked", blocked=["Backward", "Refuter"],
        )
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "blocked:   Backward, Refuter" in out

    def test_no_blocked_omits_line(self, db_path, capsys):
        gid = _seed_goal(db_path, slug="g_unblocked")
        cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        out = capsys.readouterr().out
        assert "blocked:" not in out

    def test_blocked_malformed_json_loud(self, db_path, capsys):
        """C32 R3 MED-1 + LOW-3: malformed blocked_pipelines JSON must
        produce a loud stderr surface + sys.exit(1) — not a silent skip.
        Pins the silent-failure red-line invariant established by
        C29 R3 (_extract_witness_block) extended to CLI display path."""
        gid = _seed_goal(db_path, slug="g_corrupt")
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE goals SET blocked_pipelines=? WHERE id=?",
                    ("{not valid", gid),
                )
        finally:
            conn.close()
        with pytest.raises(SystemExit):
            cmd_goal_show(_args(goal_id=str(gid)), db_path=db_path)
        err = capsys.readouterr().err
        assert "blocked_pipelines" in err
        assert "malformed JSON" in err


# ---------------------------------------------------------------------------
# goal add --kind conjecture
# ---------------------------------------------------------------------------


class TestGoalAddConjecture:
    def test_conjecture_kind_print_message(self, db_path, tmp_path, capsys):
        cmd_goal_add(
            _args(problem="ex", slug="conj1", kind="conjecture",
                  spec="∀ n, P n", spec_file=None, leaf_strategy=None),
            db_path=db_path, base_dir=tmp_path,
        )
        out = capsys.readouterr().out
        assert "kind:         conjecture" in out
        assert "queued Backward task" in out
        assert "conjecture mode" in out
        assert "Refuter will be enqueued" in out
        assert "Counterexample line is deferred" in out

    def test_theorem_kind_no_conjecture_message(self, db_path, tmp_path, capsys):
        cmd_goal_add(
            _args(problem="ex", slug="thm1", kind="theorem",
                  spec="True", spec_file=None, leaf_strategy=None),
            db_path=db_path, base_dir=tmp_path,
        )
        out = capsys.readouterr().out
        assert "kind:         theorem" in out
        # Should NOT print conjecture mode message
        assert "conjecture mode" not in out
        assert "Refuter will be enqueued" not in out

    def test_conjecture_kind_inserts_goal_with_kind(self, db_path, tmp_path):
        cmd_goal_add(
            _args(problem="ex", slug="conj2", kind="conjecture",
                  spec="∀ n, n^2 ≥ 0", spec_file=None, leaf_strategy=None),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT kind, question FROM goals WHERE slug='conj2'"
            ).fetchone()
            assert row[0] == "conjecture"
            assert row[1] == "∀ n, n^2 ≥ 0"
        finally:
            conn.close()
