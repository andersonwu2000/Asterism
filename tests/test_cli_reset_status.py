"""cmd_reset + cmd_status: per-Problem CLI tools that replace the
ad-hoc DB inspection + manual cleanup operators have been doing."""
from __future__ import annotations

import argparse
import json as _json
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.core.cli import cmd_init, cmd_reset, cmd_status, _status_payload


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
    # Defs.lean + Root.lean are now required by cmd_init.
    (pdir / "Defs.lean").write_text(
        f"import Mathlib\n\nnamespace Problems.{name}\n\nend Problems.{name}\n",
        encoding="utf-8",
    )
    (pdir / "Root.lean").write_text(
        f"import Mathlib\nimport Problems.{name}.Defs\n\n"
        f"namespace Problems.{name}\n\n"
        f"theorem main : True := by sorry\n\n"
        f"end Problems.{name}\n",
        encoding="utf-8",
    )
    return pdir


def _seed_via_init(tmp_path: Path, name: str = "wilson") -> int:
    """Run cmd_init and return the root goal id. Uses --force to skip
    the dual lake build gate (tests don't have a live lake env)."""
    cmd_init(argparse.Namespace(problem=name, force=True))
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


def test_reset_clears_problem_settings_and_paper_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Problem-keyed satellite tables (problem_settings, problem_papers)
    REFERENCE problems(name): reset must clear them or the problems
    DELETE dies on the FK — problem_papers carried this latent gap
    since v23 (reset tests never bound a paper)."""
    from Tooling.state import programme as _programme
    from Tooling.state import settings as _settings
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    _seed_via_init(tmp_path)
    conn = db.connect()
    _settings.write(conn, "wilson", "library", True)
    db.bind_paper(conn, problem="wilson", paper_id="abc123",
                  origin="user")
    # programme_revisions (v30), user_file_history (v28) and
    # problem-scoped kb_entries all REFERENCE problems(name) too — the
    # b6 run-2 reset died on the user_file_history FK (2026-07-18).
    _programme.record_pass(
        conn, "wilson",
        "# T\n## Argument\na\n## Roadmap\nr\n## Thesis\nt\n",
        {"verdict": "pass", "reservations": []}, [], 0, "b1")
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('wilson', 'Manifest.md', 'x', 'b', ?, 'observed')",
        (db.now(),))
    conn.execute(
        "INSERT INTO kb_entries (type, title, problem, created_at)"
        " VALUES ('lesson', 't', 'wilson', ?)", (db.now(),))
    conn.commit()
    conn.close()

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 0
    conn = db.connect()
    assert conn.execute(
        "SELECT count(*) FROM problem_settings WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM problem_papers WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM programme_revisions WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM user_file_history WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM kb_entries WHERE problem='wilson'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM problems WHERE name='wilson'"
    ).fetchone()[0] == 0


def test_reset_sweeps_drafts_and_presearch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reset wipes the per-problem scratch caches. `.drafts/` (progress
    notes) would pre-bias a clean baseline; `.presearch/` is worse —
    it is keyed by goal id, so after a reset that recreates the DB a
    surviving `g<id>.md` is silently served as the candidate-lemma cache
    for an UNRELATED new goal with the same id."""
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    _seed_via_init(tmp_path)
    (pdir / ".drafts").mkdir()
    (pdir / ".drafts" / "builder_g7.md").write_text("note", encoding="utf-8")
    (pdir / ".presearch").mkdir()
    (pdir / ".presearch" / "g7.md").write_text("- `Foo.bar`", encoding="utf-8")

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 0
    assert not (pdir / ".drafts").exists()
    assert not (pdir / ".presearch").exists()


def test_reset_clears_pipelines_for_problem_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting wilson must wipe wilson's pipelines but preserve cantor's."""
    _setup_problem(tmp_path, "wilson")
    _setup_problem(tmp_path, "cantor",
                   manifest_body="# cantor\n\n## Statement\n\nTrue\n")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    cmd_init(argparse.Namespace(problem="cantor", force=True))
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


def test_reset_clears_strategist_decisions_referencing_goals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strategist `ConfirmShelve` / `Reopen` decisions carry a
    `strategist_decisions.target_id` FK to goals.id. If sd rows are
    deleted AFTER goals, the FK blocks the goals DELETE with
    `FOREIGN KEY constraint failed`. Observed SG run 2026-05-17: 3
    ConfirmShelve decisions targeting distinct_collinear /
    sg_contrapositive / main froze cli reset entirely. Fix: clear
    sd rows whose target_id is in this problem's goal set before the
    goals DELETE."""
    _setup_problem(tmp_path, "sg")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="sg", force=True))
    conn = db.connect()
    gid = int(conn.execute(
        "SELECT id FROM goals WHERE problem='sg'"
    ).fetchone()["id"])
    # Seed a ConfirmShelve sd row targeting this goal (mirrors what
    # `strategist.commit_decision` writes for the ConfirmShelve case).
    conn.execute(
        "INSERT INTO strategist_decisions "
        "(triggered_at_tick, trigger_kind, decision_kind, problem,"
        " target_id, reason, payload, created_at, updated_at) "
        "VALUES (0, 'pending_review', 'ConfirmShelve', 'sg',"
        " ?, 'test', '{}', ?, ?)",
        (gid, db.now(), db.now()))
    conn.commit()

    # Must NOT raise IntegrityError.
    cmd_reset(argparse.Namespace(problem="sg"))

    conn = db.connect()
    assert conn.execute(
        "SELECT count(*) FROM strategist_decisions WHERE problem='sg'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM goals WHERE problem='sg'"
    ).fetchone()[0] == 0


def test_reset_clears_library_decls_and_kb_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A library-ized problem that also accumulated KB lessons carries two more
    `problem → problems(name)` FK children that block reset: `library_decls`
    (also `source_goal_id → goals.id`) and `kb_entries` (KB-as-SoT lessons).
    Observed 2026-06-28: derham_dd_zero reset crashed `FOREIGN KEY constraint
    failed` at `DELETE FROM problems` — first on 2 classified library_decls,
    then on a global lesson the run wrote. Fix: clear both up front."""
    _setup_problem(tmp_path, "lib")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="lib", force=True))
    conn = db.connect()
    gid = int(conn.execute(
        "SELECT id FROM goals WHERE problem='lib'").fetchone()["id"])
    # Classified library_decl (Librarian classify stage) + a global KB lesson
    # (reflection global_add) — both FK-reference the problem.
    conn.execute(
        "INSERT INTO library_decls "
        "(problem, slug, source_goal_id, verdict, target_file, file_order,"
        " lifecycle, created_at, updated_at) "
        "VALUES ('lib', 'main', ?, 'keep', 'Library/X.lean', 0,"
        " 'classified', ?, ?)",
        (gid, db.now(), db.now()))
    conn.execute(
        "INSERT INTO kb_entries (type, title, body, problem, node_id,"
        " provenance, created_at) "
        "VALUES ('lesson', 'a global lesson', '', 'lib', NULL, 'r:1', ?)",
        (db.now(),))
    conn.commit()

    # Must NOT raise IntegrityError.
    cmd_reset(argparse.Namespace(problem="lib"))

    conn = db.connect()
    for tbl in ("library_decls", "kb_entries", "goals"):
        assert conn.execute(
            f"SELECT count(*) FROM {tbl} WHERE problem='lib'"
        ).fetchone()[0] == 0, f"{tbl} not cleared"


def test_reset_clears_forward_pipeline_with_dead_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward (target_kind='Problem') pipelines that wrote a
    dead_attempt row must be cleanable by `cli reset`. Regression for
    SG 2026-05-17: the earlier `DELETE dead_attempts` passes filtered
    only on target_kind IN ('Strategy', 'Goal'), so a Forward
    dead_attempt's pipeline_id FK to pipelines blocked the
    `DELETE pipelines WHERE target_kind='Problem'` step with
    `FOREIGN KEY constraint failed`. Fix: also DELETE dead_attempts
    by pipeline_id under target_kind='Problem' before the pipelines
    DELETE."""
    _setup_problem(tmp_path, "sg")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="sg", force=True))
    conn = db.connect()
    # Seed a Forward pipeline + its dead_attempt (mirroring what
    # run_forward emits when self_verify fails).
    fwd_pid = "pid-fwd-sg"
    conn.execute(
        "INSERT INTO pipelines "
        "(id, kind, target_id, target_kind, status, outcome, "
        " started_at, finished_at) "
        "VALUES (?, 'Forward', 'sg', 'Problem', 'failed', 'failed', ?, ?)",
        (fwd_pid, db.now(), db.now()))
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, failure_reason, ts) "
        "VALUES ('sg', 'Problem', ?, 'forward_no_new_goal', ?)",
        (fwd_pid, db.now()))
    conn.commit()

    # Must NOT raise IntegrityError.
    cmd_reset(argparse.Namespace(problem="sg"))

    conn = db.connect()
    assert conn.execute(
        "SELECT count(*) FROM pipelines WHERE id = ?", (fwd_pid,)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM dead_attempts WHERE pipeline_id = ?",
        (fwd_pid,),
    ).fetchone()[0] == 0


def test_reset_isolates_other_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting wilson must leave cantor's rows alone."""
    _setup_problem(tmp_path, "wilson")
    _setup_problem(tmp_path, "cantor",
                   manifest_body="# cantor\n\n## Statement\n\nTrue\n")
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    cmd_init(argparse.Namespace(problem="cantor", force=True))
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


def test_reset_removes_proof_files_leaves_root_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reset wipes generated proof files but no longer touches Root.lean
    (Root is user-owned now — operator must restore sorry body manually
    if Root was rewritten to wrap form by a previous proved run)."""
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))

    proofs = pdir / "proofs"
    (proofs / "L_main_sub_1.lean").write_text("foo", encoding="utf-8")
    (proofs / "L_s5_sub_2.lean").write_text("foo", encoding="utf-8")
    (proofs / "_strategy_s5.lean").write_text("foo", encoding="utf-8")
    # File NOT matching the deletion patterns must survive (defensive).
    (proofs / "Helpers.lean").write_text("foo", encoding="utf-8")
    # Operator has hand-mutated Root.lean to a custom shape; reset must
    # leave it as the operator authored.
    custom_root = "theorem main : True := by trivial\n"
    (pdir / "Root.lean").write_text(custom_root, encoding="utf-8")

    cmd_reset(argparse.Namespace(problem="wilson"))

    assert not (proofs / "L_main_sub_1.lean").exists()
    assert not (proofs / "L_s5_sub_2.lean").exists()
    assert not (proofs / "_strategy_s5.lean").exists()
    assert (proofs / "Helpers.lean").exists()  # untouched
    # Root.lean preserved verbatim — framework does not own Root.lean
    assert (pdir / "Root.lean").read_text(encoding="utf-8") == custom_root


def test_reset_sweeps_verify_backup_and_tmp_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SG 2026-05-18 regression: reset must sweep Verify's atomic-write
    safety copies (`.verify_backup` / `.verify_backup_s<id>`) and
    pre-replace staging (`.lean.tmp` / `.lean.tmp_s<id>`). Before the
    fix the glob `*.backup` only matched files ENDING in `.backup`,
    leaving the sid-keyed variants behind. Recovery's
    sweep_lean_backups then copy2'd a stale `verify_backup_s9983`
    back into a goal-less `L_three_reals_pigeonhole_sign.lean`."""
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))

    proofs = pdir / "proofs"
    # All the variants left behind by killed Builder/Verify pipelines.
    (proofs / "L_main.lean.backup").write_text("x", encoding="utf-8")
    (proofs / "L_main.lean.verify_backup").write_text("x", encoding="utf-8")
    (proofs / "L_main.lean.verify_backup_s9983").write_text(
        "x", encoding="utf-8")
    (proofs / "L_main.lean.tmp").write_text("x", encoding="utf-8")
    (proofs / "L_main.lean.tmp_s9983").write_text("x", encoding="utf-8")

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 0
    assert not (proofs / "L_main.lean.backup").exists()
    assert not (proofs / "L_main.lean.verify_backup").exists()
    assert not (proofs / "L_main.lean.verify_backup_s9983").exists()
    assert not (proofs / "L_main.lean.tmp").exists()
    assert not (proofs / "L_main.lean.tmp_s9983").exists()


def test_reset_idempotent_on_clean_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resetting an already-reset Problem succeeds and writes a stub
    Root.lean (the Problem may have been initialized + reset; second
    reset should still be valid)."""
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    rc1 = cmd_reset(argparse.Namespace(problem="wilson"))
    rc2 = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc1 == 0 and rc2 == 0


def test_reset_sweeps_workspace_gateway_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reset cleans LSP gateway leftovers from two locations:
    the current `.asterism/runtime_slots/_gateway_slot_<i>.lean` (where
    `lsp_gateway.warmup` now writes them) AND the legacy workspace-root
    patterns (`_gateway_slot_<i>.lean`, `_gateway_smoke_*.lean`,
    `_axiom_probe_*.lean`) kept for migration cleanup of pre-move
    daemons. Without this, hard-killed daemon artifacts pile up across
    runs and the next gateway startup collides with stale slot files."""
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    # Drop fake gateway leftovers in the new location...
    slots_dir = tmp_path / ".asterism" / "runtime_slots"
    slots_dir.mkdir(parents=True, exist_ok=True)
    for i in range(2):
        (slots_dir / f"_gateway_slot_{i}.lean").write_text(
            "import Mathlib\n", encoding="utf-8")
    # ...and in the legacy workspace-root location.
    for name in ("_gateway_slot_0.lean", "_gateway_slot_1.lean",
                 "_gateway_smoke_abc12345.lean",
                 "_axiom_probe_def67890.lean"):
        (tmp_path / name).write_text("import Mathlib\n",
                                      encoding="utf-8")
    # An unrelated workspace file MUST survive.
    (tmp_path / "lakefile.lean").write_text("--keep me",
                                              encoding="utf-8")

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 0
    # New-location artifacts gone.
    for i in range(2):
        assert not (slots_dir / f"_gateway_slot_{i}.lean").exists()
    # Legacy-location artifacts gone.
    for name in ("_gateway_slot_0.lean", "_gateway_slot_1.lean",
                 "_gateway_smoke_abc12345.lean",
                 "_axiom_probe_def67890.lean"):
        assert not (tmp_path / name).exists(), (
            f"{name} should have been swept by reset")
    # Unrelated file untouched.
    assert (tmp_path / "lakefile.lean").exists()


def test_reset_raises_on_persistent_unlink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _robust_unlink can't remove a file even after retries (e.g.
    Windows file lock from a stuck process), reset must FAIL LOUDLY
    with rc != 0 and report which files were stuck — never silently
    swallow OSError. Without this guard, stale stale L_*.lean from
    a prior run silently inherit into the next dispatch and corrupt
    state."""
    pdir = _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    proofs = pdir / "proofs"
    (proofs / "L_stuck.lean").write_text("foo", encoding="utf-8")

    # Simulate persistent file lock: monkeypatch _robust_unlink to
    # always return False on this specific file.
    from Tooling.core import cli as cli_mod
    real_unlink = cli_mod._robust_unlink

    def fake_unlink(path, **kw):
        if path.name == "L_stuck.lean":
            return False
        return real_unlink(path, **kw)
    monkeypatch.setattr(cli_mod, "_robust_unlink", fake_unlink)

    rc = cmd_reset(argparse.Namespace(problem="wilson"))
    assert rc == 2, f"expected fail rc=2 on stuck unlink, got {rc}"


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
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    cmd_init(argparse.Namespace(problem="cantor", force=True))
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


# ---------------------------------------------------------------------
# cmd_daemon — lifecycle with built-in pre-flight (charter 5-3)
# ---------------------------------------------------------------------

def _daemon_ns(action, **kw):
    import argparse
    base = dict(daemon_action=action, scope=None, once=False,
                force=False, workspace=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_daemon_status_no_daemon(tmp_path, monkeypatch, capsys):
    import json
    from Tooling.core.cli import cmd_daemon
    (tmp_path / "Problems").mkdir()
    monkeypatch.chdir(tmp_path)
    rc = cmd_daemon(_daemon_ns("status"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["running"] is False and out["pid"] is None


def test_daemon_status_starting_window(tmp_path):
    """The boot window between daemon_start and the child's lock claim:
    a fresh anti-double-spawn marker must read as starting (with the
    scope visible and the previous run's exit suppressed) — reporting
    'idle' here flashed the Run button back mid-start. A stale marker
    (crashed boot) ages out at the marker's own 60s rule."""
    import os
    import time
    from Tooling.core.cli import daemon_status
    (tmp_path / ".asterism" / "logs").mkdir(parents=True)
    (tmp_path / ".asterism" / "daemon-starting.txt").write_text(
        "t", encoding="utf-8")
    (tmp_path / ".asterism" / "logs" / "daemon-scope.txt").write_text(
        "Test.p", encoding="utf-8")
    (tmp_path / ".asterism" / "logs" / "daemon-exit.txt").write_text(
        '{"at": "x", "rc": 0, "error": null, "scope": "Test.p"}',
        encoding="utf-8")
    st = daemon_status(tmp_path)
    assert st["starting"] is True and st["running"] is False
    assert st["scope"] == "Test.p"
    assert st["last_exit"] is None
    # stale marker (a boot that never claimed the lock) → idle again
    old = time.time() - 120
    os.utime(tmp_path / ".asterism" / "daemon-starting.txt", (old, old))
    st = daemon_status(tmp_path)
    assert st["starting"] is False
    assert st["last_exit"] is not None


def test_daemon_start_refuses_when_lock_held_by_self(tmp_path, monkeypatch,
                                                     capsys):
    """Pre-flight mechanized: a live daemon lock (pid+start-time identity,
    here OUR OWN live process) refuses a second start with the pid named.
    The button can never kill or shadow a teammate's daemon."""
    import os, psutil
    from Tooling.core.cli import cmd_daemon
    (tmp_path / "Problems").mkdir()
    (tmp_path / ".asterism").mkdir()
    me = os.getpid()
    start = psutil.Process(me).create_time()
    (tmp_path / ".asterism" / "daemon.pid").write_text(
        f"{me}\n{start}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_daemon(_daemon_ns("start"))
    assert rc == 1
    assert f"pid {me}" in capsys.readouterr().out


def test_daemon_stop_graceful_writes_stop_file(tmp_path, monkeypatch,
                                               capsys):
    import os, psutil
    from Tooling.core.cli import cmd_daemon
    from Tooling.core import dispatcher as disp
    (tmp_path / "Problems").mkdir()
    (tmp_path / ".asterism").mkdir()
    me = os.getpid()
    start = psutil.Process(me).create_time()
    (tmp_path / ".asterism" / "daemon.pid").write_text(
        f"{me}\n{start}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_daemon(_daemon_ns("stop"))
    assert rc == 0
    assert disp.stop_file_path(tmp_path).exists()
    assert "graceful" in capsys.readouterr().out


def test_daemon_stop_no_daemon_clears_stale_stop_file(tmp_path,
                                                      monkeypatch):
    from Tooling.core.cli import cmd_daemon
    from Tooling.core import dispatcher as disp
    (tmp_path / "Problems").mkdir()
    (tmp_path / ".asterism").mkdir()
    disp.stop_file_path(tmp_path).write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cmd_daemon(_daemon_ns("stop")) == 0
    assert not disp.stop_file_path(tmp_path).exists()


def test_daemon_start_refuses_while_start_marker_fresh(
        tmp_path, monkeypatch, capsys):
    """Anti-double-spawn: a second Run inside the first one's boot
    window is refused instead of silently spawning a loser daemon
    (whose scope write made the UI lie about what runs)."""
    from Tooling.core.cli import cmd_daemon
    (tmp_path / "Problems").mkdir()
    (tmp_path / ".asterism").mkdir()
    (tmp_path / ".asterism" / "daemon-starting.txt").write_text(
        "x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_daemon(_daemon_ns("start", scope="Logic.p"))
    assert rc == 1
    assert "already starting" in capsys.readouterr().out


def test_daemon_force_stop_cleans_residue(tmp_path, monkeypatch, capsys):
    """Force stop must sweep what TerminateProcess leaves behind: the
    stop-file (wedged 'stopping' forever), the dead pid's leases
    (rendered as running agents for days), and it records the exit."""
    import os as _os
    import psutil
    from Tooling.core.cli import cmd_daemon, daemon_status
    from Tooling.core import dispatcher as disp
    from Tooling.state import db as _db
    (tmp_path / "Problems").mkdir()
    (tmp_path / ".asterism").mkdir()
    me = _os.getpid()
    start = psutil.Process(me).create_time()
    (tmp_path / ".asterism" / "daemon.pid").write_text(
        f"{me}\n{start}\n", encoding="utf-8")
    disp.stop_file_path(tmp_path).write_text("x", encoding="utf-8")
    conn = _db.connect(tmp_path / "asterism.db")
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (_db.now(),))
    _db.enqueue(conn, kind="Strategist", target_id="p",
                target_kind="Problem", problem="p")
    conn.execute("UPDATE queue SET owner_pid = ?, leased_at = ?",
                 (me, _db.now()))
    conn.commit()
    conn.close()

    class _FakeProc:
        def __init__(self, _pid):
            pass

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0
    monkeypatch.setattr(psutil, "Process", _FakeProc)
    monkeypatch.chdir(tmp_path)
    rc = cmd_daemon(_daemon_ns("stop", force=True))
    assert rc == 0
    assert "released 1" in capsys.readouterr().out
    assert not disp.stop_file_path(tmp_path).exists()
    conn = _db.connect(tmp_path / "asterism.db")
    leased = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE owner_pid IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert leased == 0
    # the run's ending is on record (pid file is stale-but-dead here, so
    # status still reports running for OUR live test pid — read the
    # summary file directly instead)
    from Tooling.core.cli import _read_exit_summary
    summary = _read_exit_summary(tmp_path)
    assert summary and "force-stopped" in (summary.get("error") or "")
    assert daemon_status  # imported symbol used above in other tests


def test_daemon_start_spawns_detached_and_writes_log_pointer(
        tmp_path, monkeypatch, capsys):
    import subprocess
    from Tooling.core.cli import cmd_daemon
    from Tooling.core import dispatcher as disp
    (tmp_path / "Problems").mkdir()
    monkeypatch.chdir(tmp_path)
    disp.stop_file_path(tmp_path).parent.mkdir(exist_ok=True)
    disp.stop_file_path(tmp_path).write_text("stale", encoding="utf-8")
    seen = {}

    class _P:
        # both spawn shapes: POSIX direct child (pid) and the Windows
        # tree-detach relay (communicate prints the daemon's pid)
        pid = 4242
        def communicate(self, timeout=None):
            return b"4242\n", b""
    def fake_popen(argv, **kw):
        seen["argv"] = argv
        seen["kw"] = kw
        return _P()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    rc = cmd_daemon(_daemon_ns("start", scope="Logic.%"))
    assert rc == 0
    assert "--scope" in seen["argv"] and "Logic.%" in seen["argv"]
    assert "run" in seen["argv"]
    # stale stop file cleared so the fresh daemon is not insta-killed
    assert not disp.stop_file_path(tmp_path).exists()
    pointer = tmp_path / ".asterism" / "logs" / "daemon-current.txt"
    assert pointer.exists()
    assert "4242" in capsys.readouterr().out
