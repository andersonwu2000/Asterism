"""Tests for P6 C44 CLI extensions:
- problem list / pause / resume
- library list / check-deps / reindex / audit
- scheduler force-clear (with --force gate)
- goal add --imports
- run --bypass-startup-check
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from Tooling.cli import (
    build_parser,
    cmd_goal_add,
    cmd_library_audit,
    cmd_library_check_deps,
    cmd_library_list,
    cmd_library_reindex,
    cmd_problem_list,
    cmd_problem_pause,
    cmd_problem_resume,
    cmd_scheduler_force_clear,
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


def _write_meta(base_dir: Path, problem: str, axioms: list[str]) -> None:
    """Create Problems/<problem>/META.md with the given axioms."""
    p_dir = base_dir / "Problems" / problem
    p_dir.mkdir(parents=True, exist_ok=True)
    body = "---\n"
    body += f"problem_name: {problem}\n"
    body += "axioms:\n"
    for a in axioms:
        body += f"  - {a}\n"
    body += "---\n"
    (p_dir / "META.md").write_text(body, encoding="utf-8")


def _seed_goal(
    db_path: Path,
    *,
    problem: str = "ex",
    slug: str = "g",
    status: str = "open",
    origin: str = "root",
    answer_data: dict | None = None,
    trust_set: list[dict] | None = None,
) -> int:
    conn = connect(db_path)
    try:
        ad = json.dumps(answer_data) if answer_data else None
        ts = json.dumps(trust_set) if trust_set else None
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, trust_set, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (problem, slug, f"path/{slug}.lean", origin, "theorem",
             status, "live", ad, ts, _NOW, _NOW),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParserExtensions:
    def test_problem_list_parse(self):
        p = build_parser()
        args = p.parse_args(["problem", "list"])
        assert args.command == "problem"
        assert args.problem_command == "list"

    def test_problem_pause_requires_problem(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["problem", "pause"])
        args = p.parse_args(["problem", "pause", "--problem", "x"])
        assert args.problem == "x"

    def test_problem_resume_requires_problem(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["problem", "resume"])

    def test_library_subcommands(self):
        p = build_parser()
        for cmd in ("list", "check-deps", "reindex", "audit"):
            args = p.parse_args(["library", cmd])
            assert args.library_command == cmd

    def test_scheduler_force_clear_force_flag(self):
        p = build_parser()
        args = p.parse_args(["scheduler", "force-clear"])
        assert args.force is False
        args = p.parse_args(["scheduler", "force-clear", "--force"])
        assert args.force is True

    def test_goal_add_imports_flag(self):
        p = build_parser()
        args = p.parse_args([
            "goal", "add", "--problem", "x", "--slug", "y",
            "--kind", "theorem",
            "--spec", "True",
            "--imports", "Library.Theorems.proved,Problems.A.proved",
        ])
        assert args.imports == "Library.Theorems.proved,Problems.A.proved"

    def test_run_bypass_startup_check_flag(self):
        p = build_parser()
        args = p.parse_args(["run", "--bypass-startup-check"])
        assert args.bypass_startup_check is True
        args = p.parse_args(["run"])
        assert args.bypass_startup_check is False


# ---------------------------------------------------------------------------
# problem list
# ---------------------------------------------------------------------------


class TestProblemList:
    def test_empty(self, db_path, tmp_path, capsys):
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "no Problems found" in out

    def test_lists_known_problems(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])
        _write_meta(tmp_path, "beta", ["propext", "Quot.sound"])
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "beta" in out
        # Header
        assert "PROBLEM" in out and "STATUS" in out and "AXIOMS" in out

    def test_skipped_for_bad_meta(self, db_path, tmp_path, capsys):
        # Valid one
        _write_meta(tmp_path, "ok", ["propext"])
        # Broken: no axioms
        bad_dir = tmp_path / "Problems" / "broken"
        bad_dir.mkdir(parents=True)
        (bad_dir / "META.md").write_text("no frontmatter here\n", encoding="utf-8")
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "ok" in out
        assert "broken" in out
        assert "SKIPPED" in out

    def test_paused_problem_shown(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])
        # Simulate daemon-applied paused event
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                    (
                        "control_signal",
                        json.dumps({
                            "action": "problem_pause",
                            "problem": "alpha",
                            "status": "applied",
                        }),
                        _NOW,
                    ),
                )
        finally:
            conn.close()
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        # The status column should read 'paused'
        line = next(l for l in out.splitlines() if l.startswith("alpha"))
        assert "paused" in line

    def test_resume_after_pause_clears_status(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                    (
                        "control_signal",
                        json.dumps({
                            "action": "problem_pause",
                            "problem": "alpha",
                            "status": "applied",
                        }),
                        _NOW,
                    ),
                )
                conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                    (
                        "control_signal",
                        json.dumps({
                            "action": "problem_resume",
                            "problem": "alpha",
                            "status": "applied",
                        }),
                        _NOW,
                    ),
                )
        finally:
            conn.close()
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        line = next(l for l in out.splitlines() if l.startswith("alpha"))
        assert "active" in line

    def test_goal_counts_shown(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])
        _seed_goal(db_path, problem="alpha", slug="g1", status="open")
        _seed_goal(db_path, problem="alpha", slug="g2", status="proved")
        _seed_goal(db_path, problem="alpha", slug="g3", status="proved")
        cmd_problem_list(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        line = next(l for l in out.splitlines() if l.startswith("alpha"))
        assert "open=1" in line
        assert "proved=2" in line


# ---------------------------------------------------------------------------
# problem pause / resume
# ---------------------------------------------------------------------------


class TestProblemPauseResume:
    def test_pause_emits_control_signal(self, db_path, tmp_path):
        _write_meta(tmp_path, "alpha", ["propext"])
        cmd_problem_pause(
            _args(problem="alpha"), db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        try:
            rows = conn.execute(
                "SELECT payload FROM events WHERE kind='control_signal'"
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        pl = json.loads(rows[0][0])
        assert pl["action"] == "problem_pause"
        assert pl["source"] == "cli"
        assert pl["problem"] == "alpha"

    def test_resume_emits_control_signal(self, db_path, tmp_path):
        _write_meta(tmp_path, "alpha", ["propext"])
        cmd_problem_resume(
            _args(problem="alpha"), db_path=db_path, base_dir=tmp_path,
        )
        conn = connect(db_path)
        try:
            rows = conn.execute(
                "SELECT payload FROM events WHERE kind='control_signal'"
            ).fetchall()
        finally:
            conn.close()
        pl = json.loads(rows[0][0])
        assert pl["action"] == "problem_resume"
        assert pl["problem"] == "alpha"

    def test_unknown_problem_rejected(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])
        with pytest.raises(SystemExit) as exc:
            cmd_problem_pause(
                _args(problem="bogus"),
                db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "unknown problem" in err
        # No event written
        conn = connect(db_path)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind='control_signal'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0


# ---------------------------------------------------------------------------
# library list / check-deps / reindex / audit
# ---------------------------------------------------------------------------


class TestLibraryList:
    def test_empty(self, db_path, capsys):
        cmd_library_list(_args(), db_path=db_path)
        out = capsys.readouterr().out
        assert "no entries" in out

    def test_lists_rows(self, db_path, capsys):
        gid = _seed_goal(db_path, problem="alpha", slug="add_comm",
                          status="proved")
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO library_index "
                    "(layer, name, path, source_root_id, committed_at) "
                    "VALUES ('Theorems', 'alpha.add_comm', "
                    "'Library/Theorems/proved.lean', ?, ?)",
                    (gid, _NOW),
                )
        finally:
            conn.close()
        cmd_library_list(_args(), db_path=db_path)
        out = capsys.readouterr().out
        assert "Theorems" in out
        assert "alpha.add_comm" in out
        assert f"G{gid}" in out


class TestLibraryCheckDeps:
    def test_no_problems_no_violations(self, db_path, tmp_path, capsys):
        cmd_library_check_deps(
            _args(), db_path=db_path, base_dir=tmp_path,
        )
        out = capsys.readouterr().out
        assert "no axiom-coverage violations" in out

    def test_violation_exits_2(self, db_path, tmp_path, capsys):
        _write_meta(tmp_path, "alpha", ["propext"])  # missing Quot.sound
        gid = _seed_goal(
            db_path, problem="src", slug="needs_quot", status="proved",
            trust_set=[
                {"kind": "lean_axiom", "name": "propext"},
                {"kind": "lean_axiom", "name": "Quot.sound"},
            ],
        )
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO library_index "
                    "(layer, name, path, source_root_id, committed_at) "
                    "VALUES ('Theorems', 'src.needs_quot', "
                    "'Library/Theorems/proved.lean', ?, ?)",
                    (gid, _NOW),
                )
        finally:
            conn.close()
        with pytest.raises(SystemExit) as exc:
            cmd_library_check_deps(
                _args(), db_path=db_path, base_dir=tmp_path,
            )
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "alpha consumes 'src.needs_quot'" in out
        assert "Quot.sound" in out


class TestLibraryStubs:
    # C45 lifted reindex out of stub status; the reindex tests now live
    # in test_library_c45.py. We keep one CLI invocation here as a smoke
    # check that the wiring still parses + runs without raising.
    def test_reindex_runs(self, db_path, tmp_path, capsys):
        cmd_library_reindex(_args(), db_path=db_path, base_dir=tmp_path)
        out = capsys.readouterr().out
        assert "library reindex:" in out

    def test_audit_stub_exits_1_with_p7_message(self, db_path, capsys):
        """C44 R3 HIGH-2 fix: spec phase6_library.md:62 字面 'P6 預留
        stub exit 1 + 印「not implemented; tracked in P7+」'."""
        with pytest.raises(SystemExit) as exc:
            cmd_library_audit(_args(), db_path=db_path)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "not implemented" in err
        assert "P7+" in err


# ---------------------------------------------------------------------------
# scheduler force-clear
# ---------------------------------------------------------------------------


class TestSchedulerForceClear:
    def test_empty(self, db_path, capsys):
        cmd_scheduler_force_clear(
            _args(force=False), db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "empty" in out

    def test_clears_stale_rows(self, db_path, capsys):
        old = (
            datetime.now(timezone.utc) - timedelta(seconds=600)
        ).isoformat()
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 1, ?, ?)",
                    (old, old),
                )
        finally:
            conn.close()
        cmd_scheduler_force_clear(
            _args(force=False), db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "deleted 1" in out
        conn = connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM schedulers").fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_refuses_live_rows_without_force(self, db_path, capsys):
        fresh = datetime.now(timezone.utc).isoformat()
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 99, ?, ?)",
                    (fresh, fresh),
                )
        finally:
            conn.close()
        with pytest.raises(SystemExit) as exc:
            cmd_scheduler_force_clear(
                _args(force=False), db_path=db_path,
            )
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "live scheduler" in err
        # Row preserved
        conn = connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM schedulers").fetchone()[0]
        finally:
            conn.close()
        assert count == 1

    def test_force_clears_live_rows(self, db_path, capsys):
        fresh = datetime.now(timezone.utc).isoformat()
        conn = connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, "
                    "last_heartbeat) VALUES ('h', 99, ?, ?)",
                    (fresh, fresh),
                )
        finally:
            conn.close()
        cmd_scheduler_force_clear(
            _args(force=True), db_path=db_path,
        )
        out = capsys.readouterr().out
        assert "--force used" in out
        conn = connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM schedulers").fetchone()[0]
        finally:
            conn.close()
        assert count == 0


# ---------------------------------------------------------------------------
# goal add --imports
# ---------------------------------------------------------------------------


class TestGoalAddImports:
    def test_imports_prepended_to_template(self, db_path, tmp_path):
        cmd_goal_add(
            _args(
                problem="alpha", slug="t1", kind="theorem",
                spec="True", spec_file=None, leaf_strategy=None,
                imports="Library.Theorems.proved,Problems.A.proved",
            ),
            db_path=db_path, base_dir=tmp_path,
        )
        # The .lean file lands at Problems/alpha/Goals/<id>_t1/t1.lean
        leans = list((tmp_path / "Problems" / "alpha" / "Goals").rglob("t1.lean"))
        assert len(leans) == 1
        text = leans[0].read_text(encoding="utf-8")
        assert "import Problems.alpha.Defs" in text
        assert "import Library.Theorems.proved" in text
        assert "import Problems.A.proved" in text
        # Theorem body present
        assert "theorem t1" in text
        assert "True" in text

    def test_imports_omitted_default(self, db_path, tmp_path):
        cmd_goal_add(
            _args(
                problem="alpha", slug="t2", kind="theorem",
                spec="True", spec_file=None, leaf_strategy=None,
                imports=None,
            ),
            db_path=db_path, base_dir=tmp_path,
        )
        leans = list((tmp_path / "Problems" / "alpha" / "Goals").rglob("t2.lean"))
        text = leans[0].read_text(encoding="utf-8")
        # Only the default import should be present
        assert "import Problems.alpha.Defs" in text
        assert "import Library" not in text

    def test_empty_imports_csv_drops_blank_entries(self, db_path, tmp_path):
        cmd_goal_add(
            _args(
                problem="alpha", slug="t3", kind="theorem",
                spec="True", spec_file=None, leaf_strategy=None,
                imports="  ,  Library.X  ,, ",
            ),
            db_path=db_path, base_dir=tmp_path,
        )
        leans = list((tmp_path / "Problems" / "alpha" / "Goals").rglob("t3.lean"))
        text = leans[0].read_text(encoding="utf-8")
        # Only the trimmed non-empty entry should land
        assert "import Library.X" in text
        # Default still present
        assert "import Problems.alpha.Defs" in text
        # No blank import lines
        for line in text.splitlines():
            if line.startswith("import"):
                assert line.strip() != "import"
