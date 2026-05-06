"""cmd_reset + cmd_status: per-Problem CLI tools that replace the
ad-hoc DB inspection + manual cleanup operators have been doing."""
from __future__ import annotations

import argparse
import json as _json
from pathlib import Path

import pytest

from Tooling import db
from Tooling.cli import cmd_init, cmd_reset, cmd_status, _status_payload


# ---------------------------------------------------------------------
# Shared setup helpers
# ---------------------------------------------------------------------

_MIN_MANIFEST = (
    "# wilson\n\n## Statement\n\nTrue\n\n## Difficulty\n\n1\n"
)


def _setup_problem(tmp_path: Path, name: str = "wilson",
                   manifest_body: str = _MIN_MANIFEST) -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(manifest_body, encoding="utf-8")
    return pdir


def _seed_via_init(tmp_path: Path, name: str = "wilson") -> int:
    """Run cmd_init and return the root goal id."""
    cmd_init(argparse.Namespace(problem=name, force=False))
    conn = db.connect()
    row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND slug = 'main'",
        (name,)).fetchone()
    return int(row["id"])


def _seed_strategy(conn, goal_id: int, status: str = "proposed") -> int:
    """Insert a strategy row referencing goal_id; bypasses the
    integrity-checking DB API since we're seeding test fixtures."""
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, '', 'pid-test', ?)",
        (goal_id, status, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_dead_attempt(conn, target_id: int, target_kind: str,
                       reason: str = "lake_build_error") -> None:
    # dead_attempts.pipeline_id has a FK to pipelines; insert a
    # matching pipeline row first so the FK passes.
    pid = f"pid-{target_kind}-{target_id}-{reason}"
    conn.execute(
        "INSERT OR IGNORE INTO pipelines "
        "(id, kind, target_id, target_kind, status, outcome, "
        " started_at, finished_at) "
        "VALUES (?, 'Builder', ?, ?, 'failed', 'failed', ?, ?)",
        (pid, str(target_id), target_kind, db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, failure_reason, ts) "
        "VALUES (?, ?, ?, ?, ?)",
        (target_id, target_kind, pid, reason, db.now()),
    )
    conn.commit()


# ---------------------------------------------------------------------
# cmd_reset
# ---------------------------------------------------------------------

def test_reset_unknown_problem_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path safety: reset on a non-existent Problems/<p>/ refuses."""
    monkeypatch.chdir(tmp_path)
    rc = cmd_reset(argparse.Namespace(problem="nonexistent"))
    assert rc == 1


def test_reset_clears_db_rows_for_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    gid = _seed_via_init(tmp_path)
    conn = db.connect()
    sid = _seed_strategy(conn, gid)
    _seed_dead_attempt(conn, gid, "Goal")
    _seed_dead_attempt(conn, sid, "Strategy")

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 0

    conn = db.connect()
    assert conn.execute(
        "SELECT count(*) FROM goals WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM strategies"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM dead_attempts"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM problems WHERE name='wilson'"
    ).fetchone()[0] == 0
    # The pipelines belonging to this problem must also be cleared —
    # otherwise post-reset queries (forensics / `status`) join against
    # ghost target_ids that no longer resolve to a goal/strategy.
    assert conn.execute(
        "SELECT count(*) FROM pipelines"
    ).fetchone()[0] == 0


def test_reset_clears_pipelines_for_problem_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting wilson must wipe wilson's pipelines but preserve cantor's."""
    _setup_problem(tmp_path, "wilson")
    _setup_problem(tmp_path, "cantor",
                   manifest_body="# cantor\n\n## Statement\n\nTrue\n")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=False))
    cmd_init(argparse.Namespace(problem="cantor", force=False))
    conn = db.connect()
    wilson_gid = int(conn.execute(
        "SELECT id FROM goals WHERE problem='wilson'").fetchone()["id"])
    cantor_gid = int(conn.execute(
        "SELECT id FROM goals WHERE problem='cantor'").fetchone()["id"])
    # Seed pipelines on both problems' goals
    for label, gid in (("w", wilson_gid), ("c", cantor_gid)):
        conn.execute(
            "INSERT INTO pipelines "
            "(id, kind, target_id, target_kind, status, outcome, "
            " started_at, finished_at) "
            "VALUES (?, 'Builder', ?, 'Goal', 'failed', 'failed', ?, ?)",
            (f"pid-{label}", str(gid), db.now(), db.now()))
    # Also seed a Verify pipeline targeting a wilson strategy
    wilson_sid = _seed_strategy(conn, wilson_gid)
    conn.execute(
        "INSERT INTO pipelines "
        "(id, kind, target_id, target_kind, status, outcome, "
        " started_at, finished_at) "
        "VALUES ('pid-w-verify', 'Verify', ?, 'Strategy', 'failed', 'failed', ?, ?)",
        (str(wilson_sid), db.now(), db.now()))
    conn.commit()

    cmd_reset(argparse.Namespace(problem="wilson"))

    conn = db.connect()
    remaining = {r[0] for r in conn.execute("SELECT id FROM pipelines").fetchall()}
    assert "pid-w" not in remaining
    assert "pid-w-verify" not in remaining  # Strategy-targeting pipeline also cleared
    assert "pid-c" in remaining  # cantor's pipeline preserved


def test_reset_isolates_other_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting wilson must leave cantor's rows alone."""
    _setup_problem(tmp_path, "wilson")
    _setup_problem(tmp_path, "cantor",
                   manifest_body="# cantor\n\n## Statement\n\nTrue\n")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=False))
    cmd_init(argparse.Namespace(problem="cantor", force=False))
    conn = db.connect()
    cantor_gid = conn.execute(
        "SELECT id FROM goals WHERE problem='cantor'").fetchone()["id"]
    _seed_strategy(conn, int(cantor_gid))

    cmd_reset(argparse.Namespace(problem="wilson"))

    conn = db.connect()
    assert conn.execute(
        "SELECT count(*) FROM goals WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM goals WHERE problem='cantor'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT count(*) FROM strategies"
    ).fetchone()[0] == 1


def test_reset_removes_proof_files_and_resets_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=False))

    proofs = pdir / "proofs"
    (proofs / "L_main_sub_1.lean").write_text("foo", encoding="utf-8")
    (proofs / "L_s5_sub_2.lean").write_text("foo", encoding="utf-8")
    (proofs / "_strategy_s5.lean").write_text("foo", encoding="utf-8")
    # File NOT matching the deletion patterns must survive (defensive).
    (proofs / "Helpers.lean").write_text("foo", encoding="utf-8")
    # Mutate Root.lean to a non-sorry shape; reset should restore stub.
    (pdir / "Root.lean").write_text(
        "theorem main : True := by trivial\n", encoding="utf-8")

    cmd_reset(argparse.Namespace(problem="wilson"))

    assert not (proofs / "L_main_sub_1.lean").exists()
    assert not (proofs / "L_s5_sub_2.lean").exists()
    assert not (proofs / "_strategy_s5.lean").exists()
    assert (proofs / "Helpers.lean").exists()  # untouched
    assert ":= by sorry" in (pdir / "Root.lean").read_text(encoding="utf-8")


def test_reset_idempotent_on_clean_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting an already-reset Problem succeeds and writes a stub
    Root.lean (the Problem may have been initialized + reset; second
    reset should still be valid)."""
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=False))
    rc1 = cmd_reset(argparse.Namespace(problem="wilson"))
    rc2 = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc1 == 0 and rc2 == 0


# ---------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------

def test_status_uninitialized_problem_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cmd_status(argparse.Namespace(problem="ghost", json=False))
    assert rc == 1


def test_status_json_uninitialized_emits_exists_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cmd_status(argparse.Namespace(problem="ghost", json=True))
    assert rc == 1
    out = capsys.readouterr().out
    payload = _json.loads(out)
    assert payload["exists"] is False
    assert payload["problem"] == "ghost"


def test_status_payload_shape_for_initialized_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    gid = _seed_via_init(tmp_path)
    conn = db.connect()
    sid = _seed_strategy(conn, gid)  # 'proposed' (live)
    _seed_strategy(conn, gid, status="dead")
    _seed_dead_attempt(conn, gid, "Goal", reason="lake_build_error")
    _seed_dead_attempt(conn, gid, "Goal", reason="lake_build_error")
    _seed_dead_attempt(conn, sid, "Strategy", reason="agent_rc_nonzero")

    payload = _status_payload(conn, "wilson")
    assert payload["exists"] is True
    assert len(payload["goals"]) == 1
    assert payload["goals"][0]["slug"] == "main"
    assert len(payload["strategies"]) == 2
    assert payload["live_strategies_count"] == 1
    # Failure-reason aggregation
    assert payload["recent_failure_reasons"] == {
        "lake_build_error": 2,
        "agent_rc_nonzero": 1,
    }
    assert payload["dead_attempts_window"] == 3


def test_status_json_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` output must be valid JSON and contain the same goal
    list the textual path would print."""
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    _seed_via_init(tmp_path)
    capsys.readouterr()  # discard cmd_init's stdout
    rc = cmd_status(argparse.Namespace(problem="wilson", json=True))
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["exists"] is True
    assert payload["problem"] == "wilson"
    assert len(payload["goals"]) == 1


def test_status_recent_pipelines_filtered_to_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pipeline targeting a goal from a different problem must not
    appear in `wilson`'s status."""
    _setup_problem(tmp_path, "wilson")
    _setup_problem(tmp_path, "cantor",
                   manifest_body="# cantor\n\n## Statement\n\nTrue\n")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=False))
    cmd_init(argparse.Namespace(problem="cantor", force=False))
    conn = db.connect()
    wilson_gid = conn.execute(
        "SELECT id FROM goals WHERE problem='wilson'").fetchone()["id"]
    cantor_gid = conn.execute(
        "SELECT id FROM goals WHERE problem='cantor'").fetchone()["id"]
    # Insert pipeline rows for both
    for gid, label in [(wilson_gid, "w"), (cantor_gid, "c")]:
        conn.execute(
            "INSERT INTO pipelines "
            "(id, kind, target_id, target_kind, status, outcome, "
            " started_at, finished_at) "
            "VALUES (?, 'Builder', ?, 'Goal', 'failed', 'failed', ?, ?)",
            (f"pid-{label}", str(gid), db.now(), db.now()),
        )
    conn.commit()

    payload = _status_payload(conn, "wilson")
    pipe_ids = {p["id"] for p in payload["recent_pipelines"]}
    assert "pid-w" in pipe_ids
    assert "pid-c" not in pipe_ids
