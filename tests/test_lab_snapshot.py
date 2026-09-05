"""`asterism lab snapshot` — one problem's state, taken while a daemon
writes, optionally rewound to a historical instant.

The slice is a `carry` bundle: the same pruned DB, the same tarball, the
same manifest, so `lab build` lands it with `carry import` and the one
answer to "which rows are this problem's" is `state/carry.py`'s. What
the lab adds is the instant it was taken, the code commit it was taken
at, and — with `--rewind` — the file plane moved to the same cutoff as
the rows, in the same action.
"""
from __future__ import annotations

import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from Tooling import lab
from Tooling.lab import snapshot as snap_mod
from Tooling.state import db, groups as groups_mod, project_docs

BEFORE = "2026-08-25T12:00:00+00:00"
CUT = "2026-08-26T04:11:05+00:00"
AFTER = "2026-08-27T00:00:00+00:00"
PROBLEM = "Erdos.p1"


# ---------------------------------------------------------------------
# the root is never defaulted
# ---------------------------------------------------------------------

def test_the_lab_root_has_no_default(monkeypatch):
    """The lab's state lives in the operator's development area, and
    production must not reference that area at all (lab_design.md §0). A
    default compiled in here would be exactly such a reference, shipped
    to every checkout — so with neither `--root` nor the environment the
    lab refuses, and the refusal names both ways in."""
    monkeypatch.delenv(lab.ROOT_ENV, raising=False)
    with pytest.raises(lab.LabError) as exc:
        lab.resolve_root(None)
    assert "--root" in str(exc.value) and lab.ROOT_ENV in str(exc.value)


def test_the_lab_root_comes_from_the_flag_then_the_environment(
        tmp_path, monkeypatch):
    monkeypatch.setenv(lab.ROOT_ENV, str(tmp_path / "from_env"))
    assert lab.resolve_root(None) == (tmp_path / "from_env").resolve()
    assert lab.resolve_root(tmp_path / "from_flag") == \
        (tmp_path / "from_flag").resolve()


def test_no_lab_module_hardcodes_an_absolute_path(monkeypatch):
    """The retired `Tooling/experiments/` runners each carried one —
    `D:/Asterism_exp`, `D:/Asterism_lab/runs`, a design dir under the
    operator's private tree — and the day that tree moved, `--build`
    failed for every arm on a machine that was not the author's. A lab
    module constant that is an absolute path is a path only one disk
    has; every root in this package is derived or passed in."""
    import importlib
    import pkgutil

    offenders = []
    for mod in pkgutil.walk_packages(lab.__path__, prefix="Tooling.lab."):
        m = importlib.import_module(mod.name)
        for name, value in vars(m).items():
            if isinstance(value, Path) and value.is_absolute() and \
                    name != "REPO":
                offenders.append(f"{m.__name__}.{name} = {value.as_posix()}")
    assert not offenders, (
        "lab constant(s) are absolute paths, which no other checkout "
        "has:\n  " + "\n  ".join(offenders))


# ---------------------------------------------------------------------
# a workspace to slice
# ---------------------------------------------------------------------

def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "live"
    (ws / "Problems").mkdir(parents=True)
    (ws / "Asterism.yaml").write_text("dispatch:\n  pool: 1\n",
                                      encoding="utf-8")
    conn = db.connect(ws / "asterism.db")
    db.init_schema(conn)
    ts = BEFORE
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES ('Erdos', ?)", (ts,))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES (?, ?, 'Erdos', 1)", (PROBLEM, ts))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES ('Erdos.p2', ?, 'Erdos', 1)", (ts,))
    gid = groups_mod.ensure_top_group(conn, PROBLEM, charter="c")
    pdir = db.problem_dir(ws, PROBLEM)
    (pdir / "proofs").mkdir(parents=True)
    root = db.insert_goal(conn, problem=PROBLEM, slug="main",
                          lean_path=(pdir / "Root.lean").relative_to(
                              ws).as_posix(),
                          statement="True", origin="root", status="open")
    (pdir / "Root.lean").write_text("theorem main : True := trivial\n",
                                    encoding="utf-8")
    late = db.insert_goal(conn, problem=PROBLEM, slug="late",
                          lean_path=(pdir / "proofs" / "L_late.lean"
                                     ).relative_to(ws).as_posix(),
                          statement="True", origin="forward", status="proved")
    (pdir / "proofs" / "L_late.lean").write_text("x\n", encoding="utf-8")
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (BEFORE, root))
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (AFTER, late))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body,"
                 " status, group_id, created_at) VALUES (?,1,'route',"
                 " 'passed', ?, ?)", (PROBLEM, gid, BEFORE))
    project_docs.write(ws, "Erdos", "user/anchor.md", "# anchor\n")
    conn.commit()
    conn.close()
    return ws


def _manifest(slice_dir: Path) -> dict:
    return json.loads((slice_dir / "manifest.json").read_text(
        encoding="utf-8"))


def _tar_names(slice_dir: Path) -> "set[str]":
    with tarfile.open(slice_dir / "files.tar.gz", "r:gz") as tf:
        return {m.name.replace("\\", "/") for m in tf.getmembers()}


# ---------------------------------------------------------------------
# the slice
# ---------------------------------------------------------------------

def test_snapshot_writes_a_carry_bundle_pruned_to_one_problem(tmp_path):
    """`carry.db` + `files.tar.gz` + `manifest.json`, and the DB holds
    the scoped problem's rows only — the shape `carry import` reads, so
    `lab build` needs no second definition of "belongs to P"."""
    ws = _workspace(tmp_path)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM)
    assert (sl.path / "carry.db").is_file()
    assert (sl.path / "files.tar.gz").is_file()
    assert (sl.path / "manifest.json").is_file()
    c = sqlite3.connect(sl.path / "carry.db")
    assert [r[0] for r in c.execute("SELECT name FROM problems")] == [PROBLEM]
    c.close()
    assert any(n.startswith(f"Problems/Erdos/p1/") for n in _tar_names(sl.path))


def test_snapshot_manifest_says_where_and_when_it_came_from(tmp_path):
    """A run comparable to another run is one whose slice can be placed
    in time and in the code: the instant the copy was taken, the
    Programme revision it carries, how many goals, and the framework
    commit that took it."""
    ws = _workspace(tmp_path)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM)
    m = _manifest(sl.path)
    assert m["problem"] == PROBLEM
    assert m["taken_utc"].endswith("+00:00")
    assert m["programme_rev"] == 1
    assert m["goal_count"] == 2
    assert m["code_commit"], "the commit the lab code was at"
    assert m["schema_user_version"] > 0


def test_snapshot_carries_the_projects_documents_the_wake_reads(tmp_path):
    """`carry export` leaves `_docs/` behind on purpose — it moves a
    problem into a workspace that already has that Project's shelf. A
    lab workspace is built EMPTY, so nothing else will ever supply it,
    and `_docs/user/` is the owner's notes the Strategist's Context
    renders while `_docs/agent/` is the theory shelf the reviewer reads.
    A slice without them replays a scene the original wake never saw."""
    ws = _workspace(tmp_path)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM)
    assert "Problems/Erdos/_docs/user/anchor.md" in _tar_names(sl.path)


def test_snapshot_reads_the_live_db_without_taking_a_write_lock(tmp_path):
    """Never `shutil.copyfile`: in WAL mode the committed state lives
    partly in `-wal`, and a bare file copy silently loses it. The
    snapshot must also work while a daemon writes — that is the whole
    reason it exists as its own noun rather than as `carry export`,
    which refuses on `daemon.pid`."""
    ws = _workspace(tmp_path)
    (ws / ".asterism").mkdir(exist_ok=True)
    (ws / ".asterism" / "daemon.pid").write_text("999999 0.0",
                                                 encoding="utf-8")
    live = db.connect(ws / "asterism.db")
    live.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES ('Erdos.p3', ?, 'Erdos', 1)",
                 (BEFORE,))
    live.commit()          # committed into the -wal, not yet checkpointed
    try:
        sl = snap_mod.take(ws, tmp_path / "lab", problem="Erdos.p3")
        c = sqlite3.connect(sl.path / "carry.db")
        assert [r[0] for r in c.execute("SELECT name FROM problems")] == \
            ["Erdos.p3"], "the -wal half of the commit travelled"
        c.close()
    finally:
        live.close()


def test_snapshot_refuses_a_problem_the_workspace_does_not_hold(tmp_path):
    ws = _workspace(tmp_path)
    with pytest.raises(lab.LabError, match="Erdos.p99"):
        snap_mod.take(ws, tmp_path / "lab", problem="Erdos.p99")


# ---------------------------------------------------------------------
# --rewind: the DB and the file plane in ONE action
# ---------------------------------------------------------------------

def test_rewind_moves_the_rows_and_the_files_in_one_action(tmp_path):
    """The 2026-09-04 defect, made structurally impossible: the rewind
    used to be a DB tool and the files were copied from the live tree by
    whoever built the scratch, so a judge rewound to 23:31Z read a proof
    that landed eleven hours later. One command owns both planes — the
    slice that comes out is at the cutoff on disk as well as in the
    rows, and its ledger says on what signal each directory was
    decided."""
    ws = _workspace(tmp_path)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)
    c = sqlite3.connect(sl.path / "carry.db")
    assert [r[0] for r in c.execute("SELECT slug FROM goals")] == ["main"], \
        "the goal born after the cutoff is gone from the rows"
    c.close()
    names = _tar_names(sl.path)
    assert "Problems/Erdos/p1/proofs/L_late.lean" not in names, \
        "...and its proof file is gone from the tarball with it"
    assert "Problems/Erdos/p1/Root.lean" in names
    ledger = json.loads((sl.path / "_rewind_ledger.json").read_text(
        encoding="utf-8"))
    assert ledger["cutoff"] == CUT
    assert "Problems/Erdos/p1/proofs" in ledger["directories"]
    assert _manifest(sl.path)["rewind"]["cutoff"] == CUT


def test_a_rewound_slice_keeps_the_pre_rewind_db_to_replay_against(
        tmp_path):
    """A judge replay re-judges a proposal the rewind DELETED — that is
    what makes it historical. The body and the decisions therefore
    cannot come from the rewound DB, so the slice keeps the pruned
    pre-rewind copy beside it as `source.db`; `judge_round` reads the
    proposal there and the scene from `carry.db`."""
    ws = _workspace(tmp_path)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)
    src = sl.path / "source.db"
    assert src.is_file()
    c = sqlite3.connect(src)
    assert sorted(r[0] for r in c.execute("SELECT slug FROM goals")) == \
        ["late", "main"], "the pre-rewind rows, pruned to the problem"
    c.close()
    assert _manifest(sl.path)["rewind"]["source_db"] == "source.db"


def test_a_rewound_slice_re_renders_tree_from_the_rewound_rows(tmp_path):
    """`TREE.md` is a render of the DB and travels in the tarball. The
    first experiment-3 run was judged against a TREE that still listed
    the goal the proposal was about to mint."""
    ws = _workspace(tmp_path)
    pdir = db.problem_dir(ws, PROBLEM)
    (pdir / "TREE.md").write_text("- late [g2] — from the future\n",
                                  encoding="utf-8")
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)
    with tarfile.open(sl.path / "files.tar.gz", "r:gz") as tf:
        member = tf.extractfile("Problems/Erdos/p1/TREE.md")
        body = member.read().decode("utf-8")
    assert "from the future" not in body


def test_a_slice_id_is_derivable_from_the_problem_and_the_cutoff(tmp_path):
    """A `rewind:` block in lab.yaml names a problem and an instant, not
    a directory — so the id it would produce has to be computable
    without taking the snapshot, or every `lab run` takes a second copy
    of a slice it already has."""
    ws = _workspace(tmp_path)
    want = snap_mod.slice_id(PROBLEM, cutoff=CUT)
    sl = snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)
    assert sl.id == want
    assert sl.path == lab.snapshots_dir(tmp_path / "lab") / want


def test_taking_a_slice_twice_over_the_same_id_refuses(tmp_path):
    """A half-overwritten slice is a slice whose manifest describes rows
    it no longer holds. Reuse is `ensure_slice`'s decision, made before
    the copy starts, never a partial write on top of an existing one."""
    ws = _workspace(tmp_path)
    snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)
    with pytest.raises(lab.LabError, match="already"):
        snap_mod.take(ws, tmp_path / "lab", problem=PROBLEM, cutoff=CUT)


def test_ensure_slice_reuses_a_rewound_slice_that_already_exists(tmp_path):
    ws = _workspace(tmp_path)
    first = snap_mod.ensure_slice(tmp_path / "lab", workspace=ws,
                                  problem=PROBLEM, cutoff=CUT)
    stamp = _manifest(first.path)["taken_utc"]
    again = snap_mod.ensure_slice(tmp_path / "lab", workspace=ws,
                                  problem=PROBLEM, cutoff=CUT)
    assert again.id == first.id
    assert _manifest(again.path)["taken_utc"] == stamp, \
        "the second call reused the copy rather than taking a new one"
