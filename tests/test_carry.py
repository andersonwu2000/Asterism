"""`asterism carry export` / `asterism carry import` — moving ONE
problem's complete state between workspaces.

The shuttle was done by hand four times (flagship <-> the 32G box <->
the SP7 node) and leaked orphan rows twice, both times in a table with
no `problem` column that a hand-written prune could not see. So every
question here is asked of the SCHEMA, never of a list: the
classification must cover every table, the goal-keyed prune must leave
no orphan, and an id that collides with another problem's must be
remapped everywhere it is referenced — including the references SQLite
cannot declare (polymorphic target_kind/target_id, payload JSON, the
strategy id baked into a Lean filename and its declaration).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from Tooling.state import carry, db, groups as groups_mod


# ---------------------------------------------------------------------
# a workspace with two problems, so "leaves the other one alone" is a
# question this file can actually ask
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, ws: Path, name: str,
                  *, project: str = "Erdos") -> dict:
    """One problem with a row in every table carry has to move, plus the
    on-disk files those rows point at."""
    ts = db.now()
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES (?, ?)", (project, ts))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES (?, ?, ?, 1)", (name, ts, project))
    gid_top = groups_mod.ensure_top_group(conn, name, charter=f"{name} goal")

    pdir = db.problem_dir(ws, name)
    (pdir / "proofs").mkdir(parents=True, exist_ok=True)
    rel_root = (pdir / "Root.lean").relative_to(ws).as_posix()
    root = db.insert_goal(conn, problem=name, slug="main",
                          lean_path=rel_root, statement="True",
                          origin="root", status="open")
    rel_lemma = (pdir / "proofs" / "L_lemma.lean").relative_to(ws).as_posix()
    lemma = db.insert_goal(conn, problem=name, slug="lemma",
                           lean_path=rel_lemma, statement="True",
                           origin="forward", status="proved")
    sid = db.insert_strategy(conn, goal_id=root, lean_path=rel_root,
                             created_by="pid-seed")
    scratch = (pdir / "proofs" / f"_strategy_s{sid}.lean")
    conn.execute("UPDATE strategies SET scratch_path = ? WHERE id = ?",
                 (scratch.relative_to(ws).as_posix(), sid))
    conn.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
                 " position) VALUES (?, ?, 0)", (sid, lemma))

    pipe = f"pipe-{name}"
    conn.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
                 " status, started_at) VALUES (?, 'Backward', ?, 'Goal',"
                 " 'failed', ?)", (pipe, str(root), ts))
    conn.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
                 " status, started_at) VALUES (?, 'Forward', ?, 'Problem',"
                 " 'succeeded', ?)", (f"{pipe}-fwd", name, ts))
    conn.execute("INSERT INTO dead_attempts (target_id, target_kind,"
                 " pipeline_id, failure_reason, ts)"
                 " VALUES (?, 'Goal', ?, 'lake_build_error', ?)",
                 (root, pipe, ts))
    conn.execute("INSERT INTO dead_attempts (target_id, target_kind,"
                 " pipeline_id, failure_reason, ts)"
                 " VALUES (?, 'Strategy', ?, 'agent_declined', ?)",
                 (sid, pipe, ts))

    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id,"
        " produced_goal_id, produced_strategy_id, produced_group_id,"
        " payload, created_at, updated_at)"
        " VALUES (?, 1, 'routine', 'Inject', ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, gid_top, root, lemma, sid, gid_top,
         json.dumps({"target_goal_id": root, "group_id": gid_top}), ts, ts))
    did = int(cur.lastrowid)
    conn.execute("INSERT INTO queue (kind, target_id, target_kind, problem,"
                 " decision_id, created_at)"
                 " VALUES ('Backward', ?, 'Goal', ?, ?, ?)",
                 (str(root), name, did, ts))
    conn.execute("INSERT INTO goal_events (goal_id, problem, to_status,"
                 " event, at) VALUES (?, ?, 'proved', 'seed', ?)",
                 (lemma, name, ts))
    conn.execute("INSERT INTO kb_entries (type, title, problem, node_id,"
                 " created_at) VALUES ('lesson', 't', ?, ?, ?)",
                 (name, lemma, ts))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body,"
                 " status, group_id, created_at)"
                 " VALUES (?, 1, 'route', 'passed', ?, ?)",
                 (name, gid_top, ts))
    conn.execute("INSERT INTO problem_settings (problem, key, value,"
                 " updated_at) VALUES (?, 'library', 'true', ?)", (name, ts))
    conn.execute("INSERT INTO problem_papers (problem, paper_id, origin,"
                 " created_at) VALUES (?, ?, 'user', ?)",
                 (name, f"paper{len(name)}", ts))
    conn.execute("INSERT INTO user_file_history (problem, file, sha, body,"
                 " seen_at) VALUES (?, 'charter', 'x', 'b', ?)", (name, ts))
    conn.execute("INSERT INTO spawn_usage (pipeline_id, kind, problem,"
                 " ts) VALUES (?, 'Backward', ?, ?)", (pipe, name, ts))
    conn.execute("INSERT INTO human_commands (problem, kind, payload,"
                 " idempotency_key, status, decision_id, created_at)"
                 " VALUES (?, 'Signal', ?, ?, 'queued', ?, ?)",
                 (name, json.dumps({"target_goal_id": root}),
                  f"key-{name}", did, ts))
    conn.execute("INSERT INTO routine_verdicts (problem, group_id,"
                 " pipeline_id, verdict_json, fired_json, created_at)"
                 " VALUES (?, ?, ?, ?, ?, ?)",
                 (name, gid_top, pipe, json.dumps({"verdict": "pass"}),
                  json.dumps([{"goal_id": lemma}]), ts))
    conn.execute("INSERT INTO library_decls (problem, slug, source_goal_id,"
                 " created_at, updated_at) VALUES (?, 'lemma', ?, ?, ?)",
                 (name, lemma, ts, ts))
    conn.commit()

    (pdir / "problem.json").write_text(
        json.dumps({"problem": name, "charter": "Statement: True"}),
        encoding="utf-8")
    (pdir / "Root.lean").write_text(
        f"import Mathlib\nimport Problems.{name}.proofs._strategy_s{sid}\n\n"
        f"namespace Problems.{name}\n\n"
        f"def main := @Problems.{name}.s{sid}\n\n"
        f"end Problems.{name}\n", encoding="utf-8")
    (pdir / "proofs" / "L_lemma.lean").write_text(
        "import Mathlib\ntheorem lemma_ : True := trivial\n", encoding="utf-8")
    scratch.write_text(
        f"import Mathlib\n\nnamespace Problems.{name}\n\n"
        f"theorem s{sid} : True := trivial\n\n"
        f"end Problems.{name}\n", encoding="utf-8")
    (pdir / "TREE.md").write_text(f"main [g{root}]\n", encoding="utf-8")
    (pdir / "PROGRAMME.md").write_text("# rev 1\nroute\n", encoding="utf-8")
    (pdir / "BRIEF.md").write_text("brief\n", encoding="utf-8")
    (pdir / ".groups" / str(gid_top)).mkdir(parents=True)
    (pdir / ".groups" / str(gid_top) / "PROGRAMME.md").write_text(
        "# rev 1\nsub-route\n", encoding="utf-8")
    return {"root": root, "lemma": lemma, "sid": sid, "gid": gid_top,
            "did": did, "pipe": pipe}


def _workspace(tmp_path: Path, *names: str) -> tuple[Path, dict]:
    ws = tmp_path
    (ws / "Problems").mkdir(parents=True, exist_ok=True)
    conn = db.connect(ws / "asterism.db")
    db.init_schema(conn)
    seeded = {n: _seed_problem(conn, ws, n) for n in names}
    conn.close()
    return ws, seeded


def _rows(dbfile: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(str(dbfile))
    try:
        return [tuple(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def _export(ws: Path, problem: str, out: Path,
            monkeypatch: pytest.MonkeyPatch) -> int:
    from Tooling.core.cli.carry import cmd_carry
    monkeypatch.chdir(ws)
    return cmd_carry(argparse.Namespace(
        carry_action="export", problem=problem, out=str(out)))


def _import(ws: Path, bundle: Path, monkeypatch: pytest.MonkeyPatch,
            **kw) -> int:
    from Tooling.core.cli.carry import cmd_carry
    monkeypatch.chdir(ws)
    ns = argparse.Namespace(
        carry_action="import", bundle=str(bundle), dry_run=False,
        problem=None, allow_migrate=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return cmd_carry(ns)


# ---------------------------------------------------------------------
# classification — the question a hand list cannot answer
# ---------------------------------------------------------------------

def test_every_table_is_classified(tmp_path: Path) -> None:
    """No table may be REFUSED. A new table that carry cannot place is
    a table carry would silently drop rows from — the leak the by-hand
    shuttle produced twice — so it must fail here instead."""
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    kinds = carry.classify(conn)
    assert kinds, "classification is empty"
    assert [t for t, k in kinds.items() if k == carry.REFUSED] == []
    # and the buckets are the four the tool knows how to act on
    assert set(kinds.values()) <= {
        carry.PROBLEM_KEYED, carry.GOAL_KEYED, carry.GLOBAL}
    # the two tables the hand-shuttle leaked are goal-keyed, not global
    assert kinds["strategies"] == carry.GOAL_KEYED
    assert kinds["strategy_subgoals"] == carry.GOAL_KEYED
    assert kinds["dead_attempts"] == carry.GOAL_KEYED
    assert kinds["projects"] == carry.GLOBAL
    conn.close()


# ---------------------------------------------------------------------
# export
# ---------------------------------------------------------------------

def test_export_prunes_to_the_problem_and_keeps_the_global_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """carry.db holds P's rows and nobody else's — except `projects`
    and `library*`, which are global assets and travel whole."""
    ws, _ = _workspace(tmp_path / "src", "Erdos.p1", "Erdos.p2")
    out = tmp_path / "bundle"
    assert _export(ws, "Erdos.p1", out, monkeypatch) == 0

    cdb = out / "carry.db"
    assert cdb.exists() and (out / "files.tar.gz").exists()
    assert _rows(cdb, "SELECT name FROM problems") == [("Erdos.p1",)]
    for table in ("goals", "groups", "queue", "strategist_decisions",
                  "goal_events", "spawn_usage", "human_commands",
                  "routine_verdicts", "programme_revisions"):
        others = _rows(cdb, f"SELECT COUNT(*) FROM {table}"
                            f" WHERE problem <> 'Erdos.p1'")
        assert others == [(0,)], f"{table} kept another problem's rows"
    # global assets travel whole
    assert sorted(_rows(cdb, "SELECT name FROM projects")) == [("Erdos",)]
    assert len(_rows(cdb, "SELECT id FROM library_decls")) == 2


def test_export_leaves_no_orphan_in_the_goal_keyed_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`strategies`/`strategy_subgoals`/`dead_attempts`/`pipelines` have
    no `problem` column, so a prune that forgets to key them by goal
    leaves rows pointing at goals the snapshot no longer holds — the
    exact leak the by-hand shuttle produced twice."""
    ws, _ = _workspace(tmp_path / "src", "Erdos.p1", "Erdos.p2")
    out = tmp_path / "bundle"
    assert _export(ws, "Erdos.p1", out, monkeypatch) == 0
    cdb = out / "carry.db"
    assert _rows(cdb, "SELECT COUNT(*) FROM strategies WHERE goal_id NOT IN"
                      " (SELECT id FROM goals)") == [(0,)]
    assert _rows(cdb, "SELECT COUNT(*) FROM strategy_subgoals WHERE"
                      " strategy_id NOT IN (SELECT id FROM strategies)"
                      " OR subgoal_id NOT IN (SELECT id FROM goals)"
                      ) == [(0,)]
    assert _rows(cdb, "SELECT COUNT(*) FROM dead_attempts WHERE"
                      " target_kind='Goal' AND target_id NOT IN"
                      " (SELECT id FROM goals)") == [(0,)]
    assert _rows(cdb, "SELECT COUNT(*) FROM pipelines WHERE"
                      " target_kind='Goal' AND target_id NOT IN"
                      " (SELECT CAST(id AS TEXT) FROM goals)") == [(0,)]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["problem"] == "Erdos.p1"
    assert manifest["schema_user_version"] == db._CURRENT_USER_VERSION
    assert manifest["row_counts"]["goals"] == 2


def test_export_decides_the_failure_sentinel_by_its_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`dead_attempts.target_id = 0` is a SENTINEL, not an id.

    A failure that is not ABOUT a goal/strategy/group — a Strategist
    wake that died, a Forward or Librarian pipeline — records 0 in an
    INTEGER column and carries its real subject in `pipeline_id`
    (`dispatcher/worker.py`). So the only thing that can say which
    problem such a row belongs to is the pipeline it hangs off, and a
    prune that reads the 0 as a group id exports the wrong rows and
    then indicts the right ones: 44 of these blocked a `carry export`
    on the SP7 node, 85 sit in the operator's live DB.

    Three shapes, one rule — ownership is the pipeline's:
      * pipeline is P's        -> travels with P
      * pipeline is another's  -> stays behind, and is not P's orphan
      * pipeline is gone       -> belongs to nobody; left in place
    """
    ws, s = _workspace(tmp_path / "src", "Erdos.p1", "Erdos.p2")
    conn = db.connect(ws / "asterism.db")
    ts = db.now()
    gid = s["Erdos.p1"]["gid"]
    # A Strategist wake on P's own group, and the sentinel it wrote.
    conn.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
                 " status, started_at) VALUES ('pipe-grp-p1', 'Strategist',"
                 " ?, 'Group', 'failed', ?)", (str(gid), ts))
    conn.execute("INSERT INTO dead_attempts (target_id, target_kind,"
                 " pipeline_id, failure_reason, ts)"
                 " VALUES (0, 'Group', 'pipe-grp-p1', 'spawn_rc1', ?)", (ts,))
    # The same shape, owned by the OTHER problem's Forward pipeline.
    conn.execute("INSERT INTO dead_attempts (target_id, target_kind,"
                 " pipeline_id, failure_reason, ts)"
                 " VALUES (0, 'Problem', 'pipe-Erdos.p2-fwd', 'rc1', ?)",
                 (ts,))
    # And one whose pipeline row no longer exists at all.
    conn.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
                 " status, started_at) VALUES ('pipe-ghost', 'Strategist',"
                 " '999', 'Group', 'failed', ?)", (ts,))
    conn.execute("INSERT INTO dead_attempts (target_id, target_kind,"
                 " pipeline_id, failure_reason, ts)"
                 " VALUES (0, 'Group', 'pipe-ghost', 'spawn_rc1', ?)", (ts,))
    conn.commit()
    # `PRAGMA foreign_keys` is a no-op inside a transaction, so the
    # commit above is load-bearing: without it the pragma is ignored and
    # the DELETE trips the FK it is meant to suspend.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM pipelines WHERE id = 'pipe-ghost'")
    conn.commit()
    conn.close()

    out = tmp_path / "bundle"
    assert _export(ws, "Erdos.p1", out, monkeypatch) == 0,         "the sentinel must not be mistaken for a missing group"
    cdb = out / "carry.db"
    assert _rows(cdb, "SELECT pipeline_id FROM dead_attempts"
                      " WHERE target_id = 0") == [("pipe-grp-p1",)],         "exactly the sentinel whose pipeline is P's travels"

    # The two that stayed behind are still in the SOURCE, untouched.
    sdb = ws / "asterism.db"
    assert _rows(sdb, "SELECT COUNT(*) FROM dead_attempts"
                      " WHERE pipeline_id IN ('pipe-Erdos.p2-fwd',"
                      " 'pipe-ghost')") == [(2,)]


# ---------------------------------------------------------------------
# import
# ---------------------------------------------------------------------

def test_import_replaces_the_problem_and_leaves_the_others_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every row of P in the target is replaced by the bundle's, and
    every row of every OTHER problem comes through byte-identical."""
    src, _ = _workspace(tmp_path / "src", "Erdos.p1")
    out = tmp_path / "bundle"
    assert _export(src, "Erdos.p1", out, monkeypatch) == 0

    tgt, _ = _workspace(tmp_path / "tgt", "Erdos.p1", "Erdos.p2")
    tdb = tgt / "asterism.db"
    before_p2 = _rows(tdb, "SELECT * FROM goals WHERE problem='Erdos.p2'"
                           " ORDER BY id")
    before_p2_sd = _rows(tdb, "SELECT * FROM strategist_decisions"
                              " WHERE problem='Erdos.p2' ORDER BY id")
    before_p1 = _rows(tdb, "SELECT statement FROM goals"
                           " WHERE problem='Erdos.p1'")

    assert _import(tgt, out, monkeypatch) == 0

    assert _rows(tdb, "SELECT * FROM goals WHERE problem='Erdos.p2'"
                      " ORDER BY id") == before_p2
    assert _rows(tdb, "SELECT * FROM strategist_decisions"
                      " WHERE problem='Erdos.p2' ORDER BY id") == before_p2_sd
    assert len(before_p1) == 2
    assert _rows(tdb, "SELECT COUNT(*) FROM goals"
                      " WHERE problem='Erdos.p1'") == [(2,)]
    # the files came across, and the displaced directory was kept
    assert (tgt / "Problems" / "Erdos" / "p1" / "Root.lean").exists()
    assert list((tgt / ".asterism" / "backups").glob("carry_Erdos.p1_*"))


def test_import_remaps_colliding_ids_through_every_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The target already used these integer ids for ANOTHER problem
    (e2e probes ran locally after the fork). The imported rows get fresh
    ids, and the map is applied to every reference — the FK ones, the
    polymorphic text ones (`pipelines`/`dead_attempts` target_id), the
    link table, and the ids baked into payload JSON and into the
    strategy's Lean filename + declaration."""
    src, s = _workspace(tmp_path / "src", "Erdos.p1")
    out = tmp_path / "bundle"
    assert _export(src, "Erdos.p1", out, monkeypatch) == 0

    # A target whose OTHER problem occupies exactly the source's id
    # range — the "e2e probes ran locally after the fork" shape.
    tgt, _ = _workspace(tmp_path / "tgt", "Erdos.p9")
    tdb = tgt / "asterism.db"
    occupied_goals = {r[0] for r in _rows(tdb, "SELECT id FROM goals")}
    assert s["Erdos.p1"]["root"] in occupied_goals, "no collision to test"

    assert _import(tgt, out, monkeypatch) == 0

    # p9 untouched
    assert _rows(tdb, "SELECT COUNT(*) FROM goals"
                      " WHERE problem='Erdos.p9'") == [(2,)]
    new_root = _rows(tdb, "SELECT id FROM goals WHERE problem='Erdos.p1'"
                          " AND slug='main'")[0][0]
    new_lemma = _rows(tdb, "SELECT id FROM goals WHERE problem='Erdos.p1'"
                           " AND slug='lemma'")[0][0]
    assert new_root not in occupied_goals
    new_sid = _rows(
        tdb, f"SELECT id FROM strategies WHERE goal_id = {new_root}")[0][0]
    new_gid = _rows(
        tdb, "SELECT id FROM groups WHERE problem='Erdos.p1'")[0][0]

    # every reference follows: FK, link table, polymorphic target ids
    # (TEXT on pipelines/queue, INTEGER on dead_attempts), payload JSON,
    # and the strategy id inside the Lean file's name + declaration.
    assert _rows(tdb, "SELECT strategy_id, subgoal_id FROM strategy_subgoals"
                      f" WHERE strategy_id = {new_sid}") \
        == [(new_sid, new_lemma)]
    assert _rows(tdb, "SELECT target_kind, target_id FROM dead_attempts"
                      " WHERE pipeline_id = 'pipe-Erdos.p1'"
                      " ORDER BY target_kind") \
        == [("Goal", new_root), ("Strategy", new_sid)]
    assert _rows(tdb, "SELECT target_id FROM pipelines"
                      " WHERE id = 'pipe-Erdos.p1'") == [(str(new_root),)]
    assert _rows(tdb, "SELECT target_id FROM queue"
                      " WHERE problem='Erdos.p1'") == [(str(new_root),)]
    sd = _rows(tdb, "SELECT target_id, produced_goal_id,"
                    " produced_strategy_id, produced_group_id, payload FROM"
                    " strategist_decisions WHERE problem='Erdos.p1'")[0]
    assert sd[0] == new_root and sd[1] == new_lemma and sd[2] == new_sid
    assert sd[3] == new_gid
    assert json.loads(sd[4]) == {"target_goal_id": new_root,
                                 "group_id": new_gid}
    assert json.loads(_rows(tdb, "SELECT fired_json FROM routine_verdicts"
                                 " WHERE problem='Erdos.p1'")[0][0]) \
        == [{"goal_id": new_lemma}]

    p1 = tgt / "Problems" / "Erdos" / "p1"
    assert (p1 / ".groups" / str(new_gid)).is_dir(), \
        "the group projection dir follows its id"
    assert not (p1 / ".groups" / str(s["Erdos.p1"]["gid"])).exists()

    scratch = (tgt / "Problems" / "Erdos" / "p1" / "proofs"
               / f"_strategy_s{new_sid}.lean")
    assert scratch.exists(), "the strategy file follows its id"
    assert f"theorem s{new_sid}" in scratch.read_text(encoding="utf-8")
    root_lean = (tgt / "Problems" / "Erdos" / "p1"
                 / "Root.lean").read_text(encoding="utf-8")
    assert f"_strategy_s{new_sid}" in root_lean
    assert f"@Problems.Erdos.p1.s{new_sid}" in root_lean


def test_dry_run_prints_the_plan_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    src, _ = _workspace(tmp_path / "src", "Erdos.p1")
    out = tmp_path / "bundle"
    assert _export(src, "Erdos.p1", out, monkeypatch) == 0
    tgt, _ = _workspace(tmp_path / "tgt", "Erdos.p1", "Erdos.p2")
    tdb = tgt / "asterism.db"
    before = _rows(tdb, "SELECT * FROM goals ORDER BY id")
    before_files = sorted(
        p.name for p in (tgt / "Problems" / "Erdos" / "p1").iterdir())

    capsys.readouterr()
    assert _import(tgt, out, monkeypatch, dry_run=True) == 0
    printed = capsys.readouterr().out
    for section in ("classification", "collisions", "rows", "files",
                    "backups", "DRY RUN"):
        assert section in printed, f"dry-run plan has no {section!r} section"

    assert _rows(tdb, "SELECT * FROM goals ORDER BY id") == before
    assert sorted(
        p.name for p in (tgt / "Problems" / "Erdos" / "p1").iterdir()
    ) == before_files
    assert not (tgt / ".asterism" / "backups").exists()


def test_schema_mismatch_is_refused_without_allow_migrate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    src, _ = _workspace(tmp_path / "src", "Erdos.p1")
    out = tmp_path / "bundle"
    assert _export(src, "Erdos.p1", out, monkeypatch) == 0
    # age the bundle's schema
    conn = sqlite3.connect(str(out / "carry.db"))
    conn.execute(f"PRAGMA user_version = {db._CURRENT_USER_VERSION - 1}")
    conn.commit()
    conn.close()
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    m["schema_user_version"] = db._CURRENT_USER_VERSION - 1
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")

    tgt, _ = _workspace(tmp_path / "tgt", "Erdos.p1")
    assert _import(tgt, out, monkeypatch) == 2
    assert _import(tgt, out, monkeypatch, allow_migrate=True) == 0


def test_a_live_daemon_refuses_both_directions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DB a daemon is mid-tick on is not a thing to snapshot or
    rewrite (CLAUDE.md rule 3)."""
    import os
    import psutil
    src, _ = _workspace(tmp_path / "src", "Erdos.p1")
    out = tmp_path / "bundle"
    assert _export(src, "Erdos.p1", out, monkeypatch) == 0

    tgt, _ = _workspace(tmp_path / "tgt", "Erdos.p1")
    (tgt / ".asterism").mkdir(exist_ok=True)
    me = os.getpid()
    (tgt / ".asterism" / "daemon.pid").write_text(
        f"{me}\n{psutil.Process(me).create_time()}\n", encoding="utf-8")
    assert _import(tgt, out, monkeypatch) == 3

    (src / ".asterism").mkdir(exist_ok=True)
    (src / ".asterism" / "daemon.pid").write_text(
        f"{me}\n{psutil.Process(me).create_time()}\n", encoding="utf-8")
    assert _export(src, "Erdos.p1", tmp_path / "b2", monkeypatch) == 3


def test_export_tarball_excludes_the_id_keyed_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`.presearch/` and `.drafts/` are id-keyed run scratch the
    satellite registry already declares disposable; carrying them into
    a workspace whose ids mean something else is incident #167. The
    projections that ARE carried (`.groups/<id>/`) get renamed with
    their group instead."""
    ws, s = _workspace(tmp_path / "src", "Erdos.p1")
    pdir = ws / "Problems" / "Erdos" / "p1"
    (pdir / ".presearch").mkdir()
    (pdir / ".presearch" / "g7.md").write_text("cache", encoding="utf-8")
    (pdir / ".drafts").mkdir()
    (pdir / ".drafts" / "backward_g7.md").write_text("note", encoding="utf-8")
    out = tmp_path / "bundle"
    assert _export(ws, "Erdos.p1", out, monkeypatch) == 0
    with tarfile.open(out / "files.tar.gz", "r:gz") as tf:
        names = tf.getnames()
    assert not [n for n in names if ".presearch" in n or ".drafts" in n]
    gid = s["Erdos.p1"]["gid"]
    assert any(n.endswith(f".groups/{gid}/PROGRAMME.md") for n in names)
    assert any(n.endswith("Root.lean") for n in names)
