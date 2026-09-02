"""The human command queue (human_interface_design.md §3.3).

A person's command lands as a row in `human_commands`; the daemon
applies it on a tick through the SAME appliers the Strategist's own
decisions go through (`pipeline/strategist/commit.py`), producing an
ordinary `strategist_decisions` row with `actor='human'`.

New module rather than a section of an existing file: nothing else
tests `state/commands.py` — it is born here.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import commands, db, groups


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Problems" / "p").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES ('p', ?, 1)", (db.now(),))
    c.commit()
    return c


def _goal(conn: sqlite3.Connection, slug: str = "main",
          statement: str = "T", origin: str = "root") -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement=statement, origin=origin, depth=0)


def _q(conn: sqlite3.Connection, kind: str, payload: dict, *,
       key: str = "", expected_revision: "int | None" = None) -> int:
    return commands.enqueue(
        conn, problem="p", kind=kind, payload=payload,
        idempotency_key=key or f"k-{kind}-{len(payload)}",
        expected_revision=expected_revision)


# ---------------------------------------------------------------------
# the queue itself
# ---------------------------------------------------------------------

def test_enqueue_is_idempotent_on_the_key(conn: sqlite3.Connection) -> None:
    """The receipt is the row id, and a retried POST (a double-click, a
    dropped response) must return the SAME receipt — not a second
    command. §1.3: every command carries an idempotency key."""
    first = _q(conn, "MarkDeliverable", {"target_goal_id": 1}, key="abc")
    again = _q(conn, "MarkDeliverable", {"target_goal_id": 1}, key="abc")
    assert again == first
    assert conn.execute(
        "SELECT COUNT(*) FROM human_commands").fetchone()[0] == 1


def test_enqueue_validates_the_kind_and_the_problem(
        conn: sqlite3.Connection) -> None:
    """Two refusal types, the `state/projects.py` shape: ValueError = the
    request is malformed (422 upstream), KeyError = the named problem is
    not there (404)."""
    with pytest.raises(ValueError):
        _q(conn, "Ingest", {}, key="bad-kind")
    with pytest.raises(KeyError):
        commands.enqueue(conn, problem="ghost", kind="ConfirmShelve",
                         payload={}, idempotency_key="bad-problem")


def test_a_stale_expected_revision_is_rejected_not_applied(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """Optimistic concurrency (§1.3): the person acted on what the page
    showed. If the target moved between the read and the command, the
    command is refused rather than applied to a state nobody looked at."""
    gid = _goal(conn)
    cid = _q(conn, "ConfirmShelve", {"target_goal_id": gid,
                                     "reason": "parked by hand"},
             key="stale", expected_revision=7)
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert row["outcome"] == "stale"
    assert str(db.get_goal(conn, gid)["status"]) == "open"


def test_revision_counts_by_TARGET_KIND_not_by_bare_id(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§3.3 ruling 2026-09-02. `strategist_decisions.target_id` holds GOAL
    ids; `group_id` holds group ids; the two spaces are independent and
    both start at 1, so counting a group's revision as "rows whose
    target_id is that number" counts the decisions of an unrelated GOAL.

    Here goal 2 and group 2 are the same number and the goal carries
    three decisions: read by bare id, the group's revision reads 3, the
    person's page shows 3, and the ReturnToParent they send back is
    refused `stale` against a state nothing ever moved."""
    top = groups.ensure_top_group(conn, "p")
    g1 = _goal(conn)
    g2 = _goal(conn, "brick", "B", origin="forward")
    kid = groups.open_group(conn, problem="p", parent_group_id=top,
                            charter="the sub-charter")
    assert (g1, g2) == (top, kid), "the id collision this test is about"
    for _ in range(3):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, created_at,"
            " updated_at) VALUES ('p', 0, 'routine', 'Inject', ?, ?, ?)",
            (g2, db.now(), db.now()))
    conn.commit()

    assert commands.revision(
        conn, kind="ConfirmShelve", payload={"target_goal_id": g2}) == 3
    assert commands.revision(
        conn, kind="ReturnToParent", payload={"group_id": kid}) == 0

    cid = _q(conn, "ReturnToParent",
             {"group_id": kid, "reason": "hand it back"},
             key="rtp", expected_revision=0)
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "applied", row["outcome"]


# ---------------------------------------------------------------------
# what a person owes at POST (§3.3 ruling 2026-09-02)
# ---------------------------------------------------------------------

@pytest.mark.parametrize("kind,payload,word", [
    ("ConfirmShelve", {"target_goal_id": 1}, "reason"),
    ("ReturnToParent", {"group_id": 1}, "reason"),
    ("Inject", {"target_goal_id": 1}, "Proof"),
    ("Delegate", {}, "charter"),
    ("MarkDeliverable", {}, "target_goal_id"),
])
def test_enqueue_refuses_a_command_missing_its_own_field(
        conn: sqlite3.Connection, kind: str, payload: dict,
        word: str) -> None:
    """The refusal belongs at the POST, where a person is still looking at
    the screen. Left to apply, the same command comes back minutes later
    as a `rejected` row in a receipt nobody is watching — and §1.3's
    requirements are exactly the ones a form can check."""
    with pytest.raises(ValueError) as e:
        _q(conn, kind, payload, key=f"missing-{kind}")
    assert word in str(e.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM human_commands").fetchone()[0] == 0


def test_enqueue_accepts_the_minimal_valid_payloads(
        conn: sqlite3.Connection) -> None:
    """And the other half: the smallest payload §1.3 asks for is enough.
    A `Delegate` carrying a `target_goal_id` owes neither charter nor
    reason — the goal's own statement is the charter, and a person owes
    no justification for handing work down."""
    for kind, payload in (
            ("ConfirmShelve", {"target_goal_id": 1, "reason": "stop"}),
            ("ReturnToParent", {"group_id": 1, "reason": "exhausted"}),
            ("Inject", {"target_goal_id": 1,
                        "proof": "Theorem. T\nProof. p"}),
            ("Delegate", {"target_goal_id": 1}),
            ("Delegate", {"charter": "settle the claim"}),
            ("MarkDeliverable", {"target_goal_id": 1}),
    ):
        assert _q(conn, kind, payload, key=f"ok-{kind}-{len(payload)}")


# ---------------------------------------------------------------------
# the applier
# ---------------------------------------------------------------------

def test_every_kind_lands_as_a_human_decision_row(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The applier reuses `commit_decisions`, so a person's command is
    the same kind of row the machine writes — with `actor='human'` and
    `trigger_kind='human'`, the semantic fields §3.2 makes the
    predicates read."""
    top = groups.ensure_top_group(conn, "p")
    root = _goal(conn)
    shelve_me = _goal(conn, "brick", "B", origin="forward")
    mark_me = _goal(conn, "deliv", "D", origin="forward")
    kid = groups.open_group(conn, problem="p", parent_group_id=top,
                            charter="the sub-charter")
    ids = {
        "Inject": _q(conn, "Inject", {"target_goal_id": root,
                                      "proof": "Theorem. try again\nProof. as argued."},
                     key="k1"),
        "Delegate": _q(conn, "Delegate", {"target_goal_id": root},
                       key="k2"),
        "ConfirmShelve": _q(conn, "ConfirmShelve",
                            {"target_goal_id": shelve_me,
                             "reason": "a person stops this line"},
                            key="k3"),
        "MarkDeliverable": _q(conn, "MarkDeliverable",
                              {"target_goal_id": mark_me}, key="k4"),
        "ReturnToParent": _q(conn, "ReturnToParent",
                             {"group_id": kid, "flavour": "exhausted",
                              "reason": "hand it back"}, key="k5"),
    }
    commands.apply_pending(conn, workspace)
    for kind, cid in ids.items():
        row = commands.get(conn, cid)
        assert row["status"] == "applied", (kind, row["outcome"])
        assert row["decision_id"] is not None, kind
        assert row["applied_at"]
        d = conn.execute(
            "SELECT decision_kind, actor, trigger_kind FROM"
            " strategist_decisions WHERE id = ?",
            (row["decision_id"],)).fetchone()
        assert (str(d["decision_kind"]), str(d["actor"]),
                str(d["trigger_kind"])) == (kind, "human", "human")


def test_a_human_confirm_shelve_needs_no_paired_inject(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The pairing rule lives in `verify.verify_decisions` — the
    Strategist's gate, because the machine may never stop itself. The
    human path does not go through that verifier at all, so a solo
    ConfirmShelve lands, and it reads as a TERMINAL park (§1.3, §3.2)."""
    gid = _goal(conn, "brick", "B", origin="forward")
    cid = _q(conn, "ConfirmShelve",
             {"target_goal_id": gid, "reason": "not worth the tokens"},
             key="solo")
    commands.apply_pending(conn, workspace)
    assert commands.get(conn, cid)["status"] == "applied"
    assert str(db.get_goal(conn, gid)["status"]) == "shelved"
    assert db.is_confirm_shelve_parked(conn, gid) is True


def test_one_rows_failure_does_not_block_the_next(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The applier is a daemon tick's guest: a bad command must be a
    rejected row, never a wedged queue."""
    ok_goal = _goal(conn, "brick", "B", origin="forward")
    bad = _q(conn, "MarkDeliverable", {"target_goal_id": 9999}, key="bad")
    good = _q(conn, "ConfirmShelve",
              {"target_goal_id": ok_goal, "reason": "stop"}, key="good")
    commands.apply_pending(conn, workspace)
    assert commands.get(conn, bad)["status"] == "rejected"
    assert commands.get(conn, bad)["outcome"]
    assert commands.get(conn, good)["status"] == "applied"


def test_a_human_delegate_derives_its_charter_from_the_target(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§1.3: with a `target_goal_id` the person owes no charter. The
    applier needs one (it is the child group's fixed reference point),
    so it reads the goal's own statement."""
    gid = _goal(conn, "brick", "the statement to settle", origin="forward")
    cid = _q(conn, "Delegate", {"target_goal_id": gid}, key="deleg")
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "applied", row["outcome"]
    charter = conn.execute(
        "SELECT charter FROM groups WHERE opened_by = ?",
        (row["decision_id"],)).fetchone()["charter"]
    assert "the statement to settle" in str(charter)


def test_a_human_inject_queues_without_jumping_the_queue(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§1.3 (owner ruling 09-02): a node Inject only JOINS the queue —
    it does not outrank the goals BFS already queued, and it kills
    nothing in flight."""
    gid = _goal(conn)
    other = _goal(conn, "sibling", "S", origin="forward")
    db.enqueue(conn, kind="Formalizer", target_id=str(other),
               problem="p", priority=2)
    _q(conn, "Inject", {"target_goal_id": gid,
                        "proof": "Theorem. a person's hint\nProof. as argued."},
       key="inj")
    commands.apply_pending(conn, workspace)
    mine = conn.execute(
        "SELECT priority FROM queue WHERE target_id = ?",
        (str(gid),)).fetchone()
    assert int(mine["priority"]) <= 2
    # nothing was taken out from under the machine
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE target_id = ?",
        (str(other),)).fetchone()[0] == 1


def test_a_human_command_does_not_advance_the_wake_clocks(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """`commit_decisions` touches the Strategist's wake clocks once per
    batch — that is the MACHINE's cadence. A person's command is not a
    wake, and letting it restamp the clock would push the next routine
    out by up to a full interval."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _q(conn, "ConfirmShelve", {"target_goal_id": gid, "reason": "stop"},
       key="clock")
    commands.apply_pending(conn, workspace)
    p = conn.execute("SELECT last_strategist_at FROM problems"
                     " WHERE name = 'p'").fetchone()
    assert p["last_strategist_at"] is None


def test_a_crashed_apply_is_never_replayed(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The appliers commit as they go, so the row cannot be marked in
    the same transaction as its effects. The attempt is stamped BEFORE
    it runs: a queued row that already carries a stamp is a crash
    residue and is refused, never applied twice (a doubled Inject is two
    spawns; a doubled ConfirmShelve re-parks a revived goal)."""
    gid = _goal(conn, "brick", "B", origin="forward")
    cid = _q(conn, "ConfirmShelve", {"target_goal_id": gid, "reason": "s"},
             key="crash")
    conn.execute("UPDATE human_commands SET outcome = ? WHERE id = ?",
                 (commands.ATTEMPT_MARK, cid))
    conn.commit()
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert "interrupted" in str(row["outcome"])
    assert str(db.get_goal(conn, gid)["status"]) == "open"


def test_fetch_paper_is_refused_with_the_way_out(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The kind is in §3.3's CHECK list, but the Scholar pipeline it
    named was retired 2026-08-22 (`020ebf85`) and `_commit_one` has no
    handler — so the honest answer is a refusal that names the
    replacement, not an 'applied' row that dispatched nothing."""
    cid = _q(conn, "FetchPaper", {"query": "Erdos 1946"}, key="paper")
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert "retired" in str(row["outcome"])


def test_pending_is_oldest_first_and_get_returns_none_for_a_ghost(
        conn: sqlite3.Connection) -> None:
    a = _q(conn, "MarkDeliverable", {"target_goal_id": 1}, key="a")
    b = _q(conn, "MarkDeliverable", {"target_goal_id": 2}, key="b")
    assert [r["id"] for r in commands.pending(conn)] == [a, b]
    assert commands.get(conn, 9999) is None


def test_payload_round_trips_as_a_dict(conn: sqlite3.Connection) -> None:
    """The column is TEXT (JSON, the strategist's own decision fields);
    every reader here gets the parsed object, so no caller re-implements
    the decode."""
    cid = _q(conn, "ConfirmShelve", {"target_goal_id": 3, "reason": "x"},
             key="rt")
    assert commands.get(conn, cid)["payload"] == {
        "target_goal_id": 3, "reason": "x"}
    assert json.loads(conn.execute(
        "SELECT payload FROM human_commands WHERE id = ?",
        (cid,)).fetchone()["payload"])["reason"] == "x"


# ---------------------------------------------------------------------
# preview (§1.3: a cascading command pops a confirm window first)
# ---------------------------------------------------------------------

def _sub(conn: sqlite3.Connection, parent_goal: int, child_slug: str) -> int:
    """A sub-goal of `parent_goal` through a proposed strategy — the edge
    the shelve cascade walks."""
    sid = db.insert_strategy(
        conn, goal_id=parent_goal,
        lean_path=f"Problems/p/proofs/S_{child_slug}.lean",
        created_by="test")
    kid = _goal(conn, child_slug, "K", origin="backward")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=kid, position=0)
    conn.commit()
    return kid


def test_preview_names_every_goal_a_park_would_take(
        conn: sqlite3.Connection) -> None:
    """§1.3: a ConfirmShelve that cascades must pop a confirm window, and
    a window can only name what it is about to close. The set comes from
    the cascade's own walk, so preview and apply cannot disagree."""
    root = _goal(conn)
    kid = _sub(conn, root, "kid")
    grand = _sub(conn, kid, "grand")
    out = commands.preview(conn, problem="p", kind="ConfirmShelve",
                           payload={"target_goal_id": root})
    assert out["cascade"] is True
    assert [(a["id"], a["effect"]) for a in out["affected"]] == [
        (root, "shelved"), (kid, "shelved"), (grand, "shelved")]
    assert {a["kind"] for a in out["affected"]} == {"goal"}


def test_preview_does_not_move_anything(conn: sqlite3.Connection) -> None:
    """Read-only is the whole contract: the person has not decided yet."""
    root = _goal(conn)
    kid = _sub(conn, root, "kid")
    commands.preview(conn, problem="p", kind="ConfirmShelve",
                     payload={"target_goal_id": root})
    assert str(db.get_goal(conn, root)["status"]) == "open"
    assert str(db.get_goal(conn, kid)["status"]) == "open"


def test_preview_of_a_group_close_names_the_group_and_its_anchor(
        conn: sqlite3.Connection) -> None:
    """Closing a group is the other cascading verb: the group is handed
    back, its anchor is parked, and every group it opened is closed under
    it (`groups.set_status` cascades to descendants)."""
    top = groups.ensure_top_group(conn, "p")
    anchor = _goal(conn, "anchor", "A", origin="forward")
    kid = groups.open_group(conn, problem="p", parent_group_id=top,
                            charter="the sub-charter", anchor_goal_id=anchor)
    grand = groups.open_group(conn, problem="p", parent_group_id=kid,
                              charter="deeper still")
    out = commands.preview(conn, problem="p", kind="ReturnToParent",
                           payload={"group_id": kid})
    got = {(a["kind"], a["id"]): a["effect"] for a in out["affected"]}
    assert got[("group", kid)] == "returned"
    assert got[("group", grand)] == "closed"
    assert got[("goal", anchor)] == "shelved"
    assert out["cascade"] is True


def test_preview_of_a_non_cascading_kind_is_empty(
        conn: sqlite3.Connection) -> None:
    """`Inject` / `MarkDeliverable` / `Delegate` close nothing, so there
    is nothing for a confirm window to warn about."""
    gid = _goal(conn)
    out = commands.preview(conn, problem="p", kind="MarkDeliverable",
                           payload={"target_goal_id": gid})
    assert out == {"affected": [], "cascade": False,
                   "revision": out["revision"]}


# ---------------------------------------------------------------------
# the kill signal (§3.7) — the one command that reaches an OS process
# ---------------------------------------------------------------------

class _FakeSink:
    """The daemon's spawn registry, without a daemon. It records what it
    was asked to kill; the real one turns the same call into a kill of
    the process TREE recorded for that pipeline id."""

    def __init__(self, killed: int = 1, error: "Exception | None" = None):
        self.calls: "list[tuple[str, str]]" = []
        self._killed = killed
        self._error = error

    def deliver(self, pipeline_id: str, signal: str) -> int:
        self.calls.append((pipeline_id, signal))
        if self._error is not None:
            raise self._error
        return self._killed


def _running_formalizer(conn: sqlite3.Connection, goal_id: int,
                        pipeline_id: str = "pipe-1") -> str:
    db.record_pipeline_start(conn, pipeline_id=pipeline_id,
                             kind="Formalizer", target_id=str(goal_id),
                             target_kind="Goal")
    return pipeline_id


@pytest.mark.parametrize("payload,word", [
    ({"signal": "shelve"}, "pipeline_id"),
    ({"pipeline_id": "pipe-1"}, "signal"),
    ({"pipeline_id": "pipe-1", "signal": "explode"}, "signal"),
    ({"pipeline_id": "pipe-1", "signal": "return_to_parent"}, "reason"),
])
def test_enqueue_refuses_a_malformed_signal(
        conn: sqlite3.Connection, payload: dict, word: str) -> None:
    """§3.7's payload is `{pipeline_id, signal, reason}` and `reason` is
    owed for `return_to_parent` — closing a group from under a running
    worker retires every line beneath it, and the parent is owed the
    why. Refused at the POST like every other command's own fields."""
    with pytest.raises(ValueError) as e:
        _q(conn, "Signal", payload, key=f"bad-{word}-{len(payload)}")
    assert word in str(e.value)


def test_a_signal_needs_no_reason_unless_it_returns_to_the_parent(
        conn: sqlite3.Connection) -> None:
    for sig in ("shelve", "return_to_nl"):
        assert _q(conn, "Signal", {"pipeline_id": "pipe-1", "signal": sig},
                  key=f"ok-{sig}")


def test_signal_preview_names_the_worker_and_what_stopping_it_does(
        conn: sqlite3.Connection) -> None:
    """§1.3: a command that cascades pops a confirm window, and a window
    can only be honest if it names what it is about to kill. For a
    signal that is the pipeline itself — kind, target and how long it
    has been running, which is most of what tells a person whether they
    mean it — plus the effect the chosen signal will have."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _running_formalizer(conn, gid)
    out = commands.preview(conn, problem="p", kind="Signal",
                           payload={"pipeline_id": "pipe-1",
                                    "signal": "shelve"})
    assert out["pipeline"]["kind"] == "Formalizer"
    assert out["pipeline"]["target_id"] == str(gid)
    assert out["pipeline"]["started_at"]
    assert "park" in out["effect"].lower()
    assert [e["id"] for e in out["affected"]] == [gid]

    ghost = commands.preview(conn, problem="p", kind="Signal",
                             payload={"pipeline_id": "nope",
                                      "signal": "shelve"})
    assert ghost["pipeline"] is None


@pytest.mark.parametrize("kind,status,word", [
    ("Strategist", "running", "Strategist"),
    ("Formalizer", "succeeded", "succeeded"),
])
def test_a_signal_is_refused_unless_it_aims_at_a_running_formalizer(
        workspace: Path, conn: sqlite3.Connection, kind: str, status: str,
        word: str) -> None:
    """§3.7: only an in-flight Formalizer. The refusal NAMES the state it
    actually found — a person whose kill did nothing must not be left
    guessing which half of the sentence was wrong."""
    gid = _goal(conn, "brick", "B", origin="forward")
    db.record_pipeline_start(conn, pipeline_id="p9", kind=kind,
                             target_id=str(gid), target_kind="Goal")
    if status != "running":
        db.finish_pipeline(conn, pipeline_id="p9", status=status,
                           outcome="ok")
    sink = _FakeSink()
    cid = _q(conn, "Signal", {"pipeline_id": "p9", "signal": "shelve"},
             key=f"wrong-{kind}-{status}")
    commands.apply_pending(conn, workspace, signal_sink=sink)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert word in row["outcome"]
    assert sink.calls == [], "a refused signal must not reach a process"


def test_a_signal_against_a_pipeline_nobody_knows_is_refused(
        workspace: Path, conn: sqlite3.Connection) -> None:
    sink = _FakeSink()
    cid = _q(conn, "Signal", {"pipeline_id": "ghost", "signal": "shelve"},
             key="ghost")
    commands.apply_pending(conn, workspace, signal_sink=sink)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert "ghost" in row["outcome"]
    assert sink.calls == []


def test_a_signal_applied_without_a_registry_is_refused_not_faked(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """The registry belongs to the daemon that owns the spawn. An
    applier without one cannot kill anything, and an `applied` receipt
    for a worker still running would be the worst answer available."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _running_formalizer(conn, gid)
    cid = _q(conn, "Signal", {"pipeline_id": "pipe-1",
                              "signal": "return_to_nl"}, key="nosink")
    commands.apply_pending(conn, workspace)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert "registry" in row["outcome"]
    assert str(db.get_goal(conn, gid)["status"]) != "shelved"


def test_a_signal_that_cannot_be_delivered_files_no_decision(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """If the kill did not happen the park must not happen either: a
    parked goal whose worker is still writing into the workspace is the
    2026-08-15 failure with a human signature on it."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _running_formalizer(conn, gid)
    sink = _FakeSink(error=RuntimeError("no live spawn process registered"))
    cid = _q(conn, "Signal", {"pipeline_id": "pipe-1", "signal": "shelve"},
             key="undeliverable")
    commands.apply_pending(conn, workspace, signal_sink=sink)
    row = commands.get(conn, cid)
    assert row["status"] == "rejected"
    assert "no live spawn process registered" in row["outcome"]
    assert str(db.get_goal(conn, gid)["status"]) != "shelved"


def test_a_shelve_signal_kills_the_worker_and_parks_the_goal_as_a_human(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§3.7: `shelve` = a human park, and a human park is TERMINAL — the
    same `ConfirmShelve` the static command files, through the same
    applier, with `actor='human'`, so `is_confirm_shelve_parked` reads
    it as a decision rather than as a promise of a paired Inject."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _running_formalizer(conn, gid)
    sink = _FakeSink()
    cid = _q(conn, "Signal", {"pipeline_id": "pipe-1", "signal": "shelve",
                              "reason": "this line is a dead end"},
             key="sig-shelve")
    commands.apply_pending(conn, workspace, signal_sink=sink)

    row = commands.get(conn, cid)
    assert row["status"] == "applied", row["outcome"]
    assert sink.calls == [("pipe-1", "shelve")]
    assert str(db.get_goal(conn, gid)["status"]) == "shelved"
    assert db.is_confirm_shelve_parked(conn, gid) is True
    d = conn.execute(
        "SELECT decision_kind, actor FROM strategist_decisions WHERE id = ?",
        (row["decision_id"],)).fetchone()
    assert (str(d["decision_kind"]), str(d["actor"])) == ("ConfirmShelve",
                                                          "human")


def test_a_return_to_parent_signal_closes_the_group_with_the_reason(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§3.7: the group that owns the killed worker's goal returns to its
    parent — the existing group-return path, carrying the person's own
    reason."""
    top = groups.ensure_top_group(conn, "p")
    gid = _goal(conn, "brick", "B", origin="forward")
    # A group owns a goal by DERIVATION (`groups.group_for_goal`); the
    # anchor is the most specific of those edges.
    kid = groups.open_group(conn, problem="p", parent_group_id=top,
                            charter="the sub-charter", anchor_goal_id=gid)
    _running_formalizer(conn, gid)
    sink = _FakeSink()
    cid = _q(conn, "Signal",
             {"pipeline_id": "pipe-1", "signal": "return_to_parent",
              "reason": "the charter was wrong"}, key="sig-rtp")
    commands.apply_pending(conn, workspace, signal_sink=sink)

    row = commands.get(conn, cid)
    assert row["status"] == "applied", row["outcome"]
    d = conn.execute(
        "SELECT decision_kind, actor, group_id FROM strategist_decisions"
        " WHERE id = ?", (row["decision_id"],)).fetchone()
    assert (str(d["decision_kind"]), str(d["actor"]),
            int(d["group_id"])) == ("ReturnToParent", "human", kid)
    assert str(groups.get(conn, kid)["status"]) != groups.ACTIVE


def test_a_return_to_nl_signal_kills_and_files_no_decision(
        workspace: Path, conn: sqlite3.Connection) -> None:
    """§3.7: `return_to_nl` needs no decision row — the goal going back
    to the NL layer IS the killed pipeline's own cascade, and the
    existing outcome token says so. Nothing is re-dispatched by the
    signal itself."""
    gid = _goal(conn, "brick", "B", origin="forward")
    _running_formalizer(conn, gid)
    sink = _FakeSink()
    before = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions").fetchone()[0]
    cid = _q(conn, "Signal", {"pipeline_id": "pipe-1",
                              "signal": "return_to_nl"}, key="sig-nl")
    commands.apply_pending(conn, workspace, signal_sink=sink)

    row = commands.get(conn, cid)
    assert row["status"] == "applied", row["outcome"]
    assert sink.calls == [("pipe-1", "return_to_nl")]
    assert row["decision_id"] is None
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions").fetchone()[0] == before
    assert conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 0


def test_the_signal_cascade_map_reuses_the_frameworks_own_tokens() -> None:
    """The killed pipeline is finalised by the EXISTING completion path,
    so each signal names an outcome that path already understands.
    `return_to_nl` is the Formalizer's own decline token; the other two
    are settled by the decision the applier just filed, so their own
    cascade must decide nothing further — `moot` is the framework's word
    for exactly that."""
    from Tooling import pipeline as _pipeline
    assert commands.SIGNAL_CASCADE["return_to_nl"] == (
        "failed",
        _pipeline.DECLINE_TO_FAILURE_REASON[_pipeline.DECLINE_RETURN_TO_NL])
    assert commands.SIGNAL_CASCADE["shelve"][0] == "moot"
    assert commands.SIGNAL_CASCADE["return_to_parent"][0] == "moot"
    assert set(commands.SIGNAL_CASCADE) == set(commands.SIGNALS)


def test_a_killed_pipelines_ending_is_the_persons_signal_not_its_own(
        conn: sqlite3.Connection) -> None:
    """§3.7's dispatcher half. A killed worker reports whatever its death
    looked like from inside — a broken stream, a non-zero rc — and
    finalised on that the pipeline reads as an infra failure, with the
    person's decision nowhere in the record. So the armed signal is
    substituted: the row's own outcome says who stopped it, and the pair
    handed to the EXISTING cascade is `SIGNAL_CASCADE`'s."""
    db.record_pipeline_start(conn, pipeline_id="pipe-1", kind="Formalizer",
                             target_id="1", target_kind="Goal")

    class _Sink:
        def __init__(self):
            self.armed = {"pipe-1": "shelve"}

        def take(self, pid):
            return self.armed.pop(pid, None)

    sink = _Sink()
    assert commands.finalise_signalled(
        conn, sink, "pipe-1", "failed", "unclassified_spawn_failure") == (
        "moot", "")
    row = conn.execute(
        "SELECT status, outcome FROM pipelines WHERE id = 'pipe-1'"
    ).fetchone()
    assert (str(row["status"]), str(row["outcome"])) == ("failed",
                                                         "human_signal:shelve")
    # Spent: a signal decides exactly one ending.
    assert commands.finalise_signalled(
        conn, sink, "pipe-1", "failed", "agent_error") == ("failed",
                                                           "agent_error")


def test_an_unsignalled_pipeline_keeps_its_own_ending(
        conn: sqlite3.Connection) -> None:
    """All but a handful of completions. Nothing is rewritten and the
    `pipelines` row the worker already finalised is not touched again."""
    db.record_pipeline_start(conn, pipeline_id="pipe-2", kind="Formalizer",
                             target_id="1", target_kind="Goal")
    db.finish_pipeline(conn, pipeline_id="pipe-2", status="succeeded",
                       outcome="proved")

    class _Empty:
        def take(self, pid):
            return None

    assert commands.finalise_signalled(
        conn, _Empty(), "pipe-2", "succeeded", "") == ("succeeded", "")
    assert commands.finalise_signalled(
        conn, None, "pipe-2", "succeeded", "") == ("succeeded", "")
    assert str(conn.execute(
        "SELECT outcome FROM pipelines WHERE id = 'pipe-2'"
    ).fetchone()["outcome"]) == "proved"
