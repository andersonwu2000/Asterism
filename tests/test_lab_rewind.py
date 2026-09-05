"""`Tooling.lab.rewind` — rewind a problem's DB state to a
cutoff instant so a historical wake can be replayed with today's
prompts (experiments 2/3, 2026-08-30: "would the NL layer mint the
fin10 table brick again?").

The rewind is an APPROXIMATION and says so: rows created after the
cutoff are deleted, goal statuses are read back from `goal_events`,
strategies whose goal is no longer proved fall back to `proposed`,
groups touched after the cutoff go back to `active`. It runs on a COPY;
the live DB is never opened for writing.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from Tooling.lab import rewind as tt
from Tooling.state import db

CUT = "2026-08-26T04:11:05+00:00"
BEFORE = "2026-08-25T12:00:00+00:00"
AFTER = "2026-08-27T00:00:00+00:00"


def _seed(conn: sqlite3.Connection):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done) VALUES (?, ?, 1)",
                 ("p", BEFORE))
    old = db.insert_goal(conn, problem="p", slug="old", lean_path="Problems/p/proofs/L_old.lean",
                         statement="T", origin="backward", depth=1)
    new = db.insert_goal(conn, problem="p", slug="new", lean_path="Problems/p/proofs/L_new.lean",
                         statement="T", origin="backward", depth=1)
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (BEFORE, old))
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (AFTER, new))
    # old goal: open before the cutoff, proved after it
    conn.execute("INSERT INTO goal_events (goal_id, problem, from_status, to_status, event, reason, at)"
                 " VALUES (?,?,?,?,?,?,?)", (old, "p", "open", "attempting", "backward_decomposed", "", BEFORE))
    conn.execute("INSERT INTO goal_events (goal_id, problem, from_status, to_status, event, reason, at)"
                 " VALUES (?,?,?,?,?,?,?)", (old, "p", "attempting", "proved", "set_terminal", "", AFTER))
    db.update_goal_status(conn, old, "proved")
    s_old = db.insert_strategy(conn, goal_id=old, lean_path="Problems/p/proofs/L_old.lean",
                               scratch_path="Problems/p/proofs/_strategy_s1.lean", created_by="x")
    db.update_strategy_status(conn, s_old, "succeeded")
    conn.execute("UPDATE strategies SET created_at=? WHERE id=?", (BEFORE, s_old))
    s_new = db.insert_strategy(conn, goal_id=old, lean_path="Problems/p/proofs/L_old.lean",
                               scratch_path="Problems/p/proofs/_strategy_s2.lean", created_by="x")
    conn.execute("UPDATE strategies SET created_at=? WHERE id=?", (AFTER, s_new))
    db.link_subgoal(conn, strategy_id=s_new, subgoal_id=new, position=0)
    conn.execute("INSERT INTO strategist_decisions (problem, triggered_at_tick, trigger_kind, decision_kind,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?)", ("p", 1, "routine", "Noop", BEFORE, BEFORE))
    conn.execute("INSERT INTO strategist_decisions (problem, triggered_at_tick, trigger_kind, decision_kind,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?)", ("p", 2, "routine", "Noop", AFTER, AFTER))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body, status, verdict, dialogue, rounds, created_at)"
                 " VALUES (?,?,?,?,?,?,?,?)", ("p", 1, "b1", "passed", "{}", "[]", 0, BEFORE))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body, status, verdict, dialogue, rounds, created_at)"
                 " VALUES (?,?,?,?,?,?,?,?)", ("p", 2, "b2", "passed", "{}", "[]", 0, AFTER))
    conn.commit()
    return old, new, s_old, s_new


def test_rewind_deletes_post_cutoff_rows_and_rewinds_statuses(conn):
    old, new, s_old, s_new = _seed(conn)
    rep = tt.rewind(conn, problem="p", cutoff=CUT)
    assert db.get_goal(conn, new) is None, "a goal born after the cutoff is gone"
    assert db.get_goal(conn, old)["status"] == "attempting", "read back from goal_events"
    assert conn.execute("SELECT status FROM strategies WHERE id=?", (s_old,)).fetchone()["status"] == "proposed", \
        "its goal is no longer proved, so the win is not yet won"
    assert conn.execute("SELECT COUNT(*) FROM strategies WHERE id=?", (s_new,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM strategy_subgoals WHERE strategy_id=?", (s_new,)).fetchone()[0] == 0
    assert [r["rev"] for r in conn.execute("SELECT rev FROM programme_revisions WHERE problem='p'")] == [1]
    assert conn.execute("SELECT COUNT(*) FROM strategist_decisions WHERE problem='p'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM goal_events WHERE at > ?", (CUT,)).fetchone()[0] == 0
    assert rep["goals_deleted"] == 1 and rep["strategies_deleted"] == 1 and rep["goals_rewound"] == 1


def test_rewind_refuses_the_live_database(tmp_path, monkeypatch):
    """The rewind mutates: only a copy may be opened."""
    import pytest
    live = tmp_path / "asterism.db"
    live.write_text("", encoding="utf-8")
    monkeypatch.setattr(tt, "_looks_live", lambda p: True)
    with pytest.raises(RuntimeError, match="live"):
        tt.open_copy_for_rewind(live)


def test_rewind_clamps_group_clocks_to_the_last_surviving_commit(conn):
    """The trigger derivation reads `groups.last_strategist_at` as the
    batch-acknowledgement ratchet. Clamping it to the cutoff instant
    makes the batch resolved just before look acknowledged, and the
    replay derives `routine` instead of the `inject_batch_done` the
    original wake had. The clock goes back to the last SURVIVING
    strategist commit of that group."""
    _seed(conn)
    conn.execute("INSERT INTO groups (problem, charter, status, created_at, updated_at,"
                 " last_routine_at, last_strategist_at) VALUES (?,?,?,?,?,?,?)",
                 ("p", "c", "active", BEFORE, AFTER, AFTER, AFTER))
    gid = conn.execute("SELECT id FROM groups WHERE problem='p'").fetchone()["id"]
    conn.execute("UPDATE strategist_decisions SET group_id=? WHERE problem='p'", (gid,))
    conn.commit()
    tt.rewind(conn, problem="p", cutoff=CUT)
    g = conn.execute("SELECT last_strategist_at, last_routine_at FROM groups WHERE id=?", (gid,)).fetchone()
    assert g["last_strategist_at"] == BEFORE, "the surviving decision's created_at, not the cutoff"
    assert g["last_routine_at"] <= BEFORE


def test_prune_proof_files_removes_files_of_deleted_rows(tmp_path, conn):
    """Files on disk must match the rewound DB: a brick or strategy
    file born after the cutoff would still show in CATALOG / inspect.

    (`L_old.lean` leaves too, under the second rule the test below owns
    — its goal survives the rewind but its PROOF postdates the cutoff.
    What this one pins is that the deleted rows' files go and the rows
    that survived unchanged keep theirs.)"""
    old, new, s_old, s_new = _seed(conn)
    snap = tmp_path / "snap.db"
    snap_conn = sqlite3.connect(snap)
    conn.backup(snap_conn); snap_conn.close()
    proofs = tmp_path / "ws" / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    for name in ("L_old.lean", "L_new.lean", "_strategy_s1.lean", "_strategy_s2.lean", "L_unrelated.lean"):
        (proofs / name).write_text("x", encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    removed = tt.prune_proof_files(conn, snapshot_db=snap, workspace=tmp_path / "ws",
                                   problem="p", cutoff=CUT)
    assert "L_new.lean" in removed and "_strategy_s2.lean" in removed
    assert (proofs / "_strategy_s1.lean").exists(),         "the surviving strategy's file stays"
    assert (proofs / "L_unrelated.lean").exists(), "files the DB never knew are left alone"


def test_refresh_derived_files_rewrites_tree_without_the_deleted_goals(tmp_path, conn):
    """Experiment 3, first run (2026-08-30): the scratch DB was rewound
    but `Problems/<p>/TREE.md` was the snapshot's file — it still listed
    the goal the replayed proposal was about to mint, and the judge's
    projection copies TREE.md verbatim, so the judge rebutted the
    proposal as 'duplicate work'. The rendered files are derived from
    the DB and must be re-derived after the rewind."""
    old, new, s_old, s_new = _seed(conn)
    pdir = tmp_path / "ws" / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "TREE.md").write_text("- new [g%d] — stale\n- old [g%d]\n" % (new, old),
                                  encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    written = tt.refresh_derived_files(conn, workspace=tmp_path / "ws", problem="p")
    tree = (pdir / "TREE.md").read_text(encoding="utf-8")
    assert f"[g{new}]" not in tree and "stale" not in tree
    assert f"[g{old}]" in tree
    assert any(p.name == "TREE.md" for p in written)


def test_prune_removes_a_proof_that_landed_after_the_cutoff(tmp_path, conn):
    """A goal that already EXISTED at the cutoff survives the rewind —
    and its `proofs/L_<slug>.lean` survived with it, holding whatever
    proof landed later. `_seed`'s `old` is exactly that shape: open at
    the cutoff, proved after it.

    The 2026-09-04 judge replay paid for it. `run_matrix` / the
    judge-replay scratch builder copy `Problems/<p>/` from the LIVE
    tree, `rewind` moves the DB only, and `prune_proof_files` removed
    the files of DELETED rows only — so a rewound judge read a proof
    that did not exist at the instant it was judging
    (`docs/internal/experiments/criterion2_replay_2026-09-04.md` §2.3,
    §五.3). Derived from the record, never from mtime: the goal is not
    proved in the rewound DB and IS proved in the snapshot, so the
    bytes on disk postdate the cutoff."""
    old, new, s_old, s_new = _seed(conn)
    snap = tmp_path / "snap.db"
    snap_conn = sqlite3.connect(snap)
    conn.backup(snap_conn); snap_conn.close()
    proofs = tmp_path / "ws" / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    for name in ("L_old.lean", "L_new.lean", "_strategy_s1.lean",
                 "_strategy_s2.lean", "L_unrelated.lean"):
        (proofs / name).write_text("x", encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    removed = tt.prune_proof_files(conn, snapshot_db=snap,
                                   workspace=tmp_path / "ws", problem="p",
                                   cutoff=CUT)
    assert "L_old.lean" in removed, \
        "the proof landed after the cutoff — the rewound scene has no such file"
    assert not (proofs / "L_old.lean").exists()
    assert (proofs / "L_unrelated.lean").exists(), \
        "files the DB never knew are left alone"


def test_rewind_maps_a_retired_status_out_of_the_event_journal(conn):
    """v51 (`8c1aba0d`) retired the goal status `dead` and narrowed the
    `goals.status` CHECK, but deliberately left the historical
    `goal_events` rows alone — "the history is the point". `rewind`
    reads its statuses back out of that journal, so on any post-v51 DB
    with pre-v51 history it wrote `dead` into a column that no longer
    accepts it and died on the CHECK. The mapping belongs at the read,
    not in a migration that would erase the forensics v51 preserved.

    The goal starts `open` — REVIVED after the cutoff — so the rewind
    has to actually WRITE the mapped status. Seeded already-`shelved`
    (as this test was until the lab port) the rewind finds want ==
    status and returns without touching the column, so the CHECK the
    mapping exists to survive is never reached and the test passes
    with the mapping deleted."""
    _seed(conn)
    gid = db.insert_goal(conn, problem="p", slug="retired",
                         lean_path="Problems/p/proofs/L_retired.lean",
                         statement="T", origin="backward", depth=1)
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (BEFORE, gid))
    conn.execute(
        "INSERT INTO goal_events (goal_id, problem, from_status, to_status,"
        " event, reason, at) VALUES (?,?,?,?,?,?,?)",
        (gid, "p", "attempting", "dead", "wrong_context", "", BEFORE))
    db.update_goal_status(conn, gid, "open")
    conn.commit()
    tt.rewind(conn, problem="p", cutoff=CUT)
    assert db.get_goal(conn, gid)["status"] == "shelved", \
        "the v51 dead→shelved mapping, applied where the journal is read"


def test_rewind_stops_loudly_on_a_retired_status_nobody_mapped(conn,
                                                              monkeypatch):
    """The other half of the mapping's contract: a journal status the
    schema dropped and this table does not name must stop the rewind
    with the migration to look at, not become whatever is nearest."""
    import pytest
    _seed(conn)
    gid = db.insert_goal(conn, problem="p", slug="unmapped",
                         lean_path="Problems/p/proofs/L_unmapped.lean",
                         statement="T", origin="backward", depth=1)
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (BEFORE, gid))
    conn.execute(
        "INSERT INTO goal_events (goal_id, problem, from_status, to_status,"
        " event, reason, at) VALUES (?,?,?,?,?,?,?)",
        (gid, "p", "attempting", "vaporized", "x", "", BEFORE))
    conn.commit()
    with pytest.raises(RuntimeError, match="vaporized"):
        tt.rewind(conn, problem="p", cutoff=CUT)


# ─── the surfaces the rewind did not reach (2026-09-04 replay §五.1) ───
#
# `26bccdef` rewound the DB and `proofs/`. Everything else the judge's
# projection and the Strategist's Context read was still the LIVE file:
# `_docs/{user,agent}/` (the judge's `{papers_dir}`), `.drafts/`,
# `.presearch/`, `.groups/`, and the rendered `PROGRAMME.md` / `TREE.md`.
# The clean replay report recorded the consequence: two fires in row 1362
# cite `tw_restoration_equivalence.md`, written 10.4 h AFTER that row's
# cutoff (`criterion2_replay2_2026-09-04.md` §五.1).

def _stamp_mtime(path, iso: str) -> None:
    from datetime import datetime
    ts = datetime.fromisoformat(iso).timestamp()
    os.utime(path, (ts, ts))


def _snapshot(conn: sqlite3.Connection, tmp_path):
    snap = tmp_path / "snap.db"
    snap_conn = sqlite3.connect(snap)
    conn.backup(snap_conn)
    snap_conn.close()
    return snap


def _docs_ws(tmp_path):
    ws = tmp_path / "ws"
    (ws / "Problems" / "p" / "_docs" / "agent").mkdir(parents=True)
    (ws / "Problems" / "p" / "_docs" / "user").mkdir(parents=True)
    return ws


def _insert_group(conn: sqlite3.Connection, created_at: str,
                  parent=None) -> int:
    cur = conn.execute(
        "INSERT INTO groups (problem, parent_group_id, charter, status,"
        " created_at, updated_at) VALUES (?,?,?,?,?,?)",
        ("p", parent, "c", "active", created_at, created_at))
    conn.commit()
    return int(cur.lastrowid)


def test_prune_project_docs_drops_a_theory_document_written_after_the_cutoff(
        tmp_path, conn):
    """`_docs/agent/` has a DB record: `theory_documents.path` +
    `created_at`. A document the rewind's row-delete erased must leave
    the scratch with it — the judge's `{papers_dir}` points straight at
    this tree."""
    _seed(conn)
    ws = _docs_ws(tmp_path)
    old_doc = "Problems/p/_docs/agent/g1_20260825-1200_old.md"
    new_doc = "Problems/p/_docs/agent/g1_20260827-0000_new.md"
    for rel in (old_doc, new_doc):
        (ws / rel).write_text("<!--\npipeline: pid\n-->\n\n# doc\n",
                              encoding="utf-8")
    for rel, at in ((old_doc, BEFORE), (new_doc, AFTER)):
        conn.execute(
            "INSERT INTO theory_documents (problem, objective, situation,"
            " path, status, rounds, created_at) VALUES (?,?,?,?,?,?,?)",
            ("p", "o", "s", rel, "accepted", 1, at))
    conn.commit()
    snap = _snapshot(conn, tmp_path)
    tt.rewind(conn, problem="p", cutoff=CUT)
    assert conn.execute("SELECT COUNT(*) FROM theory_documents"
                        ).fetchone()[0] == 1, \
        "the rewind deletes the row before the file is judged"
    led = tt.prune_project_docs(conn, snapshot_db=snap, workspace=ws,
                                problem="p", cutoff=CUT)
    assert not (ws / new_doc).exists()
    assert (ws / old_doc).exists(), \
        "the surviving row's document is dated by the DB, never by mtime"
    agent = led["Problems/p/_docs/agent"]
    assert agent["dropped"] == 1 and agent["kept"] == 1
    assert "theory_documents" in agent["provenance"]


def test_prune_project_docs_dates_owner_notes_by_mtime_and_says_which(
        tmp_path, conn):
    """`_docs/user/` is the owner's own writing — no DB row exists for
    it (`theory_documents` is the agent's half). The rewind must date it
    off git when the workspace is a checkout and off mtime otherwise,
    and SAY which in the ledger: a reader who cannot tell which signal
    was used cannot tell how much to trust the scene."""
    _seed(conn)
    ws = _docs_ws(tmp_path)
    keep = ws / "Problems/p/_docs/user/anchor_note.md"
    drop = ws / "Problems/p/_docs/user/tw_restoration_equivalence.md"
    for p in (keep, drop):
        p.write_text("note\n", encoding="utf-8")
    _stamp_mtime(keep, BEFORE)
    _stamp_mtime(drop, AFTER)
    snap = _snapshot(conn, tmp_path)
    tt.rewind(conn, problem="p", cutoff=CUT)
    led = tt.prune_project_docs(conn, snapshot_db=snap, workspace=ws,
                                problem="p", cutoff=CUT)
    assert not drop.exists(), \
        "written after the cutoff — the 1362 fires that cited it"
    assert keep.exists()
    user = led["Problems/p/_docs/user"]
    assert user["provenance"] == "mtime", \
        "the ledger names the signal actually used"
    assert user["kept"] == 1 and user["dropped"] == 1


def test_prune_project_docs_reads_git_history_from_the_source_workspace(
        tmp_path, conn, monkeypatch):
    """The lab rewinds a STAGED slice: the bytes sit in a staging tree
    that is not a checkout and never will be, while the git history of
    the same workspace-relative path is in the live workspace the slice
    came from. `_docs/user/` is the owner's own writing and has no DB
    row at all, so git is its only authoritative signal — asking the
    staging tree for it silently demotes the whole directory to mtime,
    which a tar round-trip is free to rewrite. `git_root` splits the two
    questions so the dating stays where the commits are."""
    _seed(conn)
    ws = _docs_ws(tmp_path)
    live = tmp_path / "live"
    live.mkdir()
    note = ws / "Problems/p/_docs/user/anchor_note.md"
    note.write_text("note\n", encoding="utf-8")
    _stamp_mtime(note, AFTER)          # the mtime says "drop it"

    asked: "list[str]" = []

    def _fake_git_iso(root, rel):
        asked.append(str(root))
        return BEFORE if Path(root) == live else None

    monkeypatch.setattr(tt, "_git_iso", _fake_git_iso)
    snap = _snapshot(conn, tmp_path)
    tt.rewind(conn, problem="p", cutoff=CUT)
    led = tt.prune_project_docs(conn, snapshot_db=snap, workspace=ws,
                                problem="p", cutoff=CUT, git_root=live)
    assert note.exists(), \
        "the commit predates the cutoff — the tar's mtime is not the fact"
    assert led["Problems/p/_docs/user"]["provenance"] == "git"
    assert str(live) in asked, "git was asked of the source workspace"


def test_prune_project_docs_drops_every_owner_note_it_cannot_date(
        tmp_path, conn, monkeypatch):
    """No git history and no readable mtime = no way to tell which side
    of the cutoff a note is on. A judge reading nothing is safer than a
    judge reading the future, so the whole `_docs/user/` goes and the
    ledger records that it did."""
    _seed(conn)
    ws = _docs_ws(tmp_path)
    for name in ("a.md", "b.md"):
        (ws / "Problems/p/_docs/user" / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(tt, "_git_iso", lambda ws_, rel: None)
    monkeypatch.setattr(tt, "_mtime_iso", lambda p: None)
    snap = _snapshot(conn, tmp_path)
    tt.rewind(conn, problem="p", cutoff=CUT)
    led = tt.prune_project_docs(conn, snapshot_db=snap, workspace=ws,
                                problem="p", cutoff=CUT)
    assert list((ws / "Problems/p/_docs/user").glob("*.md")) == []
    user = led["Problems/p/_docs/user"]
    assert user["provenance"] == "none" and user["kept"] == 0
    assert user["dropped"] == 2


def test_prune_run_scratch_keeps_only_ids_alive_at_the_cutoff(tmp_path, conn):
    """`.presearch/g<goal>.md`, `.drafts/*_g<goal>.md`,
    `.drafts/strategist_plan_g<group>.md` and `.groups/<group>/` are all
    id-keyed. An id the rewind deleted names a thing that did not exist
    at the cutoff, so its file cannot either."""
    old, new, s_old, s_new = _seed(conn)
    g_old = _insert_group(conn, BEFORE)
    g_new = _insert_group(conn, AFTER, parent=g_old)
    pdir = tmp_path / "ws" / "Problems" / "p"
    (pdir / ".presearch").mkdir(parents=True)
    (pdir / ".drafts").mkdir()
    (pdir / ".groups" / str(g_old)).mkdir(parents=True)
    (pdir / ".groups" / str(g_new)).mkdir(parents=True)
    files = {
        f".presearch/g{old}.md": True,
        f".presearch/g{new}.md": False,
        f".drafts/backward_g{old}.md": True,
        f".drafts/backward_g{new}.md": False,
        f".drafts/strategist_plan_g{g_old}.md": True,
        f".drafts/strategist_plan_g{g_new}.md": False,
        f".groups/{g_old}/PROGRAMME.md": True,
        f".groups/{g_new}/PROGRAMME.md": False,
    }
    for rel in files:
        (pdir / rel).write_text("x", encoding="utf-8")
        _stamp_mtime(pdir / rel, BEFORE)
    tt.rewind(conn, problem="p", cutoff=CUT)
    led = tt.prune_run_scratch(conn, workspace=tmp_path / "ws", problem="p",
                               cutoff=CUT)
    for rel, keep in files.items():
        assert (pdir / rel).exists() is keep, rel
    assert not (pdir / ".groups" / str(g_new)).exists(), \
        "the group's whole directory goes with its id"
    assert led["Problems/p/.presearch"]["dropped"] == 1
    assert led["Problems/p/.groups"]["dropped"] == 1
    # Signal ATOMS, deduplicated. An entry decided by a live id AND a
    # date carries both, and joining the composite strings rendered the
    # real `.presearch` as `goal_id+mtime+goal_id+decision_id+mtime+`
    # `decision_id` — which reads like six signals.
    assert led["Problems/p/.presearch"]["provenance"] == "goal_id+mtime"


def test_prune_run_scratch_drops_a_live_ids_note_rewritten_after_the_cutoff(
        tmp_path, conn):
    """The 09-04 leak that had nothing to do with ids: group 691 existed
    long before the cutoff, but `.drafts/strategist_plan_g691.md` is a
    REWRITE-by-contract file and the copy in the scratch was the 09-04
    one (`criterion2_replay2_2026-09-04.md` §五.1 — the judge's Context
    showed 2305 chars where the era's note had 1660). A live id is not
    enough; the bytes must also predate the cutoff."""
    _seed(conn)
    g = _insert_group(conn, BEFORE)
    pdir = tmp_path / "ws" / "Problems" / "p"
    (pdir / ".drafts").mkdir(parents=True)
    note = pdir / ".drafts" / f"strategist_plan_g{g}.md"
    note.write_text("tomorrow's plan\n", encoding="utf-8")
    _stamp_mtime(note, AFTER)
    tt.rewind(conn, problem="p", cutoff=CUT)
    tt.prune_run_scratch(conn, workspace=tmp_path / "ws", problem="p",
                         cutoff=CUT)
    assert not note.exists()


def test_refresh_derived_files_removes_a_programme_the_rewind_erased(
        tmp_path, conn):
    """`PROGRAMME.md` is a render of the current passed revision. When
    the rewind deletes every passed revision a group had, `render`
    returns None and writes nothing — so the LIVE file survived into the
    scratch and the judge read a Programme that did not exist yet."""
    _seed(conn)
    g = _insert_group(conn, BEFORE)
    conn.execute("UPDATE programme_revisions SET group_id = ? WHERE problem='p'",
                 (g,))
    conn.execute("DELETE FROM programme_revisions WHERE created_at = ?",
                 (BEFORE,))
    conn.commit()
    pdir = tmp_path / "ws" / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "PROGRAMME.md").write_text("# rev 2 — from the future\n",
                                       encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    tt.refresh_derived_files(conn, workspace=tmp_path / "ws", problem="p")
    assert not (pdir / "PROGRAMME.md").exists(), \
        "no passed revision at the cutoff means no rendered Programme"


def test_rewind_files_writes_a_ledger_of_every_directory(tmp_path, conn):
    """One line per directory in the rewind output, and the same rows
    durable in the scratch as `_rewind_ledger.json` — the experiment
    that reads the scratch a week later must be able to state which
    surfaces were rewound, on what signal, and what was dropped."""
    import json
    old, new, s_old, s_new = _seed(conn)
    _insert_group(conn, BEFORE)
    ws = _docs_ws(tmp_path)
    pdir = ws / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_new.lean").write_text("x", encoding="utf-8")
    (pdir / ".presearch").mkdir()
    (pdir / ".presearch" / f"g{new}.md").write_text("x", encoding="utf-8")
    (pdir / ".drafts").mkdir()
    (pdir / ".groups").mkdir()
    snap = _snapshot(conn, tmp_path)
    tt.rewind(conn, problem="p", cutoff=CUT)
    led = tt.rewind_files(conn, snapshot_db=snap, workspace=ws, problem="p",
                          cutoff=CUT)
    on_disk = json.loads(
        (ws / "_rewind_ledger.json").read_text(encoding="utf-8"))
    assert on_disk == led
    dirs = led["directories"]
    for key in ("Problems/p/proofs", "Problems/p/_docs/agent",
                "Problems/p/_docs/user", "Problems/p/.drafts",
                "Problems/p/.presearch", "Problems/p/.groups"):
        assert key in dirs, key
        assert {"kept", "dropped", "provenance"} <= set(dirs[key])
    assert led["cutoff"] == CUT
    assert not (pdir / "proofs" / "L_new.lean").exists()
    assert any(p.endswith("TREE.md") for p in led["regenerated"])
