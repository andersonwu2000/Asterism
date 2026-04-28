"""Tests for P3 C26 CLI extensions: goal unblock + goal add --spec-file."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.cli import (
    build_parser,
    cmd_goal_add,
    cmd_goal_unblock,
)
from Tooling.db.connect import connect, init_schema
from Tooling.subsystems.blocked_pipelines import (
    block_pipeline,
    get_blocked_pipelines,
)


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


def _seed_goal(db_path: Path, *, slug: str = "g") -> int:
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("ex", slug, f"path/{slug}.lean", "root", "theorem", "open",
             "live", _NOW, _NOW),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI parser: goal unblock + goal add --spec-file
# ---------------------------------------------------------------------------


class TestParserUnblock:
    def test_unblock_specific_kind_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["goal", "unblock", "5", "Backward"])
        assert args.command == "goal"
        assert args.goal_command == "unblock"
        assert args.goal_id == "5"
        assert args.pipeline_kind == "Backward"
        assert args.unblock_all is False

    def test_unblock_all_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["goal", "unblock", "5", "--all"])
        assert args.unblock_all is True
        assert args.pipeline_kind is None

    def test_unblock_invalid_kind_rejected(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["goal", "unblock", "5", "BogusKind"])

    def test_unblock_missing_kind_rejected(self) -> None:
        """Mutually-exclusive group requires either pipeline_kind or --all."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["goal", "unblock", "5"])

    def test_unblock_kind_and_all_mutex(self) -> None:
        """C26 R3 LOW-5: argparse mutex prevents giving both pipeline_kind and --all."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["goal", "unblock", "5", "Backward", "--all"])


class TestParserSpecFile:
    def test_spec_file_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "goal", "add", "--problem", "ex", "--slug", "g",
            "--kind", "theorem", "--spec-file", "/tmp/spec.txt",
        ])
        assert args.spec is None
        assert args.spec_file == "/tmp/spec.txt"
        assert args.leaf_strategy is None

    def test_spec_and_spec_file_mutually_exclusive(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "goal", "add", "--problem", "ex", "--slug", "g",
                "--kind", "theorem", "--spec", "True",
                "--spec-file", "/tmp/spec.txt",
            ])


# ---------------------------------------------------------------------------
# cmd_goal_unblock
# ---------------------------------------------------------------------------


class TestUnblockCommand:
    def test_unblock_specific_kind_removes(self, db_path, capsys) -> None:
        gid = _seed_goal(db_path)
        conn = connect(db_path)
        try:
            block_pipeline(conn, gid, "Backward")
            block_pipeline(conn, gid, "Builder")
        finally:
            conn.close()

        cmd_goal_unblock(
            _args(goal_id=str(gid), pipeline_kind="Backward",
                  unblock_all=False),
            db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "unblocked 'Backward'" in out

        conn = connect(db_path)
        try:
            assert get_blocked_pipelines(conn, gid) == ["Builder"]
        finally:
            conn.close()

    def test_unblock_all(self, db_path, capsys) -> None:
        gid = _seed_goal(db_path, slug="g_all")
        conn = connect(db_path)
        try:
            block_pipeline(conn, gid, "Backward")
            block_pipeline(conn, gid, "Builder")
        finally:
            conn.close()

        cmd_goal_unblock(
            _args(goal_id=str(gid), pipeline_kind=None, unblock_all=True),
            db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "unblocked all" in out

        conn = connect(db_path)
        try:
            assert get_blocked_pipelines(conn, gid) == []
        finally:
            conn.close()

    def test_unblock_kind_not_present_is_noop(self, db_path, capsys) -> None:
        gid = _seed_goal(db_path, slug="g_noop")
        cmd_goal_unblock(
            _args(goal_id=str(gid), pipeline_kind="Backward",
                  unblock_all=False),
            db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "was not in blocked_pipelines" in out

    def test_unblock_invalid_goal_id_exits(self, db_path) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_goal_unblock(
                _args(goal_id="nonexistent", pipeline_kind="Backward",
                      unblock_all=False),
                db_path=db_path,
            )
        assert exc.value.code == 1

    def test_unblock_all_on_empty_list_is_noop(self, db_path, capsys) -> None:
        """C26 R3 LOW-5: --all on already-empty blocked_pipelines prints
        '0 entries removed' (idempotent, parallel to specific-kind no-op test)."""
        gid = _seed_goal(db_path, slug="g_empty_all")
        cmd_goal_unblock(
            _args(goal_id=str(gid), pipeline_kind=None, unblock_all=True),
            db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "unblocked all (0 entries removed)" in out

    def test_unblock_g_root_alias(self, db_path, capsys) -> None:
        """C26 R3 LOW-5: G_root alias works (origin='root' resolution)."""
        gid = _seed_goal(db_path, slug="g_alias_root")  # origin='root'
        conn = connect(db_path)
        try:
            block_pipeline(conn, gid, "Backward")
        finally:
            conn.close()
        cmd_goal_unblock(
            _args(goal_id="G_root", pipeline_kind="Backward", unblock_all=False),
            db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "unblocked 'Backward'" in out


# ---------------------------------------------------------------------------
# cmd_goal_add --spec-file
# ---------------------------------------------------------------------------


class TestSpecFile:
    def test_spec_file_loaded_into_goal(self, db_path, tmp_path, capsys) -> None:
        spec_text = "∀ m n : Nat, m + n = n + m"
        spec_file = tmp_path / "spec.txt"
        spec_file.write_text(spec_text + "\n", encoding="utf-8")
        cmd_goal_add(
            _args(problem="sg", slug="add_comm", kind="theorem",
                  spec=None, spec_file=str(spec_file), leaf_strategy=None),
            db_path=db_path, base_dir=tmp_path,
        )
        out = capsys.readouterr().out
        assert "queued Backward" in out

        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT question FROM goals WHERE slug = 'add_comm'"
            ).fetchone()
            # Whitespace stripped per cmd_goal_add
            assert row[0] == spec_text
        finally:
            conn.close()

    def test_spec_file_missing_exits(self, db_path, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="sg", slug="g", kind="theorem", spec=None,
                      spec_file=str(tmp_path / "nope.txt"), leaf_strategy=None),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1

    def test_spec_file_empty_exits(self, db_path, tmp_path) -> None:
        spec_file = tmp_path / "empty.txt"
        spec_file.write_text("   \n  \n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="sg", slug="g", kind="theorem", spec=None,
                      spec_file=str(spec_file), leaf_strategy=None),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1

    def test_spec_file_directory_path_handled(self, db_path, tmp_path) -> None:
        """C26 R3 LOW-5: directory path → friendly exit 1, not IsADirectoryError traceback."""
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="sg", slug="g", kind="theorem", spec=None,
                      spec_file=str(tmp_path), leaf_strategy=None),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1

    def test_spec_file_non_utf8_handled(self, db_path, tmp_path) -> None:
        """C26 R3 LOW-5: non-UTF8 bytes → friendly exit 1, not UnicodeDecodeError traceback."""
        spec_file = tmp_path / "binary.bin"
        spec_file.write_bytes(b"\xff\xfe\x00\x00 not valid utf-8")
        with pytest.raises(SystemExit) as exc:
            cmd_goal_add(
                _args(problem="sg", slug="g", kind="theorem", spec=None,
                      spec_file=str(spec_file), leaf_strategy=None),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1

    def test_inline_spec_strip_symmetric_with_spec_file(
        self, db_path, tmp_path, capsys
    ) -> None:
        """C26 R3 LOW-2: inline --spec also gets .strip() (was asymmetric)."""
        cmd_goal_add(
            _args(problem="sg", slug="strip_g", kind="theorem",
                  spec="  True  \n", spec_file=None, leaf_strategy=None),
            db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT question FROM goals WHERE slug = 'strip_g'"
            ).fetchone()
            assert row[0] == "True"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# BACKWARD_FORCE=succeed extension (P3 C26 task #15)
# ---------------------------------------------------------------------------


class TestBackwardForceSucceed:
    def test_succeed_returns_success_with_no_strategy(
        self, tmp_path, monkeypatch
    ) -> None:
        from Tooling.pipelines.backward import (
            Backward,
            BackwardConfig,
        )
        monkeypatch.setenv("BACKWARD_FORCE", "succeed")
        # Note: with FORCE active, goal_id is unused but accepted.
        bw = Backward(
            conn=None,  # type: ignore[arg-type]
            chain=None,  # type: ignore[arg-type]
            config=BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path)),
        )
        result = bw.run(goal_id=42)
        assert result.outcome == "success"
        assert result.strategy_id is None
        assert result.subgoal_ids == []

    def test_unknown_force_value_raises(
        self, tmp_path, monkeypatch
    ) -> None:
        from Tooling.pipelines.backward import (
            Backward,
            BackwardConfig,
        )
        monkeypatch.setenv("BACKWARD_FORCE", "bogus")
        bw = Backward(
            conn=None,  # type: ignore[arg-type]
            chain=None,  # type: ignore[arg-type]
            config=BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path)),
        )
        with pytest.raises(ValueError, match="unknown BACKWARD_FORCE value"):
            bw.run(goal_id=1)
