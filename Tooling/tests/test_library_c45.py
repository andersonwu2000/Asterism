"""P6 C45 tests:
- LIBRARY_BUILD_FAULT env hook supersedes verifier resolution
- reindex_library walks proved.lean + INSERTs missing library_index rows
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling.cli import cmd_library_reindex
from Tooling.db.connect import connect, init_schema
from Tooling.library.promotion import promote_to_library, _resolve_lake_verify
from Tooling.library.reindex import reindex_library


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


def _seed_proved_classical_goal(
    db_path: Path,
    *,
    problem: str = "alpha",
    slug: str = "add_comm",
    goal_id: int | None = None,
) -> int:
    """Seed a goal that qualifies for both per-Problem and Library promotion."""
    conn = connect(db_path)
    try:
        ts = json.dumps([
            {"kind": "lean_axiom", "name": "propext"},
        ])
        ad = json.dumps({
            "type": "classical",
            "lean_path": f"Problems/{problem}/Goals/g/{slug}.lean",
        })
        cols = (
            "problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, trust_set, created_at, updated_at"
        )
        vals = (
            problem, slug, f"path/{slug}.lean", "root", "theorem",
            "proved", "live", ad, ts, _NOW, _NOW,
        )
        if goal_id is not None:
            conn.execute(
                f"INSERT INTO goals (id, {cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (goal_id, *vals),
            )
        else:
            conn.execute(
                f"INSERT INTO goals ({cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                vals,
            )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# LIBRARY_BUILD_FAULT env hook
# ---------------------------------------------------------------------------


class TestLibraryBuildFaultEnvHook:
    def test_resolve_returns_always_false(self):
        """When LIBRARY_BUILD_FAULT=1, _resolve_lake_verify returns a
        callable that returns False unconditionally."""
        with patch.dict(os.environ, {"LIBRARY_BUILD_FAULT": "1"}, clear=False):
            verify = _resolve_lake_verify(None)
            assert verify(Path("/whatever")) is False

    def test_supersedes_explicit_verify(self):
        """LIBRARY_BUILD_FAULT must override even an explicit verify
        callable so the test path is not silently bypassed."""
        with patch.dict(os.environ, {"LIBRARY_BUILD_FAULT": "1"}, clear=False):
            explicit = lambda _path: True  # noqa: E731
            verify = _resolve_lake_verify(explicit)
            assert verify(Path("x")) is False

    def test_supersedes_library_verify_noop(self):
        with patch.dict(
            os.environ,
            {"LIBRARY_BUILD_FAULT": "1", "LIBRARY_VERIFY_NOOP": "1"},
            clear=False,
        ):
            verify = _resolve_lake_verify(None)
            assert verify(Path("x")) is False

    def test_off_falls_through(self):
        """LIBRARY_BUILD_FAULT unset (or 0) lets the normal resolution
        chain proceed."""
        with patch.dict(
            os.environ,
            {"LIBRARY_BUILD_FAULT": "0", "LIBRARY_VERIFY_NOOP": "1"},
            clear=False,
        ):
            verify = _resolve_lake_verify(None)
            assert verify(Path("x")) is True

    def test_promote_reverts_when_set(self, db_path, tmp_path):
        """End-to-end: promote_to_library with LIBRARY_BUILD_FAULT=1 must
        revert (truncate proved.lean + DELETE library_index row)."""
        gid = _seed_proved_classical_goal(db_path)
        conn = connect(db_path)
        try:
            with patch.dict(
                os.environ, {"LIBRARY_BUILD_FAULT": "1"}, clear=False,
            ):
                events: list[tuple[str, dict]] = []
                result = promote_to_library(
                    conn, gid, tmp_path,
                    emit_event=lambda k, p: events.append((k, p)),
                )
            assert result.reverted is True
            # File truncated (per-Problem + Library)
            assert not result.per_problem_appended
            assert not result.library_theorems_appended
            assert not result.library_index_inserted
            # library_index row removed
            count = conn.execute(
                "SELECT COUNT(*) FROM library_index"
            ).fetchone()[0]
            assert count == 0
            # partial_revert event emitted
            assert any(
                p.get("rule") == "library_promotion_partial_revert"
                for _, p in events
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# reindex_library
# ---------------------------------------------------------------------------


class TestReindexLibrary:
    def _write_proved_file(
        self, base_dir: Path, lines: list[str],
    ) -> None:
        path = base_dir / "Library" / "Theorems" / "proved.lean"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_no_file(self, db_path, tmp_path):
        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
        finally:
            conn.close()
        assert result.n_lines_scanned == 0
        assert result.inserted == []
        assert result.unparsed == []

    def test_inserts_missing_row(self, db_path, tmp_path):
        gid = _seed_proved_classical_goal(
            db_path, problem="alpha", slug="add_comm",
        )
        line = (
            f"theorem alpha.add_comm := "
            f"Problems.alpha.Goals.{gid}_add_comm.add_comm"
        )
        self._write_proved_file(tmp_path, [line])

        conn = connect(db_path)
        try:
            # Pre-condition: index empty
            assert conn.execute(
                "SELECT COUNT(*) FROM library_index"
            ).fetchone()[0] == 0
            result = reindex_library(conn, tmp_path)
            assert result.inserted == ["alpha.add_comm"]
            assert result.unparsed == []
            assert result.unresolved == []
            row = conn.execute(
                "SELECT name, path, source_root_id, layer "
                "FROM library_index"
            ).fetchone()
            assert row[0] == "alpha.add_comm"
            assert row[2] == gid
            assert row[3] == "Theorems"
        finally:
            conn.close()

    def test_skips_already_indexed(self, db_path, tmp_path):
        gid = _seed_proved_classical_goal(db_path, problem="alpha", slug="t")
        # Pre-existing index row
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO library_index "
                    "(layer, name, path, source_root_id, committed_at) "
                    "VALUES ('Theorems', 'alpha.t', 'p', ?, ?)",
                    (gid, _NOW),
                )
        finally:
            conn.close()
        line = f"theorem alpha.t := Problems.alpha.Goals.{gid}_t.t"
        self._write_proved_file(tmp_path, [line])

        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
            assert result.inserted == []
            assert result.already_indexed == ["alpha.t"]
            assert conn.execute(
                "SELECT COUNT(*) FROM library_index"
            ).fetchone()[0] == 1
        finally:
            conn.close()

    def test_unresolved_when_no_matching_goal(self, db_path, tmp_path):
        # File line references a goal that doesn't exist in DB
        line = "theorem ghost.thm := Problems.ghost.Goals.99_thm.thm"
        self._write_proved_file(tmp_path, [line])
        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
            assert "ghost.thm" in result.unresolved
            assert result.inserted == []
        finally:
            conn.close()

    def test_unparsed_for_hand_edits(self, db_path, tmp_path):
        self._write_proved_file(tmp_path, [
            "theorem some.weird := custom_proof_term",
            "-- not a theorem",
        ])
        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
            assert "theorem some.weird := custom_proof_term" in result.unparsed
            # Comment line is silently skipped
            assert all("not a theorem" not in u for u in result.unparsed)
        finally:
            conn.close()

    def test_blank_lines_skipped(self, db_path, tmp_path):
        gid = _seed_proved_classical_goal(db_path, problem="a", slug="t")
        self._write_proved_file(tmp_path, [
            "",
            f"theorem a.t := Problems.a.Goals.{gid}_t.t",
            "",
        ])
        conn = connect(db_path)
        try:
            result = reindex_library(conn, tmp_path)
            assert result.inserted == ["a.t"]
            assert result.n_lines_scanned == 1
        finally:
            conn.close()

    def test_idempotent_second_run(self, db_path, tmp_path):
        gid = _seed_proved_classical_goal(db_path, problem="a", slug="t")
        self._write_proved_file(tmp_path, [
            f"theorem a.t := Problems.a.Goals.{gid}_t.t",
        ])
        conn = connect(db_path)
        try:
            r1 = reindex_library(conn, tmp_path)
            assert r1.inserted == ["a.t"]
            r2 = reindex_library(conn, tmp_path)
            assert r2.inserted == []
            assert r2.already_indexed == ["a.t"]
            assert conn.execute(
                "SELECT COUNT(*) FROM library_index"
            ).fetchone()[0] == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# CLI cmd_library_reindex
# ---------------------------------------------------------------------------


class TestCmdLibraryReindex:
    def test_no_file_clean_message(self, db_path, tmp_path, capsys):
        cmd_library_reindex(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "scanned 0" in out
        assert "no changes" in out

    def test_inserts_listed(self, db_path, tmp_path, capsys):
        gid = _seed_proved_classical_goal(db_path, problem="a", slug="t")
        path = tmp_path / "Library" / "Theorems" / "proved.lean"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"theorem a.t := Problems.a.Goals.{gid}_t.t\n",
            encoding="utf-8",
        )
        cmd_library_reindex(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "+ a.t" in out
        assert "inserted (1)" in out
