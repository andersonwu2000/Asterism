"""`asterism lab run` and `lab gc` — the DRIVER and the RECORD.

The drivers are the four retired `Tooling/experiments/` runners plus the
framework's own daemon, with their logic kept and their hardcoded paths
gone. The record is what makes two runs comparable after the workspaces
are gone: the slice, the code commit, the prompts as they were on disk,
the seats as the run actually had them, and the provider's own token
accounting.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from Tooling import lab
from Tooling.lab import build as build_mod
from Tooling.lab import driver as driver_mod
from Tooling.lab import run as run_mod
from Tooling.lab import snapshot as snap_mod
from Tooling.lab import spec as spec_mod
from Tooling.state import db, groups as groups_mod

BEFORE = "2026-08-25T12:00:00+00:00"
PROBLEM = "Erdos.p1"


# ---------------------------------------------------------------------
# the drivers
# ---------------------------------------------------------------------

def test_every_declared_driver_kind_has_an_implementation():
    """`lab.yaml` validates `kind:` against `spec.DRIVER_KINDS` and the
    driver dispatches on `driver.KINDS`. Two lists that can disagree is
    an arm that validates and then dies in the workspace it just built."""
    assert set(spec_mod.DRIVER_KINDS) == set(driver_mod.KINDS)


def test_a_driver_refuses_a_workspace_a_daemon_owns(tmp_path):
    ws = tmp_path / "live"
    (ws / ".asterism").mkdir(parents=True)
    (ws / ".asterism" / "daemon.pid").write_text("4242 0.0", encoding="utf-8")
    with pytest.raises(SystemExit, match="lab copy"):
        driver_mod.assert_scratch(ws)
    plain = tmp_path / "scratch"
    plain.mkdir()
    driver_mod.assert_scratch(plain)          # the negative half


def test_a_driver_refuses_to_run_code_from_outside_its_workspace(tmp_path):
    """The arm's whole variable can be a prompt overlay, and prompts are
    read from the importing package's own directory
    (`pipeline.PROMPT_DIR`). A driver that picked up the framework
    checkout's `Tooling` would run the UNEDITED prompt and file the
    result under the arm's name — the failure `lab build`'s overlay
    refusals exist to stop, one layer down."""
    ws = tmp_path / "ws"
    (ws / "Tooling").mkdir(parents=True)
    driver_mod.assert_workspace_code(ws, str(ws / "Tooling" / "__init__.py"))
    with pytest.raises(SystemExit, match="OUTSIDE"):
        driver_mod.assert_workspace_code(
            ws, str(tmp_path / "checkout" / "Tooling" / "__init__.py"))


def test_a_driver_hardens_the_console_before_it_enters_the_pipeline(
        monkeypatch):
    """A driver is an entry point into the same pipeline `asterism run`
    enters, and the CLI hardens the console first. The retired runners
    did not: on a cp950 console the `⚠` in a length warning raised
    UnicodeEncodeError INSIDE the wake, and arm C run 2 of the push
    experiment (2026-09-03) died with its proposal written, its
    Adversary round spent and nothing committed."""
    import io
    import sys
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp950"))
    driver_mod.harden_console()
    print("⚠ i ∉ A")          # the two characters that killed the run
    sys.stdout.flush()
    assert "⚠ i ∉ A" in sys.stdout.buffer.getvalue().decode("utf-8")


# ---------------------------------------------------------------------
# judge_round — the historical proposal
# ---------------------------------------------------------------------

def test_reconstructed_decisions_parse_with_the_inject_prose_under_proof():
    """The DB keeps an Inject's prose in `brief`; the parser reads it
    from `proof`. A reconstruction that used the column name would hand
    the judge an Inject with no argument — and judge that."""
    from Tooling.pipeline.strategist.model import parse_decisions
    rows = [
        {"decision_kind": "ConfirmShelve", "target_id": 9061, "brief": None,
         "reason": "parked", "payload": "{}"},
        {"decision_kind": "Inject", "target_id": None,
         "brief": "### Brick `x`\n\nMint exactly one theorem…",
         "reason": None,
         "payload": json.dumps({"pipeline": "Formalizer", "step_index": 0,
                                "batch_size": 1})},
    ]
    objs = driver_mod.reconstruct_decisions(rows)
    decisions, err = parse_decisions(json.dumps(objs))
    assert not err and decisions is not None
    shelve, inject = decisions
    assert shelve.kind == "ConfirmShelve" and shelve.target_id == 9061
    assert inject.kind == "Inject" and inject.brief.startswith("### Brick `x`")
    assert inject.payload.get("pipeline") == "Formalizer"
    assert "step_index" not in inject.payload, \
        "framework-stamped batch bookkeeping is not author input"
    assert "batch_size" not in inject.payload


def _rev_db(tmp_path, *, batch_id, decisions=()):
    p = tmp_path / "source.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE programme_revisions (id INTEGER PRIMARY KEY,"
              " problem TEXT, body TEXT, batch_id TEXT, dialogue TEXT)")
    c.execute("CREATE TABLE strategist_decisions (id INTEGER PRIMARY KEY,"
              " decision_kind TEXT, target_id INT, brief TEXT, reason TEXT,"
              " payload TEXT, batch_id TEXT)")
    c.execute("INSERT INTO programme_revisions VALUES (1362, 'p', 'BODY',"
              " ?, '[]')", (batch_id,))
    for d in decisions:
        c.execute("INSERT INTO strategist_decisions (decision_kind,"
                  " target_id, brief, reason, payload, batch_id)"
                  " VALUES (?,?,?,?,?,?)",
                  (d["decision_kind"], d.get("target_id"), d.get("brief"),
                   d.get("reason"), d.get("payload", "{}"), batch_id))
    c.commit()
    c.close()
    return p


def test_a_rejected_revision_replays_with_an_empty_decisions_projection(
        tmp_path):
    """A proposal rebutted to exhaustion never files a batch, so its
    `batch_id` is NULL — and the loader used to exit on it. That is
    backwards: the rejected family is exactly the one a rubric change
    most needs re-judged, and 66 of the live DB's rows are in it.

    The decisions are not in the DB and not recoverable from it: the
    `dialogue` column carries rounds of (proposal, criticisms, verdict)
    and nothing else, and reading them out of the proposal's PROSE would
    be the free-text detection the framework forbids. So the row loads
    with an empty projection and SAYS SO; the arm's `decisions:` file is
    the supported way to hand in ones recovered from a transcript."""
    p = driver_mod.load_proposal(_rev_db(tmp_path, batch_id=None), 1362)
    assert p["problem"] == "p" and p["body"] == "BODY"
    assert p["decisions"] == [] and p["batch_id"] is None
    assert "no decisions" in p["note"].lower() or "never" in p["note"].lower()


def test_a_committed_revision_still_carries_its_filed_decisions(tmp_path):
    src = _rev_db(tmp_path, batch_id="b1",
                  decisions=[{"decision_kind": "Inject",
                              "brief": "### Brick `x`"}])
    p = driver_mod.load_proposal(src, 1362)
    assert p["batch_id"] == "b1"
    assert [d["kind"] for d in p["decisions"]] == ["Inject"]
    assert p["note"] == ""


# ---------------------------------------------------------------------
# the daemon driver's stop conditions
# ---------------------------------------------------------------------

def _daemon_db(tmp_path) -> sqlite3.Connection:
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES ('Erdos', ?)", (BEFORE,))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES (?, ?, 'Erdos', 1)",
                 (PROBLEM, BEFORE))
    gid = groups_mod.ensure_top_group(conn, PROBLEM, charter="c")
    for slug in ("a", "b"):
        g = db.insert_goal(conn, problem=PROBLEM, slug=slug,
                           lean_path=f"Problems/Erdos/p1/proofs/L_{slug}.lean",
                           statement="True", origin="forward")
        db.update_goal_status(conn, g, "proved")
    conn.execute("INSERT INTO programme_revisions (problem, rev, body,"
                 " status, group_id, created_at) VALUES (?,1,'r','passed',"
                 " ?, ?)", (PROBLEM, gid, BEFORE))
    conn.commit()
    return conn


def test_a_daemon_arms_stop_condition_counts_what_the_run_produced(tmp_path):
    """The slice arrives with the problem's whole history in it — two
    proved goals here, thirty-five on a real one. An absolute threshold
    would be satisfied before the daemon started and stop the run on its
    first poll, having measured nothing."""
    conn = _daemon_db(tmp_path)
    try:
        base = driver_mod.baseline_counts(conn, PROBLEM)
        assert base == {"proved": 2, "revisions": 1}
        assert driver_mod.stop_reached(conn, PROBLEM, {"proved": 1},
                                       baseline=base, elapsed=0) is None
        g = db.insert_goal(conn, problem=PROBLEM, slug="c",
                           lean_path="Problems/Erdos/p1/proofs/L_c.lean",
                           statement="True", origin="forward")
        db.update_goal_status(conn, g, "proved")
        conn.commit()
        assert driver_mod.stop_reached(conn, PROBLEM, {"proved": 1},
                                       baseline=base, elapsed=0) == "proved+1"
    finally:
        conn.close()


def test_a_daemon_arm_stops_on_wall_clock_too(tmp_path):
    conn = _daemon_db(tmp_path)
    try:
        base = driver_mod.baseline_counts(conn, PROBLEM)
        assert driver_mod.stop_reached(conn, PROBLEM, {"wall_sec": 60},
                                       baseline=base, elapsed=59) is None
        assert driver_mod.stop_reached(conn, PROBLEM, {"wall_sec": 60},
                                       baseline=base,
                                       elapsed=61) == "wall_sec>=60"
        assert driver_mod.stop_reached(conn, PROBLEM, {}, baseline=base,
                                       elapsed=1e9) is None, \
            "no condition means the daemon's own --once decides"
    finally:
        conn.close()


def test_a_lab_daemon_never_binds_the_live_workspaces_gateway_port():
    """Two gateways on one port is one gateway serving two boards' Lean,
    and the loser dies at boot. The lab picks a free one per run."""
    a, b = driver_mod.free_port(), driver_mod.free_port()
    assert a != 8765 and b != 8765
    assert 1024 < a < 65536


# ---------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------

def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "live"
    (ws / "Problems").mkdir(parents=True)
    conn = db.connect(ws / "asterism.db")
    db.init_schema(conn)
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES ('Erdos', ?)", (BEFORE,))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES (?, ?, 'Erdos', 1)",
                 (PROBLEM, BEFORE))
    groups_mod.ensure_top_group(conn, PROBLEM, charter="c")
    pdir = db.problem_dir(ws, PROBLEM)
    (pdir / "proofs").mkdir(parents=True)
    db.insert_goal(conn, problem=PROBLEM, slug="main",
                   lean_path=(pdir / "Root.lean").relative_to(ws).as_posix(),
                   statement="True", origin="root", status="open")
    (pdir / "Root.lean").write_text("theorem main : True := trivial\n",
                                    encoding="utf-8")
    conn.commit()
    conn.close()
    return ws


@pytest.fixture(scope="module")
def head() -> str:
    out = subprocess.run(["git", "-C", str(lab.REPO), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


@pytest.fixture(scope="module")
def base(tmp_path_factory, head) -> Path:
    return build_mod.ensure_base(tmp_path_factory.mktemp("labroot"), head)


def _exp(root: Path, slice_id: str, *, kind: str = "judge_round",
         arm_body: str = "") -> spec_mod.Experiment:
    d = lab.docs_dir(root, "e1")
    d.mkdir(parents=True, exist_ok=True)
    body = {"judge_round": "    group: 1\n    rows: [1]\n"}.get(kind, "")
    (d / "lab.yaml").write_text(
        f"snapshot: {slice_id}\narms:\n  a:\n    kind: {kind}\n{body}"
        f"{arm_body}", encoding="utf-8")
    return spec_mod.load(root, "e1")


def _fake_driver(result: dict):
    """A launcher that writes what a real driver would, and nothing
    else — the record's assembly is what these tests are about, and a
    real spawn is minutes and a quota."""
    def launch(ws: Path, spec_path: Path):
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        out = Path(spec["out"])
        out.mkdir(parents=True, exist_ok=True)
        (out / driver_mod.RESULT_BASENAME).write_text(
            json.dumps(result), encoding="utf-8")
        return 0, 1.5
    return launch


def test_the_run_record_pins_the_slice_the_commit_and_the_prompts(
        tmp_path, base, head):
    """The workspace is gone by the time anyone reads this; the record
    is the only thing that can say what the run ran on."""
    root = tmp_path / "lab"
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id)
    result = {"outcome": "success", "usage": {"turns": 7,
                                              "output_tokens": 1234},
              "seats": {"adversary": {"provider": "codex",
                                      "model": "gpt-5"}},
              "artefacts": ["attempts/pid1"]}
    run_mod.run_once(root, exp, "a", slice_=sl, base=base, commit=head,
                     rep=1, launch=_fake_driver(result))
    rec = json.loads(
        (lab.runs_dir(root, "e1") / "a_r1" / "_out" / "run_record.json"
         ).read_text(encoding="utf-8"))
    assert rec["slice"] == sl.id and rec["code_commit"] == head
    assert rec["outcome"] == "success" and rec["rc"] == 0
    assert rec["usage"]["turns"] == 7
    assert rec["seats"]["adversary"]["model"] == "gpt-5"
    assert rec["artefacts"] == ["attempts/pid1"]
    assert rec["slice_manifest"]["problem"] == PROBLEM


def test_the_record_hashes_the_prompts_the_workspace_actually_held(
        tmp_path, base, head):
    """Not the arm's DECLARED overlay: the declaration says what was
    asked for, the hashes say what the seat read. Every "the arm ran the
    unedited prompt and looked like it worked" failure lives in the gap
    between those two."""
    root = tmp_path / "lab"
    d = lab.docs_dir(root, "e1")
    (d / "overlays").mkdir(parents=True)
    (d / "overlays" / "adv.md").write_text("judge harder\n",
                                           encoding="utf-8")
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id,
               arm_body="    prompts: {adversary/adversary.md: overlays/adv.md}\n")
    run_mod.run_once(root, exp, "a", slice_=sl, base=base, commit=head,
                     rep=1, launch=_fake_driver({"outcome": "success"}))
    rec = json.loads(
        (lab.runs_dir(root, "e1") / "a_r1" / "_out" / "run_record.json"
         ).read_text(encoding="utf-8"))
    import hashlib
    want = hashlib.sha256(
        (d / "overlays" / "adv.md").read_bytes()).hexdigest()
    assert rec["prompt_sha256"]["adversary/adversary.md"] == want
    assert len(rec["prompt_sha256"]) > 5, "every prompt, not just the overlay"
    assert rec["overlay"]["prompts"] == ["adversary/adversary.md"]


def test_the_workspace_is_deleted_and_the_experiment_is_not(
        tmp_path, base, head):
    """"Runs, then discarded; there is no restore" (lab_design.md §2).
    `_out/` and the record ARE the experiment; everything else in the
    directory is a copy of a slice and a copy of a commit."""
    root = tmp_path / "lab"
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id)
    ws = run_mod.run_once(root, exp, "a", slice_=sl, base=base, commit=head,
                          rep=1, launch=_fake_driver({"outcome": "success"}))
    assert sorted(p.name for p in ws.iterdir()) == ["_out", "run_record.json"]
    assert not (ws / "asterism.db").exists()
    assert not (ws / "Tooling").exists()


def test_keep_leaves_the_workspace_standing(tmp_path, base, head):
    root = tmp_path / "lab"
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id)
    ws = run_mod.run_once(root, exp, "a", slice_=sl, base=base, commit=head,
                          rep=1, keep=True,
                          launch=_fake_driver({"outcome": "success"}))
    assert (ws / "asterism.db").is_file() and (ws / "Tooling").is_dir()


def test_each_repetition_gets_its_own_workspace(tmp_path, base, head):
    root = tmp_path / "lab"
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id)
    dirs = run_mod.run_arm(root, exp, "a", workspace=live, reps=2,
                           launch=_fake_driver({"outcome": "success"}))
    assert [d.name for d in dirs] == ["a_r1", "a_r2"]
    for d in dirs:
        assert (d / "_out" / "run_record.json").is_file()


def test_transcripts_are_copied_out_before_the_workspace_goes(tmp_path,
                                                              monkeypatch):
    """codex keeps its rollout INSIDE the workspace, so it dies with it
    unless something copies it; claude keeps its jsonl in its own home
    under a name derived from the cwd, which a reader should not have to
    reconstruct a week later."""
    ws = tmp_path / "ws"
    (ws / ".asterism" / "codex_sessions" / "abc").mkdir(parents=True)
    (ws / ".asterism" / "codex_sessions" / "abc" / "rollout.jsonl"
     ).write_text("{}\n", encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    cdir = run_mod.claude_transcript_dir(ws)
    cdir.mkdir(parents=True)
    (cdir / "sess.jsonl").write_text("{}\n", encoding="utf-8")

    out = tmp_path / "out"
    kept = run_mod.collect_transcripts(ws, out)
    assert (out / "transcripts" / "codex" / "abc" / "rollout.jsonl").is_file()
    assert (out / "transcripts" / "claude" / "sess.jsonl").is_file()
    assert "transcripts/codex" in kept


def test_the_claude_transcript_directory_uses_the_clis_own_munge(tmp_path,
                                                                monkeypatch):
    """`D:\\Asterism` -> `D--Asterism`: every character that is not a
    letter or a digit becomes a dash. The rule is the claude CLI's, so
    it is spelled once."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    got = run_mod.claude_transcript_dir(Path("D:/Asterism"))
    assert got.name in ("D--Asterism", "D--Asterism-")
    assert got.parent == home / ".claude" / "projects"


# ---------------------------------------------------------------------
# gc
# ---------------------------------------------------------------------

def _finished_run(root: Path, exp: str, name: str) -> Path:
    d = lab.runs_dir(root, exp) / name
    (d / "_out").mkdir(parents=True)
    (d / "_out" / "run_record.json").write_text("{}", encoding="utf-8")
    (d / "run_record.json").write_text("{}", encoding="utf-8")
    (d / "Tooling").mkdir()
    (d / "asterism.db").write_text("x", encoding="utf-8")
    return d


def test_gc_clears_finished_workspaces_and_leaves_live_ones(tmp_path):
    root = tmp_path / "lab"
    done = _finished_run(root, "e1", "a_r1")
    live = lab.runs_dir(root, "e1") / "a_r2"
    (live / "Tooling").mkdir(parents=True)
    rep = run_mod.gc(root)
    assert "runs/e1/a_r1" in rep["cleared"]
    assert sorted(p.name for p in done.iterdir()) == ["_out",
                                                      "run_record.json"]
    assert (live / "Tooling").is_dir(), "a run with no record is still going"


def _slice_dir(root: Path, sid: str, taken: str) -> Path:
    d = lab.snapshots_dir(root) / sid
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(
        json.dumps({"problem": PROBLEM, "taken_utc": taken}),
        encoding="utf-8")
    return d


def test_gc_keeps_referenced_slices_and_the_newest_few(tmp_path):
    """A slice is what makes a run reproducible, so it goes only when
    nothing points at it AND it is not among the newest."""
    root = tmp_path / "lab"
    old = _slice_dir(root, "Erdos.p1_20260101-000000Z", "2026-01-01T00:00:00Z")
    cited = _slice_dir(root, "Erdos.p1_20260102-000000Z",
                       "2026-01-02T00:00:00Z")
    for n, day in ((3, "03"), (4, "04"), (5, "05")):
        _slice_dir(root, f"Erdos.p1_202601{day}-000000Z",
                   f"2026-01-{day}T00:00:00Z")
    d = lab.docs_dir(root, "e1")
    d.mkdir(parents=True)
    (d / "lab.yaml").write_text(
        f"snapshot: {cited.name}\narms:\n"
        f"  a: {{kind: judge_round, group: 1, rows: [1]}}\n",
        encoding="utf-8")
    rep = run_mod.gc(root, keep_latest=3)
    assert rep["dropped"] == [old.name]
    assert cited.is_dir(), "named by a lab.yaml"


def test_gc_drops_nothing_when_a_lab_yaml_will_not_parse(tmp_path):
    """gc never deletes on the strength of a file it failed to read: an
    unparseable lab.yaml may name every slice there is."""
    root = tmp_path / "lab"
    _slice_dir(root, "Erdos.p1_20260101-000000Z", "2026-01-01T00:00:00Z")
    _slice_dir(root, "Erdos.p1_20260102-000000Z", "2026-01-02T00:00:00Z")
    d = lab.docs_dir(root, "e1")
    d.mkdir(parents=True)
    (d / "lab.yaml").write_text("arms: {}\n", encoding="utf-8")
    rep = run_mod.gc(root, keep_latest=1)
    assert rep["dropped"] == []
