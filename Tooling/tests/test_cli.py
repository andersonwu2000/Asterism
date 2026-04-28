"""Unit tests for Tooling/cli.py.

File-system operations use tmp_path (real I/O).
DB operations use a temp file DB via tmp_path.
Reactor.run and CommitWriter.recover_scan are mocked where testing integration
points rather than the full pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.cli import (
    _parse_goal_id,
    _resolve_goal_id,
    build_parser,
    cmd_db_recover,
    cmd_goal_add,
    cmd_goal_show,
    cmd_init,
    cmd_run,
    cmd_stop,
)
from Tooling.db.connect import connect, init_schema


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _db(tmp_path: Path):
    db_path = tmp_path / "asterism.db"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def _args(**kwargs):
    """Tiny namespace builder for argparse-style args.

    Uses argparse.Namespace so that getattr(ns, name, default) returns the
    default for unset attributes (MagicMock would return a child MagicMock,
    breaking any `arg is None` checks downstream).
    """
    return argparse.Namespace(**kwargs)


# ──────────────────────────────────────────────────────────────
# _parse_goal_id
# ──────────────────────────────────────────────────────────────


class TestParseGoalId:
    def test_integer_string(self):
        assert _parse_goal_id("1") == 1

    def test_g_underscore_prefix(self):
        assert _parse_goal_id("G_42") == 42

    def test_g_prefix_no_underscore(self):
        assert _parse_goal_id("G7") == 7

    def test_case_insensitive(self):
        assert _parse_goal_id("g_3") == 3

    def test_invalid_returns_none(self):
        assert _parse_goal_id("root") is None
        assert _parse_goal_id("G_abc") is None


# ──────────────────────────────────────────────────────────────
# init
# ──────────────────────────────────────────────────────────────


class TestInit:
    def test_creates_directory_structure(self, tmp_path):
        cmd_init(_args(problem="example"), base_dir=tmp_path)
        prob = tmp_path / "Problems" / "example"
        assert (prob / "META.md").exists()
        assert (prob / "Defs.lean").exists()
        assert (prob / "Root.lean").exists()

    def test_meta_contains_axioms(self, tmp_path):
        cmd_init(_args(problem="example"), base_dir=tmp_path)
        content = (tmp_path / "Problems" / "example" / "META.md").read_text(encoding="utf-8")
        assert "propext" in content
        assert "Quot.sound" in content
        assert "Classical.choice" in content

    def test_idempotent(self, tmp_path):
        cmd_init(_args(problem="example"), base_dir=tmp_path)
        meta_before = (tmp_path / "Problems" / "example" / "META.md").read_text(encoding="utf-8")
        # Run again — should not overwrite existing files.
        cmd_init(_args(problem="example"), base_dir=tmp_path)
        meta_after = (tmp_path / "Problems" / "example" / "META.md").read_text(encoding="utf-8")
        assert meta_before == meta_after

    def test_multiple_problems(self, tmp_path):
        cmd_init(_args(problem="alpha"), base_dir=tmp_path)
        cmd_init(_args(problem="beta"), base_dir=tmp_path)
        assert (tmp_path / "Problems" / "alpha" / "META.md").exists()
        assert (tmp_path / "Problems" / "beta" / "META.md").exists()


# ──────────────────────────────────────────────────────────────
# goal add
# ──────────────────────────────────────────────────────────────


class TestGoalAdd:
    def _leaf(self, tmp_path: Path, content: str = "theorem foo : True := by trivial") -> Path:
        f = tmp_path / "leaf.lean"
        f.write_text(content, encoding="utf-8")
        return f

    def test_goals_row_inserted(self, tmp_path):
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path)
        cmd_goal_add(
            _args(problem="ex", slug="foo", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        row = conn.execute("SELECT problem, slug, origin, kind, status, commit_state "
                           "FROM goals WHERE slug='foo'").fetchone()
        assert row is not None
        problem, slug, origin, kind, status, commit_state = row
        assert problem == "ex"
        assert slug == "foo"
        assert origin == "root"
        assert kind == "theorem"
        assert status == "open"
        assert commit_state == "live"

    def test_strategies_row_inserted(self, tmp_path):
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path)
        cmd_goal_add(
            _args(problem="ex", slug="foo", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        goal_row = conn.execute("SELECT id FROM goals WHERE slug='foo'").fetchone()
        assert goal_row is not None
        goal_id = goal_row[0]
        strat = conn.execute(
            "SELECT goal_id, status, commit_state FROM strategies WHERE goal_id=?",
            (goal_id,),
        ).fetchone()
        assert strat is not None
        assert strat[0] == goal_id
        assert strat[1] == "proposed"
        assert strat[2] == "live"

    def test_leaf_strategy_moved_to_strategies_dir(self, tmp_path):
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path, "theorem bar : 1=1 := by rfl")
        original_content = leaf.read_text()
        cmd_goal_add(
            _args(problem="ex", slug="bar", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )
        # Original file should be gone (moved).
        assert not leaf.exists()
        # Strategy lean_path should exist with same content.
        conn = connect(db_path)
        strat_path = conn.execute(
            "SELECT s.lean_path FROM strategies s "
            "JOIN goals g ON s.goal_id=g.id WHERE g.slug='bar'"
        ).fetchone()[0]
        dest = tmp_path / strat_path
        assert dest.exists()
        assert dest.read_text() == original_content

    def test_queue_row_inserted(self, tmp_path):
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path)
        cmd_goal_add(
            _args(problem="ex", slug="foo", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        strat_id = conn.execute(
            "SELECT s.id FROM strategies s JOIN goals g ON s.goal_id=g.id WHERE g.slug='foo'"
        ).fetchone()[0]
        q = conn.execute(
            "SELECT kind, target_id, priority FROM queue WHERE target_id=?",
            (str(strat_id),),
        ).fetchone()
        assert q is not None
        assert q[0] == "Builder"
        assert q[1] == str(strat_id)
        assert q[2] == 0

    def test_lean_paths_use_canonical_id_slug_format(self, tmp_path):
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path)
        cmd_goal_add(
            _args(problem="ex", slug="myprop", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        g_id, g_path = conn.execute(
            "SELECT id, lean_path FROM goals WHERE slug='myprop'"
        ).fetchone()
        s_id, s_path = conn.execute(
            "SELECT s.id, s.lean_path FROM strategies s JOIN goals g ON s.goal_id=g.id "
            "WHERE g.slug='myprop'"
        ).fetchone()
        assert f"{g_id}_myprop" in g_path
        assert f"{s_id}_myprop" in s_path

    def test_missing_leaf_strategy_exits_1(self, tmp_path):
        db_path = _db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="ex", slug="foo", kind="theorem",
                      leaf_strategy=str(tmp_path / "nonexistent.lean")),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1

    def test_commit_fault_after_step1_exits_2_friendly(self, tmp_path, capsys, monkeypatch):
        """COMMIT_FAULT injection → exit 2 with friendly stderr message (not Python traceback).

        DB state after fault: goals row is 'pending' (recoverable via `db recover`).
        """
        db_path = _db(tmp_path)
        leaf = self._leaf(tmp_path)
        monkeypatch.setenv("COMMIT_FAULT", "after_step1")
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="ex", slug="foo", kind="theorem", leaf_strategy=str(leaf)),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "COMMIT_FAULT" in err
        assert "db recover" in err
        # Pending row should still exist for recovery.
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT commit_state FROM goals WHERE slug='foo'"
            ).fetchone()
            assert row is not None
            assert row[0] == "pending"
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────────
# run
# ──────────────────────────────────────────────────────────────


class TestRun:
    def test_once_calls_reactor_run(self, tmp_path):
        db_path = _db(tmp_path)
        args = _args(once=True)
        with patch("Tooling.cli.Reactor") as MockReactor:
            instance = MockReactor.return_value
            # Reactor.run() triggers sys.exit(0) on empty queue; mock to avoid that.
            instance.run.side_effect = SystemExit(0)
            with pytest.raises(SystemExit) as exc:
                cmd_run(args, db_path=db_path, base_dir=tmp_path)
        assert exc.value.code == 0
        instance.run.assert_called_once()

    def test_default_calls_run_daemon(self, tmp_path):
        """No --once flag → daemon mode (run_daemon)."""
        db_path = _db(tmp_path)
        args = _args(once=False)
        with patch("Tooling.cli.Reactor") as MockReactor:
            instance = MockReactor.return_value
            instance.run_daemon.side_effect = SystemExit(0)
            with pytest.raises(SystemExit) as exc:
                cmd_run(args, db_path=db_path, base_dir=tmp_path)
        assert exc.value.code == 0
        instance.run_daemon.assert_called_once()

    def test_reactor_receives_db_path(self, tmp_path):
        db_path = _db(tmp_path)
        args = _args(once=False)
        with patch("Tooling.cli.Reactor") as MockReactor:
            instance = MockReactor.return_value
            instance.run_daemon.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                cmd_run(args, db_path=db_path, base_dir=tmp_path)
        # Reactor should have been instantiated with db_path as first positional arg.
        call_args = MockReactor.call_args
        assert call_args[0][0] == db_path


# ──────────────────────────────────────────────────────────────
# stop
# ──────────────────────────────────────────────────────────────


class TestStop:
    def _insert_scheduler(self, conn):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO schedulers (host, pid, started_at, last_heartbeat) "
            "VALUES (?, ?, ?, ?)",
            ("testhost", 12345, now, now),
        )
        conn.commit()

    def test_no_scheduler_prints_message_no_event(self, tmp_path, capsys):
        """No scheduler row → print notice, no event inserted, exit 0."""
        db_path = _db(tmp_path)
        cmd_stop(_args(signal="shutdown", all=False), db_path=db_path)
        out = capsys.readouterr().out
        assert "no scheduler running" in out
        conn = connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='control_signal'"
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_with_scheduler_inserts_shutdown_event(self, tmp_path, capsys):
        """Scheduler row present → inserts control_signal event with action=shutdown."""
        db_path = _db(tmp_path)
        conn = connect(db_path)
        self._insert_scheduler(conn)
        conn.close()

        cmd_stop(_args(signal="shutdown", all=False), db_path=db_path)
        out = capsys.readouterr().out
        assert "shutdown" in out

        conn = connect(db_path)
        row = conn.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchone()
        conn.close()
        assert row is not None
        payload = json.loads(row[0])
        assert payload["action"] == "shutdown"
        assert payload["source"] == "cli"

    def test_stop_signal_pause(self, tmp_path, capsys):
        """--signal pause inserts pause action."""
        db_path = _db(tmp_path)
        conn = connect(db_path)
        self._insert_scheduler(conn)
        conn.close()

        cmd_stop(_args(signal="pause", all=False), db_path=db_path)

        conn = connect(db_path)
        row = conn.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert json.loads(row[0])["action"] == "pause"

    def test_stop_signal_resume(self, tmp_path, capsys):
        """--signal resume inserts resume action."""
        db_path = _db(tmp_path)
        conn = connect(db_path)
        self._insert_scheduler(conn)
        conn.close()

        cmd_stop(_args(signal="resume", all=False), db_path=db_path)

        conn = connect(db_path)
        row = conn.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert json.loads(row[0])["action"] == "resume"

    def test_stop_all_sends_shutdown(self, tmp_path, capsys):
        """--all flag sends shutdown regardless of --signal."""
        db_path = _db(tmp_path)
        conn = connect(db_path)
        self._insert_scheduler(conn)
        conn.close()

        cmd_stop(_args(signal="pause", all=True), db_path=db_path)

        conn = connect(db_path)
        row = conn.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchone()
        conn.close()
        assert json.loads(row[0])["action"] == "shutdown"


# ──────────────────────────────────────────────────────────────
# db recover
# ──────────────────────────────────────────────────────────────


class TestDbRecover:
    def test_calls_recover_scan(self, tmp_path):
        db_path = _db(tmp_path)
        with patch("Tooling.cli.CommitWriter") as MockWriter:
            instance = MockWriter.return_value
            instance.recover_scan.return_value = {"goals": [], "strategies": []}
            cmd_db_recover(_args(), db_path=db_path)
        instance.recover_scan.assert_called_once()

    def test_clean_db_message(self, tmp_path, capsys):
        db_path = _db(tmp_path)
        cmd_db_recover(_args(), db_path=db_path)
        out = capsys.readouterr().out
        assert "no pending rows" in out

    def test_recovered_rows_reported(self, tmp_path, capsys):
        db_path = _db(tmp_path)
        with patch("Tooling.cli.CommitWriter") as MockWriter:
            instance = MockWriter.return_value
            instance.recover_scan.return_value = {"goals": [3, 5], "strategies": []}
            cmd_db_recover(_args(), db_path=db_path)
        out = capsys.readouterr().out
        assert "goals" in out
        assert "3" in out


# ──────────────────────────────────────────────────────────────
# goal show
# ──────────────────────────────────────────────────────────────


class TestGoalShow:
    def _insert_goal(self, conn, slug="testgoal", status="open", answer_data=None):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, answer_data, "
            " commit_state, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("ex", slug, f"Problems/ex/{slug}.lean", "root", "theorem",
             status, answer_data, "live", now, now),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_shows_status(self, tmp_path, capsys):
        db_path = _db(tmp_path)
        conn = connect(db_path)
        g_id = self._insert_goal(conn, slug="myfoo", status="open")
        conn.close()
        cmd_goal_show(_args(goal_id=str(g_id)), db_path=db_path)
        out = capsys.readouterr().out
        assert "status" in out
        assert "open" in out

    def test_shows_answer_data_when_proved(self, tmp_path, capsys):
        db_path = _db(tmp_path)
        conn = connect(db_path)
        ad = json.dumps({"type": "classical", "lean_path": "Problems/ex/foo.lean"})
        g_id = self._insert_goal(conn, slug="proven", status="proved", answer_data=ad)
        conn.close()
        cmd_goal_show(_args(goal_id=f"G_{g_id}"), db_path=db_path)
        out = capsys.readouterr().out
        assert "proved" in out
        assert "classical" in out
        assert "lean_path" in out

    def test_shows_strategy_list(self, tmp_path, capsys):
        from datetime import datetime, timezone
        db_path = _db(tmp_path)
        conn = connect(db_path)
        g_id = self._insert_goal(conn, slug="withstrat", status="open")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO strategies (goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?,?,?,?,?)",
            (g_id, "Problems/ex/Strategies/1_withstrat.lean", "proposed", "live", now),
        )
        conn.commit()
        conn.close()
        cmd_goal_show(_args(goal_id=str(g_id)), db_path=db_path)
        out = capsys.readouterr().out
        assert "strategies" in out
        assert "proposed" in out

    def test_unknown_goal_exits_1(self, tmp_path):
        db_path = _db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_goal_show(_args(goal_id="999"), db_path=db_path)
        assert exc.value.code == 1

    def test_invalid_goal_id_format_exits_1(self, tmp_path):
        """Truly invalid format (not 'root' alias, not integer) → exit 1."""
        db_path = _db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_goal_show(_args(goal_id="xyz"), db_path=db_path)
        assert exc.value.code == 1

    def test_root_alias_resolves_to_origin_root(self, tmp_path, capsys):
        """phase1_skeleton.md ## Demo line 76: `asterism goal show G_root` must work."""
        db_path = _db(tmp_path)
        conn = connect(db_path)
        g_id = self._insert_goal(conn, slug="rootgoal", status="open")
        conn.close()
        # Both 'G_root' and 'root' aliases should resolve to the unique origin='root' goal.
        cmd_goal_show(_args(goal_id="G_root"), db_path=db_path)
        out = capsys.readouterr().out
        assert "rootgoal" in out
        cmd_goal_show(_args(goal_id="root"), db_path=db_path)
        out = capsys.readouterr().out
        assert "rootgoal" in out

    def test_root_alias_with_no_root_goal_exits_1(self, tmp_path):
        """No origin='root' goal exists → root alias cannot resolve → exit 1."""
        db_path = _db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_goal_show(_args(goal_id="G_root"), db_path=db_path)
        assert exc.value.code == 1


# ──────────────────────────────────────────────────────────────
# Argument parser smoke tests
# ──────────────────────────────────────────────────────────────


class TestParser:
    def test_init_parses(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--problem", "ex"])
        assert args.command == "init"
        assert args.problem == "ex"

    def test_goal_add_parses(self):
        parser = build_parser()
        args = parser.parse_args([
            "goal", "add",
            "--problem", "ex", "--slug", "foo",
            "--kind", "theorem", "--leaf-strategy", "/tmp/f.lean",
        ])
        assert args.command == "goal"
        assert args.goal_command == "add"
        assert args.slug == "foo"
        assert args.leaf_strategy == "/tmp/f.lean"

    def test_goal_show_parses(self):
        parser = build_parser()
        args = parser.parse_args(["goal", "show", "G_1"])
        assert args.goal_command == "show"
        assert args.goal_id == "G_1"

    def test_run_once_parses(self):
        parser = build_parser()
        args = parser.parse_args(["run", "--once"])
        assert args.command == "run"
        assert args.once is True

    def test_run_default_no_once_flag(self):
        """Default 'run' (no flags) = daemon mode: once=False."""
        parser = build_parser()
        args = parser.parse_args(["run"])
        assert args.command == "run"
        assert args.once is False

    def test_run_daemon_flag_still_parses(self):
        """C17 R3 HIGH-1: --daemon kept as P1 forward-compat alias (no-op)."""
        parser = build_parser()
        args = parser.parse_args(["run", "--daemon"])
        assert args.command == "run"
        assert args.daemon is True
        assert args.once is False

    def test_stop_default_parses(self):
        parser = build_parser()
        args = parser.parse_args(["stop"])
        assert args.command == "stop"
        assert args.signal == "shutdown"
        assert args.all is False

    def test_stop_signal_pause_parses(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "--signal", "pause"])
        assert args.signal == "pause"

    def test_stop_all_parses(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "--all"])
        assert args.all is True

    def test_db_recover_parses(self):
        parser = build_parser()
        args = parser.parse_args(["db", "recover"])
        assert args.command == "db"
        assert args.db_command == "recover"

    def test_leaf_strategy_flag_in_help(self):
        """--leaf-strategy help text must mention P1 testing-only and P2 removal."""
        parser = build_parser()
        import io
        buf = io.StringIO()
        try:
            parser.parse_args(["goal", "add", "--help"])
        except SystemExit:
            pass
        # Check that the help text for leaf-strategy mentions testing-only / P2.
        help_text = parser.format_help() + " "
        goal_parser_help = ""
        for action in parser._subparsers._actions:
            if hasattr(action, "_name_parser_map"):
                if "goal" in action._name_parser_map:
                    goal_parser = action._name_parser_map["goal"]
                    for sub_action in goal_parser._subparsers._actions:
                        if hasattr(sub_action, "_name_parser_map"):
                            if "add" in sub_action._name_parser_map:
                                goal_parser_help = sub_action._name_parser_map["add"].format_help()
        assert "P1" in goal_parser_help or "testing-only" in goal_parser_help or "P2" in goal_parser_help


# ──────────────────────────────────────────────────────────────
# End-to-end integration (init → goal add → run → goal show)
# ──────────────────────────────────────────────────────────────


class TestEndToEnd:
    """Acceptance #9 path: init → goal add → run → goal show one-shot.

    Builder.run is mocked to return BuilderResult(outcome='proved') and write
    the strategies.status='succeeded' UPDATE that the cascade rule expects.
    Verifies CLI commands compose: init builds the dirs, goal add stages the
    queue, run drains queue + cascades to goal status='proved', goal show
    displays the proved state.
    """

    def test_init_goal_add_run_show_proved(self, tmp_path, capsys, monkeypatch):
        from datetime import datetime, timezone
        from Tooling.pipelines.builder import BuilderResult

        # 1. init
        cmd_init(_args(problem="ex"), base_dir=tmp_path)

        # 2. goal add (real CommitWriter path)
        leaf = tmp_path / "leaf.lean"
        leaf.write_text("theorem t : True := by trivial\n", encoding="utf-8")
        db_path = tmp_path / "asterism.db"
        cmd_goal_add(
            _args(problem="ex", slug="t", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )

        # Confirm queue has 1 task before run.
        conn = connect(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 1
            (g_id,) = conn.execute("SELECT id FROM goals WHERE slug='t'").fetchone()
            (s_id,) = conn.execute("SELECT id FROM strategies WHERE goal_id=?",
                                    (g_id,)).fetchone()
        finally:
            conn.close()

        # 3. run — mock Builder.run to simulate proved outcome + UPDATE
        # strategies.status='succeeded' (what real Builder.run does on proved).
        def fake_builder_factory(strategy_id, conn, cfg):
            mock_b = MagicMock()
            def fake_run():
                with conn:
                    conn.execute(
                        "UPDATE strategies SET status='succeeded' WHERE id=?",
                        (strategy_id,),
                    )
                return BuilderResult(outcome="proved", tactic="trivial")
            mock_b.run.side_effect = fake_run
            return mock_b

        with patch("Tooling.scheduler.Builder", side_effect=fake_builder_factory):
            with pytest.raises(SystemExit) as exc:
                cmd_run(_args(once=True, daemon=False),
                        db_path=db_path, base_dir=tmp_path)
            assert exc.value.code == 0  # empty queue clean exit

        # Confirm cascade ran: goal proved + answer_data.
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT status, answer_data FROM goals WHERE id=?", (g_id,)
            ).fetchone()
            assert row[0] == "proved"
            ad = json.loads(row[1])
            assert ad["type"] == "classical"
            assert "lean_path" in ad
            assert conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 0
        finally:
            conn.close()

        # 4. goal show — display proved status + answer_data
        cmd_goal_show(_args(goal_id=str(g_id)), db_path=db_path)
        out = capsys.readouterr().out
        assert "proved" in out
        assert "classical" in out
        # And via root alias (acceptance #2 demo path).
        cmd_goal_show(_args(goal_id="G_root"), db_path=db_path)
        out = capsys.readouterr().out
        assert "proved" in out
