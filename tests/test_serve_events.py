"""GET /api/problems/{p}/events contract tests — the Timeline read.

The surface's whole claim is that every row reads `at | what happened |
to whom`, so the laws pinned here are about SHAPE (an event always
names an object, prose never becomes a label) and about TIMESTAMP
HONESTY (the engine's own log outranks reconstruction, and a reading
that had to fall back to `goals.updated_at` says so).

Fixtures go through the real writers — `db.update_goal_status` for a
logged transition, `failures.is_infra` for the infra split — because a
hand-written fixture is exactly how the adversary-verdict read drifted
away from its own contract for a week (2026-08-05).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)", ("p", db.now()))
    conn.commit()
    return conn


def _goal(conn: sqlite3.Connection, slug: str, *, origin: str = "forward",
          status: str = "open") -> int:
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"proofs/{slug}.lean",
                          statement="True", origin=origin, status=status)


def _decide(conn: sqlite3.Connection, kind: str, *, brief: str = "",
            reason: str = "", target: "int | None" = None,
            produced: "int | None" = None,
            outcome: "str | None" = None) -> int:
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " outcome, produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', ?, ?, ?, ?, '{}', ?, ?, ?, ?)",
        (kind, target, brief, reason, outcome, produced,
         db.now(), db.now()))
    conn.commit()
    return int(cur.lastrowid)


def _events(workspace: Path) -> dict:
    r = TestClient(create_app(workspace)).get("/api/problems/p/events")
    assert r.status_code == 200
    return r.json()


def test_unknown_problem_404(workspace: Path) -> None:
    _open_db(workspace).close()
    r = TestClient(create_app(workspace)).get("/api/problems/nope/events")
    assert r.status_code == 404


def test_every_event_names_an_object(workspace: Path) -> None:
    """The design rests on it: a row that names nothing cannot be
    followed, and following one object through the log is the reading
    the decision-only timeline could not do."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    _decide(conn, "Inject", brief="Roadmap: x\n\n## Need\nMint brick `b`.",
            produced=g, outcome="success")
    _decide(conn, "Ingest", reason="done")
    _decide(conn, "Noop", reason="nothing to do")
    db.update_goal_status(conn, g, "proved", event="builder_proved")
    conn.close()
    for e in _events(workspace)["events"]:
        assert e["label"], e
        assert e["kind"], e


def test_a_landing_is_an_event(workspace: Path) -> None:
    """The complaint that started the rewrite: 52 of 54 goals reached
    proved and not one of those landings appeared on the timeline."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    db.update_goal_status(conn, g, "proved", event="builder_proved")
    conn.close()
    ev = _events(workspace)["events"]
    landed = [e for e in ev if e["kind"] == "proved"]
    assert [(e["label"], e["goal_id"]) for e in landed] == [("brick_a", g)]


def test_engine_log_outranks_reconstruction(workspace: Path) -> None:
    """A goal the engine wrote down is never ALSO reconstructed: the
    landing appears once, at the logged instant, and claims to be
    exact."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    # a producing decision whose outcome write would date the landing
    _decide(conn, "Inject", produced=g, outcome="success")
    db.update_goal_status(conn, g, "proved", event="builder_proved")
    logged_at = conn.execute(
        "SELECT at FROM goal_events WHERE goal_id = ?", (g,)).fetchone()[0]
    conn.close()
    d = _events(workspace)
    landed = [e for e in d["events"] if e["kind"] == "proved"]
    assert len(landed) == 1
    assert landed[0]["at"] == logged_at
    assert landed[0]["approx"] is False
    # and the boundary the reader needs in order to trust the dates
    assert d["log_since"] == logged_at


def test_reconstruction_says_when_it_guessed(workspace: Path) -> None:
    """Pre-log history has no recorded instant. A landing dated from
    `goals.updated_at` — a column also bumped by attempts and
    deliverable writes — must be marked, not passed off as the
    engine's own word."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    # simulate pre-v36 history: state set, nothing logged, nothing that
    # produced it
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?", (g,))
    conn.commit()
    conn.close()
    d = _events(workspace)
    landed = [e for e in d["events"] if e["kind"] == "proved"]
    assert len(landed) == 1
    assert landed[0]["approx"] is True
    assert d["log_since"] is None  # no record at all → no boundary to draw


def test_reconstruction_prefers_the_work_that_produced_it(
        workspace: Path) -> None:
    """Between `goals.updated_at` and the succeeded pipeline that
    targeted the goal, the pipeline is the real instant."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?", (g,))
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('pid1', 'Formalizer', ?, 'Goal', 'succeeded', 'success',"
        " '2026-01-01T00:00:00+00:00', '2026-01-01T00:05:00+00:00')",
        (str(g),))
    conn.commit()
    conn.close()
    landed = [e for e in _events(workspace)["events"] if e["kind"] == "proved"]
    assert landed[0]["at"] == "2026-01-01T00:05:00+00:00"
    assert landed[0]["approx"] is False


def test_prose_never_becomes_a_label(workspace: Path) -> None:
    """A brief is 1.3KB of roadmap markdown. It rides along for the
    expansion; the row is identified by the brick."""
    brief = "Roadmap: lattice bridge\n\n## Need\nMint brick `brick_a`."
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    _decide(conn, "Inject", brief=brief, produced=g, outcome="success")
    conn.close()
    asked = [e for e in _events(workspace)["events"] if e["kind"] == "asked"]
    assert asked[0]["label"] == "brick_a"
    assert asked[0]["body"] == brief


def test_a_dispatch_whose_brick_does_not_exist_is_still_named(
        workspace: Path) -> None:
    """An Inject that failed or is still in flight has no goal row. The
    row must still say what was ASKED FOR, or the reader sees an
    anonymous event exactly where they most want a name."""
    conn = _open_db(workspace)
    _decide(conn, "Inject",
            brief="Roadmap: x\n\n## Need\nMint brick `never_built` in y.")
    conn.close()
    asked = [e for e in _events(workspace)["events"] if e["kind"] == "asked"]
    assert asked[0]["label"] == "never_built"
    assert asked[0]["object_kind"] == "unbuilt"
    assert asked[0]["goal_id"] is None


def test_a_dispatch_is_named_by_the_path_it_mints_into(
        workspace: Path) -> None:
    """The strategist's WORDING moves; the file convention does not.
    Batches now write "Mint into `proofs/L_x.lean`" with no "mint brick
    `x`" anywhere, and a prose-only reader labelled those rows with the
    problem's own name — anonymous exactly on the newest dispatches
    (owner, 2026-08-09)."""
    conn = _open_db(workspace)
    _decide(conn, "Inject",
            brief="Roadmap: the forced cores as bricks\n\n## Need\nThe "
                  "seven-set forced core as a single brick. Mint into "
                  "`proofs/L_uc_forced_seven_path_core.lean`.")
    conn.close()
    asked = [e for e in _events(workspace)["events"] if e["kind"] == "asked"]
    assert asked[0]["label"] == "uc_forced_seven_path_core"
    assert asked[0]["object_kind"] == "unbuilt"


def test_shelving_is_not_counted_twice(workspace: Path) -> None:
    """ConfirmShelve IS the shelving — the goal's state must not add a
    second row for the same fact."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    _decide(conn, "ConfirmShelve", target=g, reason="parked")
    conn.execute("UPDATE goals SET status = 'shelved' WHERE id = ?", (g,))
    conn.commit()
    conn.close()
    ev = _events(workspace)["events"]
    assert len([e for e in ev if e["kind"] == "shelved"]) == 1


def test_infra_deaths_are_split_from_real_failures(workspace: Path) -> None:
    """The failure registry's own semantics: an infra death never
    incremented `goals.attempts`, so numbering it would tell the reader
    the machine tried more times than it did. The fixture derives from
    `is_infra` rather than restating it."""
    from Tooling.state.failures import is_infra
    infra = next(r for r in ("spawn_fast_fail", "agent_declined")
                 if is_infra(r))
    real = next(r for r in ("lake_build_error", "agent_timeout")
                if not is_infra(r))
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    for pid in ("x", "y"):
        conn.execute(
            "INSERT INTO pipelines (id, kind, target_id, target_kind,"
            " status, outcome, started_at, finished_at)"
            " VALUES (?, 'Backward', ?, 'Goal', 'failed', 'failed', ?, ?)",
            (pid, str(g), db.now(), db.now()))
    conn.commit()
    db.record_dead_attempt(conn, target_id=g, target_kind="Goal",
                           pipeline_id="x", failure_reason=infra)
    db.record_dead_attempt(conn, target_id=g, target_kind="Goal",
                           pipeline_id="y", failure_reason=real)
    conn.close()
    ev = _events(workspace)["events"]
    assert [e["kind"] for e in ev if e["kind"] == "hiccup"] == ["hiccup"]
    assert [e["kind"] for e in ev if e["kind"] == "failed"] == ["failed"]
    # neither is numbered: an ordinal would claim to be the
    # engine's attempt sequence, and `goals.attempts` is a
    # different number that disagrees in both directions
    assert all(e["n"] is None for e in ev if e["kind"] in ("failed", "hiccup"))


def test_a_goal_nobody_dispatched_still_has_a_birthday(
        workspace: Path) -> None:
    """A decomposition cuts subgoals out of a parent; no decision names
    them, and they used to be absent from the timeline entirely."""
    conn = _open_db(workspace)
    g = _goal(conn, "sub_a", origin="backward")
    conn.close()
    ev = _events(workspace)["events"]
    assert [(e["kind"], e["label"], e["goal_id"]) for e in ev] == [
        ("opened", "sub_a", g)]


def test_a_revival_is_news_a_worker_picking_it_up_is_not(
        workspace: Path) -> None:
    """`goal_events` records every transition; the log shows the ones a
    reader would call events. attempting/open churn is the attempt rows'
    story, but a settled goal going back into play is a real change."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    db.update_goal_status(conn, g, "attempting", event="dispatch")
    db.update_goal_status(conn, g, "proved", event="builder_proved")
    db.update_goal_status(conn, g, "open", event="strategist_reopen")
    conn.close()
    kinds = [e["kind"] for e in _events(workspace)["events"]]
    assert "reopened" in kinds
    assert "proved" in kinds
    assert "attempting" not in kinds


def test_a_brick_carries_the_argument_it_serves(workspace: Path) -> None:
    """v35 — a problem under load argues several groups at once (7 on
    simple_loop_conjecture) and their bricks interleave in one stream.
    A commissioned brick inherits its decision's group; a subgoal
    nobody commissioned serves the same argument as the goal it was
    cut out of."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    top = _groups.ensure_top_group(conn, "p")
    sub_group = _groups.open_group(conn, problem="p", parent_group_id=top,
                                   charter="settle the sub-claim")
    brick = _goal(conn, "brick_a")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, brief, reason, payload,"
        " outcome, produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', ?, '', '', '{}',"
        " 'success', ?, ?, ?)", (sub_group, brick, db.now(), db.now()))
    # a decomposition cuts a subgoal out of that brick
    child = _goal(conn, "sub_a", origin="backward")
    sid = db.insert_strategy(conn, goal_id=brick,
                             lean_path="proofs/brick_a.lean",
                             scratch_path="", created_by="test")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=child, position=0)
    conn.commit()
    conn.close()
    d = _events(workspace)
    assert {g["id"] for g in d["groups"]} == {top, sub_group}
    by_label = {(e["label"], e["kind"]): e["group_id"] for e in d["events"]}
    assert by_label[("brick_a", "asked")] == sub_group
    assert by_label[("sub_a", "opened")] == sub_group


def test_a_revision_row_is_titled_by_the_revision(workspace: Path) -> None:
    """"programme" on every row said which surface it came from, not
    what changed. A revision names itself in its own `# Title`."""
    from Tooling.state import groups as _groups
    from Tooling.state import programme as prog
    conn = _open_db(workspace)
    top = _groups.ensure_top_group(conn, "p")
    prog.record_pass(conn, "p", "# Park the open core; mint the engine\n\n"
                     "## Argument\nA.\n\n## Proof\nT.\n\n## Roadmap\nR.",
                     {"reservations": []}, [], 0, None, group_id=top)
    conn.commit()
    conn.close()
    revs = [e for e in _events(workspace)["events"] if e["kind"] == "rev"]
    assert len(revs) == 1
    assert revs[0]["label"] == "Park the open core; mint the engine"
    assert revs[0]["n"] == 1


def test_newest_first_and_a_brick_is_asked_for_before_it_lands(
        workspace: Path) -> None:
    """Mint and landing inside one clock minute must not read as a
    proof that preceded its own dispatch."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    at = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, reason, payload, outcome,"
        " produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', '', '', '{}', 'success',"
        " ?, ?, ?)", (g, at, at))
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?", (g,))
    conn.execute("UPDATE goals SET updated_at = ? WHERE id = ?", (at, g))
    conn.commit()
    conn.close()
    ev = _events(workspace)["events"]
    assert [e["at"] for e in ev] == sorted((e["at"] for e in ev), reverse=True)
    assert [e["kind"] for e in ev].index("proved") < \
        [e["kind"] for e in ev].index("asked")


def test_a_decided_shelve_is_one_event_not_two(workspace: Path) -> None:
    """A decision whose EXECUTION is a status write lands in both
    records: the strategist's ConfirmShelve AND the goal's logged
    transition. Same act — the owner saw it as duplicated rows
    (2026-08-12). The decision survives because it carries WHY.

    Measured on union_closed: 8 pairs, every delta under 0.1s, because
    the status write rides the decision.
    """
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    _decide(conn, "ConfirmShelve", target=g, reason="one route, exhausted")
    db.update_goal_status(conn, g, "shelved", event="set_terminal")
    conn.close()
    shelved = [e for e in _events(workspace)["events"]
               if e["kind"] == "shelved"]
    assert len(shelved) == 1
    assert shelved[0]["note"] == "one route, exhausted"


def test_an_undecided_shelve_still_shows(workspace: Path) -> None:
    """The dedupe must not swallow a transition nobody decided — the
    engine shelves on its own when attempts run out, and that row is
    the only record of it."""
    conn = _open_db(workspace)
    g = _goal(conn, "brick_a")
    db.update_goal_status(conn, g, "shelved", event="attempts_exhausted")
    conn.close()
    ev = _events(workspace)["events"]
    assert len([e for e in ev if e["kind"] == "shelved"]) == 1


def test_a_dispatch_is_named_by_its_title_when_no_path_is_given(
        workspace: Path) -> None:
    """Third wording in the wild: a brief whose brick is named ONLY in
    its markdown title, with no `proofs/...` path and no "mint" phrase
    anywhere in 2974 bytes (decision #3137 on union_closed)."""
    conn = _open_db(workspace)
    _decide(conn, "Inject",
            brief="# `uc_residual_surplus_floor` - the residual split\n\n"
                  "## Need\nEvery count in this tree ends the same way.")
    conn.close()
    asked = [e for e in _events(workspace)["events"] if e["kind"] == "asked"]
    assert asked[0]["label"] == "uc_residual_surplus_floor"
    assert asked[0]["object_kind"] == "unbuilt"


def test_a_human_decision_says_who_decided(workspace: Path) -> None:
    """HID §3.2: `actor` is a semantic field, so the reading layer must
    carry it — a person's park rendered identically to the machine's
    invites the reader to answer it as a peer's opinion. The timeline
    event names the actor; the machine's rows keep saying 'strategist'."""
    conn = _open_db(workspace)
    gid = _goal(conn, "brick")
    mine = _decide(conn, "ConfirmShelve", target=gid, reason="stop",
                   outcome="success")
    conn.execute("UPDATE strategist_decisions SET actor = 'human',"
                 " trigger_kind = 'human' WHERE id = ?", (mine,))
    theirs = _decide(conn, "Noop", reason="thinking", outcome="success")
    conn.commit()
    conn.close()
    by_id = {e["id"]: e for e in _events(workspace)["events"]}
    assert by_id[f"d{mine}"]["actor"] == "human"
    assert by_id[f"d{theirs}"]["actor"] == "strategist"


# ---------------------------------------------------------------------
# The theory layer (v52, theory_wake_design.md) — outcomes are events
# too. A `Theorize` is dispatched work whose product is a DOCUMENT, and
# the Timeline is the surface that says what the machine did: a request
# nobody can see, answered by a document nobody can see, is a whole
# layer running off the record (owner, 2026-09-04).
# ---------------------------------------------------------------------

def _theorize(conn: sqlite3.Connection, workspace: Path, *,
              objective: str,
              situation: str = "two bricks landed, the third died") -> int:
    """A real `Theorize` through the real committer — the row's payload
    shape, its batch_id and its group stamp are all that writer's, so a
    fixture cannot drift from what the engine files."""
    from Tooling.pipeline.strategist.commit import commit_decision
    from Tooling.pipeline.strategist.model import Decision
    return commit_decision(
        Decision(kind="Theorize", reason="the counting wall",
                 payload={"objective": objective, "situation": situation}),
        conn, problem="p", tick=0, trigger_kind="routine",
        workspace=workspace).decision_row_id


def _theory_pipeline(conn: sqlite3.Connection, group_id: int, *,
                     pipeline_id: str = "tp1",
                     outcome: "str | None" = None) -> str:
    """A Theorist wake as the dispatcher records it: Group-targeted, the
    same shape a Strategist wake takes (worker.py, task_kind
    'Theorist')."""
    db.record_pipeline_start(conn, pipeline_id=pipeline_id,
                             kind="Theorist", target_id=str(int(group_id)),
                             target_kind="Group")
    if outcome is not None:
        db.finish_pipeline(
            conn, pipeline_id=pipeline_id,
            status="succeeded" if outcome == "success" else "failed",
            outcome=outcome)
    return pipeline_id


def _theory_doc(conn: sqlite3.Connection, *, group_id: int,
                decision_id: "int | None", objective: str,
                path: "str | None", status: str, rounds: int,
                pipeline_id: str = "tp1") -> int:
    from Tooling.pipeline.theorist import landing as _landing
    return _landing.record(
        conn, problem="p", group_id=group_id, pipeline_id=pipeline_id,
        decision_id=decision_id, objective=objective,
        situation="s", path=path, status=status, rounds=rounds,
        verdict_json=None)


def _top(conn: sqlite3.Connection) -> int:
    from Tooling.state import groups as _groups
    return _groups.ensure_top_group(conn, "p")


def test_a_theory_request_is_an_event(workspace: Path) -> None:
    """A `Theorize` filed nothing readable on the Timeline: the decision
    reader has a verb for every other kind, fell through to the engine's
    own token for this one, and labelled the row with the PROBLEM's name
    because a Theorize names no goal. The row must say what was asked,
    and name the question."""
    conn = _open_db(workspace)
    _theorize(conn, workspace, objective="Is the surplus floor forced?")
    conn.close()
    ev = _events(workspace)["events"]
    asked = [e for e in ev if e["kind"] == "asked_theory"]
    assert len(asked) == 1
    assert asked[0]["object_kind"] == "theory"
    assert asked[0]["label"] == "Is the surplus floor forced?"
    assert asked[0]["goal_id"] is None
    assert asked[0]["group_id"] is not None


def test_a_theory_request_is_named_by_its_objective_first_line(
        workspace: Path) -> None:
    """The objective is a request, not a title: the strategist prompt
    asks for a statement plus the wall around it, and the ones in the
    wild run to paragraphs. Same law as the Programme's title — the
    headline is the first line, capped, and the rest is expansion."""
    conn = _open_db(workspace)
    _theorize(conn, workspace,
              objective="A" * 400 + "\n\nthe second paragraph")
    conn.close()
    asked = [e for e in _events(workspace)["events"]
             if e["kind"] == "asked_theory"]
    assert asked[0]["label"] == "A" * 120


def test_the_theory_wake_starts_and_ends_on_the_record(
        workspace: Path) -> None:
    """Outcomes are events too, and that cuts both ways: a wake still
    running is why nothing else is happening in that group, and a wake
    that came back failed is why no document ever landed. Both instants
    are in `pipelines`; neither reached the log."""
    conn = _open_db(workspace)
    gid = _top(conn)
    _theorize(conn, workspace, objective="Is the surplus floor forced?")
    _theory_pipeline(conn, gid, outcome="success")
    row = conn.execute("SELECT started_at, finished_at FROM pipelines"
                       " WHERE id = 'tp1'").fetchone()
    started, finished = str(row["started_at"]), str(row["finished_at"])
    conn.close()
    by_kind = {e["kind"]: e for e in _events(workspace)["events"]}
    assert by_kind["theorizing"]["at"] == started
    assert by_kind["theorized"]["at"] == finished
    for k in ("theorizing", "theorized"):
        assert by_kind[k]["object_kind"] == "theory"
        assert by_kind[k]["label"] == "Is the surplus floor forced?"
        assert by_kind[k]["group_id"] == gid
    # the finish says WHAT came back — an infra death and a refused
    # review are the same row otherwise
    assert by_kind["theorized"]["note"] == "success"


def test_a_running_theory_wake_is_named_by_the_request_in_flight(
        workspace: Path) -> None:
    """The document does not exist yet, so the pipeline row cannot be
    joined to one. The `Theorize` on that group that precedes it is what
    it is answering (the framework allows one in flight per group), and
    an anonymous row is worst exactly where it is newest."""
    conn = _open_db(workspace)
    gid = _top(conn)
    _theorize(conn, workspace, objective="Is the surplus floor forced?")
    _theory_pipeline(conn, gid)
    conn.close()
    ev = _events(workspace)["events"]
    live = [e for e in ev if e["kind"] == "theorizing"]
    assert [e["label"] for e in live] == ["Is the surplus floor forced?"]
    # nothing finished, so nothing claims it did
    assert not [e for e in ev if e["kind"] == "theorized"]


def test_an_old_wake_is_named_by_the_request_it_answered(
        workspace: Path) -> None:
    """A group asks the theory layer more than once over its life. The
    wake that has no document row yet takes the request it can only be
    answering — the last one filed BEFORE it started — and never the
    newest, which would relabel every past wake on the group with
    today's question."""
    conn = _open_db(workspace)
    gid = _top(conn)
    first = _theorize(conn, workspace, objective="the first wall")
    _theory_pipeline(conn, gid, pipeline_id="tp_old")
    conn.execute("UPDATE strategist_decisions SET outcome = 'failed'"
                 " WHERE id = ?", (first,))
    conn.execute("UPDATE pipelines SET started_at = ?, status = 'failed'"
                 " WHERE id = 'tp_old'", ("2026-09-01T00:00:00+00:00",))
    conn.execute("UPDATE strategist_decisions SET created_at = ?"
                 " WHERE id = ?", ("2026-08-31T00:00:00+00:00", first))
    conn.commit()
    _theorize(conn, workspace, objective="the second wall")
    _theory_pipeline(conn, gid, pipeline_id="tp_new")
    conn.close()
    live = {e["id"]: e["label"] for e in _events(workspace)["events"]
            if e["kind"] == "theorizing"}
    assert live == {"tstp_old": "the first wall",
                    "tstp_new": "the second wall"}


def test_an_accepted_document_lands_with_its_path_and_its_cost(
        workspace: Path) -> None:
    """The one artifact the decision log had no table for. Accepted =
    the document is on the Project's shelf, and the row carries the path
    the reader opens plus what the review cost."""
    conn = _open_db(workspace)
    gid = _top(conn)
    did = _theorize(conn, workspace,
                    objective="Is the surplus floor forced?")
    rel = "Problems/P/_docs/agent/g1_20260904-1612_the_floor.md"
    _theory_doc(conn, group_id=gid, decision_id=did,
                objective="Is the surplus floor forced?", path=rel,
                status="accepted", rounds=2)
    conn.close()
    got = [e for e in _events(workspace)["events"] if e["kind"] == "theory"]
    assert len(got) == 1
    assert got[0]["object_kind"] == "theory"
    assert got[0]["label"] == "Is the surplus floor forced?"
    assert got[0]["path"] == rel
    assert got[0]["n"] == 2
    assert got[0]["group_id"] == gid


def test_a_refused_document_is_still_an_event_and_lands_nothing(
        workspace: Path) -> None:
    """A rejected run keeps its row: the request, the rounds and the
    refusal are what the NEXT request on that wall is written against.
    It landed no file, so it offers no path — absent, not a dead link."""
    conn = _open_db(workspace)
    gid = _top(conn)
    did = _theorize(conn, workspace, objective="the refused question")
    _theory_doc(conn, group_id=gid, decision_id=did,
                objective="the refused question", path=None,
                status="rejected", rounds=3)
    conn.close()
    ev = _events(workspace)["events"]
    refused = [e for e in ev if e["kind"] == "theory_refused"]
    assert len(refused) == 1
    assert refused[0]["label"] == "the refused question"
    assert refused[0]["n"] == 3
    assert refused[0]["path"] is None
    assert not [e for e in ev if e["kind"] == "theory"]


def test_a_wake_that_died_before_any_ruling_is_not_a_refusal(
        workspace: Path) -> None:
    """`theory_refused` says a reviewer read the document and refused
    it. A wake whose spawn died leaves no `theory_documents` row at all,
    and the log must say THAT — 2026-09-05, union_closed g691: two runs
    died in the codex stream and every surface called them refusals."""
    conn = _open_db(workspace)
    gid = _top(conn)
    _theorize(conn, workspace, objective="the question nobody ruled on")
    _theory_pipeline(conn, gid, outcome="failed")
    conn.close()
    ev = _events(workspace)["events"]
    died = [e for e in ev if e["kind"] == "theory_died"]
    assert len(died) == 1
    assert died[0]["object_kind"] == "theory"
    assert died[0]["label"] == "the question nobody ruled on"
    assert died[0]["group_id"] == gid
    assert not [e for e in ev if e["kind"] in ("theory", "theory_refused")]


def test_a_refused_wake_is_not_also_reported_as_dead(
        workspace: Path) -> None:
    """The sibling must not double-file: a run that reached a ruling has
    its answer row already."""
    conn = _open_db(workspace)
    gid = _top(conn)
    did = _theorize(conn, workspace, objective="the refused question")
    _theory_pipeline(conn, gid, outcome="failed")
    _theory_doc(conn, group_id=gid, decision_id=did,
                objective="the refused question", path=None,
                status="rejected", rounds=3)
    conn.close()
    ev = _events(workspace)["events"]
    assert len([e for e in ev if e["kind"] == "theory_refused"]) == 1
    assert not [e for e in ev if e["kind"] == "theory_died"]


def test_the_theory_rows_carry_the_batch_they_settle(
        workspace: Path) -> None:
    """A `Theorize` is an open batch step: the pipeline fills its
    outcome on both roads and the group is then woken by
    `maybe_enqueue_inject_batch_done`. The reader who wants to know why
    a batch closed needs the ANSWER's rows to name the same batch the
    request does — that relay is the whole reason the request is a batch
    step and not a fire-and-forget."""
    conn = _open_db(workspace)
    gid = _top(conn)
    did = _theorize(conn, workspace,
                    objective="Is the surplus floor forced?")
    _theory_pipeline(conn, gid, outcome="success")
    _theory_doc(conn, group_id=gid, decision_id=did,
                objective="Is the surplus floor forced?",
                path="Problems/P/_docs/agent/x.md", status="accepted",
                rounds=1)
    batch = conn.execute("SELECT batch_id FROM strategist_decisions"
                         " WHERE id = ?", (did,)).fetchone()[0]
    conn.close()
    assert batch
    theory = [e for e in _events(workspace)["events"]
              if e["object_kind"] == "theory"]
    assert {e["kind"] for e in theory} == {
        "asked_theory", "theorizing", "theorized", "theory"}
    assert {e["batch_id"] for e in theory} == {batch}


def test_the_theory_layer_reads_in_the_order_it_happened(
        workspace: Path) -> None:
    """Same law the bricks get: a request, its wake and its answer
    landing inside one clock second must not read as a document that
    preceded the question. Newest first, later-in-life first."""
    conn = _open_db(workspace)
    gid = _top(conn)
    did = _theorize(conn, workspace,
                    objective="Is the surplus floor forced?")
    _theory_pipeline(conn, gid, outcome="success")
    _theory_doc(conn, group_id=gid, decision_id=did,
                objective="Is the surplus floor forced?",
                path="Problems/P/_docs/agent/x.md", status="accepted",
                rounds=1)
    at = conn.execute("SELECT created_at FROM strategist_decisions"
                      " WHERE id = ?", (did,)).fetchone()[0]
    conn.execute("UPDATE strategist_decisions SET created_at = ?", (at,))
    conn.execute("UPDATE pipelines SET started_at = ?, finished_at = ?",
                 (at, at))
    conn.execute("UPDATE theory_documents SET created_at = ?", (at,))
    conn.commit()
    conn.close()
    kinds = [e["kind"] for e in _events(workspace)["events"]
             if e["object_kind"] == "theory"]
    assert kinds == ["theorized", "theory", "theorizing", "asked_theory"]
