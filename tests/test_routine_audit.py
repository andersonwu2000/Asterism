"""The routine wake is an AUDIT (owner design 2026-08-30): it rules on
four criteria in `verdict.json` — per LINE for criteria 3 and 4, a
line being the root goal an Inject dispatched plus everything under it
— and makes no decisions. A fired finding is persistent state
(`routine_verdicts`) that seats an action wake (`routine_fired`); an
all-clear verdict ends the wake. The old routine audited its own notes
and Noop'd while a 596-node subtree grew for four days.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.state import groups as groups_store


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "a.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    c.commit()
    return c


def _goal(conn, slug, status="open", depth=0):
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"Problems/p/proofs/L_{slug}.lean",
                          statement=f"theorem {slug} : T", origin="backward",
                          depth=depth, status=status)


def _inject(conn, group_id, root_id, batch="b1", outcome=None,
            created_at=None):
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, group_id,"
        " produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Inject', ?, ?, ?, ?, ?, ?)",
        (batch, group_id, root_id, outcome,
         created_at or db.now(), db.now()))
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _tree(conn, root_id, kids):
    """One strategy under `root_id` with the given (slug, status) kids."""
    sid = db.insert_strategy(conn, goal_id=root_id,
                             lean_path="Problems/p/proofs/L_root.lean",
                             created_by="pipe")
    ids = []
    for i, (slug, status) in enumerate(kids):
        g = _goal(conn, slug, status=status, depth=1)
        db.link_subgoal(conn, strategy_id=sid, subgoal_id=g, position=i)
        ids.append(g)
    return sid, ids


# ------------------------------------------------------------ db helpers

def test_descendant_ids_walks_strategy_subgoals(conn):
    root = _goal(conn, "root")
    _sid, (a, b) = _tree(conn, root, [("a", "open"), ("b", "proved")])
    _sid2, (c,) = _tree(conn, a, [("c", "dead")])
    assert db.descendant_ids(conn, root) == {a, b, c}
    assert db.descendant_ids(conn, b) == set()


def test_in_flight_lines_report_each_root_with_its_tallies(conn):
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    root = _goal(conn, "root", status="attempting")
    _tree(conn, root, [("a", "proved"), ("b", "open"), ("c", "dead"),
                       ("d", "shelved")])
    did = _inject(conn, top, root, batch="abcdef0123",
                  created_at="2026-08-26T04:13:13+00:00")
    done_root = _goal(conn, "done", status="proved")
    _inject(conn, top, done_root, batch="finished", outcome="success")

    lines = audit.in_flight_lines(conn, "p", top)
    assert [ln["slug"] for ln in lines] == ["root"]
    ln = lines[0]
    assert ln["goal_id"] == root and ln["decision_id"] == did
    assert ln["batch_id"].startswith("abcdef01")
    assert ln["descendants"] == 4
    assert ln["tallies"] == {"proved": 1, "attempting": 0, "open": 1,
                             "dead": 1, "shelved": 1, "disproved": 0,
                             "pending_strategist_review": 0}
    assert ln["age_days"] >= 3


# ------------------------------------------------------------- verdict

SNAP = [{"goal_id": 1, "slug": "r1"}, {"goal_id": 2, "slug": "r2"}]


def _verdict(**over):
    v = {"criteria": {
        "1": ["clear: AHEAD 4 closes the MAIN claim — B's bound still stands"],
        "2": ["clear: the branch architecture is the only argued route"],
        "3": [{"goal_id": 1, "slug": "r1", "verdict": "fired",
               "reason": "Roadmap PAST retired it: no consumer"},
              {"goal_id": 2, "slug": "r2", "verdict": "clear",
               "reason": "AHEAD 2 consumes it"}],
        "4": [{"goal_id": 1, "slug": "r1", "verdict": "fired",
               "reason": "same-shape splits to depth five, zero proved"}]}}
    v["criteria"].update(over)
    return json.dumps(v)


def test_parse_verdict_finds_fired_lines_and_unaudited_roots():
    from Tooling.pipeline.strategist import audit
    v, err = audit.parse_verdict(_verdict(), SNAP)
    assert err == "", err
    assert [(f.criterion, f.goal_id) for f in v.fired] == [(3, 1), (4, 1)]
    assert v.fired[0].reason.startswith("Roadmap PAST")
    # r2 was never audited under criterion 4: not clear, not fired.
    assert v.unaudited == [(4, 2)]
    assert v.any_fired


def test_parse_verdict_rejects_a_bare_clear_and_a_missing_criterion():
    from Tooling.pipeline.strategist import audit
    _v, err = audit.parse_verdict(_verdict(**{"2": ["clear"]}), SNAP)
    assert "criterion 2" in err and "reason" in err
    bad = json.loads(_verdict())
    del bad["criteria"]["4"]
    _v, err = audit.parse_verdict(json.dumps(bad), SNAP)
    assert "criterion 4" in err


def test_parse_verdict_ignores_unknown_roots_and_keeps_the_first_duplicate():
    from Tooling.pipeline.strategist import audit
    v, err = audit.parse_verdict(_verdict(**{"3": [
        {"goal_id": 9, "slug": "ghost", "verdict": "fired", "reason": "x"},
        {"goal_id": 1, "slug": "r1", "verdict": "clear", "reason": "first"},
        {"goal_id": 1, "slug": "r1", "verdict": "fired", "reason": "second"},
        {"goal_id": 2, "slug": "r2", "verdict": "clear", "reason": "ok"}]}),
        SNAP)
    assert err == ""
    assert [(f.criterion, f.goal_id) for f in v.fired] == [(4, 1)]
    assert v.unknown == [(3, 9)] and v.duplicates == [(3, 1)]


def test_coverage_report_names_missing_duplicate_and_unknown_roots():
    from Tooling.pipeline.strategist import audit
    obj = json.loads(_verdict(**{"3": [
        {"goal_id": 9, "verdict": "clear", "reason": "x"},
        {"goal_id": 1, "verdict": "clear", "reason": "a"},
        {"goal_id": 1, "verdict": "clear", "reason": "b"}]}))
    notes = audit.coverage_report(obj, SNAP)
    joined = " | ".join(notes)
    assert "criterion 3" in joined and "r2" in joined      # missing
    assert "9" in joined                                    # unknown
    assert "r1" in joined and "twice" in joined             # duplicate
    assert "criterion 4" in joined and "r2" in joined


def test_recorded_fired_verdict_is_pending_until_acted(conn):
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    v, _ = audit.parse_verdict(_verdict(), SNAP)
    vid = audit.record_verdict(conn, problem="p", group_id=top,
                               pipeline_id="pipe-1", verdict=v,
                               raw=_verdict())
    row = audit.pending_fired_verdict(conn, top)
    assert row is not None and int(row["id"]) == vid
    assert json.loads(row["fired_json"])[0]["goal_id"] == 1
    audit.mark_acted(conn, vid)
    assert audit.pending_fired_verdict(conn, top) is None


def test_an_all_clear_verdict_is_recorded_but_never_pending(conn):
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    clear = _verdict(**{"3": [
        {"goal_id": 1, "verdict": "clear", "reason": "AHEAD 1"},
        {"goal_id": 2, "verdict": "clear", "reason": "AHEAD 2"}],
        "4": [{"goal_id": 1, "verdict": "clear", "reason": "fresh"},
              {"goal_id": 2, "verdict": "clear", "reason": "fresh"}]})
    v, _ = audit.parse_verdict(clear, SNAP)
    assert not v.any_fired
    audit.record_verdict(conn, problem="p", group_id=top,
                         pipeline_id="pipe-2", verdict=v, raw=clear)
    assert audit.pending_fired_verdict(conn, top) is None
    assert conn.execute("SELECT COUNT(*) FROM routine_verdicts").fetchone()[0] == 1


def test_trigger_kinds_carry_routine_fired_as_a_batch_done_like_wake():
    from Tooling.pipeline import strategist
    assert "routine_fired" in strategist.TRIGGER_KINDS
    assert "routine_fired" in strategist.BATCH_DONE_LIKE


# ------------------------------------------------- wiring: trigger, wake,
# context, verify, commit, validate_json

@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def wconn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    c.commit()
    return c


@pytest.fixture
def mfst():
    from Tooling.state import intent as intent_mod
    return intent_mod.ProblemIntent(problem="p", charter="T")


def _line_in_flight(conn, top, slug="root"):
    root = _goal(conn, slug, status="attempting")
    _tree(conn, root, [("kid_open", "open"), ("kid_dead", "dead")])
    _inject(conn, top, root, batch="live0001")
    return root


def _fired_verdict_text(root_id, slug="root"):
    return json.dumps({"criteria": {
        "1": ["clear: AHEAD 3 closes the MAIN claim — one bound stands"],
        "2": ["clear: the route is the only argued one"],
        "3": [{"goal_id": root_id, "slug": slug, "verdict": "fired",
               "reason": "Roadmap PAST retired it: no consumer"}],
        "4": [{"goal_id": root_id, "slug": slug, "verdict": "clear",
               "reason": "first dispatch, no failures yet"}]}})


def test_choose_trigger_seats_routine_fired_for_a_pending_verdict(wconn):
    from Tooling.core.dispatcher import triggers
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    v, _ = audit.parse_verdict(_fired_verdict_text(root),
                               [{"goal_id": root, "slug": "root"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    trig, _pending = triggers._derive_strategist_trigger(
        wconn, "p", group_id=top, routine_interval_min=0)
    assert trig == "routine_fired"


def test_strategist_triggers_seat_a_group_with_a_pending_fired_verdict(wconn):
    from Tooling.core.dispatcher import triggers
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    v, _ = audit.parse_verdict(_fired_verdict_text(root),
                               [{"goal_id": root, "slug": "root"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    triggers.strategist_triggers(wconn, running=set(), interval_min=0)
    assert db.is_in_queue(wconn, target_id=str(top), kind="Strategist")


def test_routine_wake_records_the_verdict_and_touches_only_the_routine_clock(
        wconn, workspace, mfst, monkeypatch):
    from Tooling import agent
    from Tooling.pipeline import strategist
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    seen: dict = {}

    def fake_spawn(**kw):
        snap = json.loads((kw["attempts_dir"] / audit.ROOTS_FILE)
                          .read_text(encoding="utf-8"))
        seen["snapshot"] = snap
        seen["prompt"] = kw["prompt_path"].name
        (kw["attempts_dir"] / audit.VERDICT_FILE).write_text(
            _fired_verdict_text(root), encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        wconn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, intent=mfst, pipeline_id="pipe-r1",
        group_id=top)
    assert r.outcome == "success", r
    assert seen["snapshot"] == [{"goal_id": root, "slug": "root"}]
    assert seen["prompt"] == "routine.md"
    row = audit.pending_fired_verdict(wconn, top)
    assert row is not None and row["pipeline_id"] == "pipe-r1"
    g = wconn.execute("SELECT last_routine_at, last_strategist_at FROM groups"
                      " WHERE id = ?", (top,)).fetchone()
    assert g["last_routine_at"] is not None
    assert g["last_strategist_at"] is None, (
        "an audit must not acknowledge Inject batches it never processed")
    p = wconn.execute("SELECT last_routine_at, last_strategist_at FROM problems"
                      " WHERE name = 'p'").fetchone()
    assert p["last_routine_at"] is not None and p["last_strategist_at"] is None
    assert wconn.execute("SELECT COUNT(*) FROM strategist_decisions"
                         " WHERE trigger_kind = 'routine'"
                         ).fetchone()[0] == 0, "an audit makes no decisions"


def test_routine_wake_gets_one_corrective_turn_for_a_missing_verdict(
        wconn, workspace, mfst, monkeypatch):
    from Tooling import agent
    from Tooling.pipeline import strategist
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    calls: list[bool] = []

    def fake_spawn(**kw):
        calls.append(bool(kw.get("is_retry")))
        if kw.get("is_retry"):
            (kw["attempts_dir"] / audit.VERDICT_FILE).write_text(
                _fired_verdict_text(root), encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        wconn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, intent=mfst, pipeline_id="pipe-r2",
        group_id=top)
    assert calls == [False, True] and r.outcome == "success"


def test_routine_context_has_the_lines_section_and_the_roots_snapshot(
        wconn, workspace, mfst, tmp_path):
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    adir = tmp_path / "attempts-r"
    adir.mkdir()
    path = compile_strategist_context(
        wconn, problem="p", trigger_kind="routine", attempts_dir=adir,
        workspace=workspace, intent=mfst, group_id=top)
    text = path.read_text(encoding="utf-8")
    assert "## Lines in flight" in text
    assert f"`root` (goal_id {root}" in text and "dead 1" in text
    assert json.loads((adir / audit.ROOTS_FILE).read_text(
        encoding="utf-8")) == [{"goal_id": root, "slug": "root"}]


def test_action_wake_context_carries_the_fired_findings_verbatim(
        wconn, workspace, mfst, tmp_path):
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    v, _ = audit.parse_verdict(_fired_verdict_text(root),
                               [{"goal_id": root, "slug": "root"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    adir = tmp_path / "attempts-a"
    adir.mkdir()
    text = compile_strategist_context(
        wconn, problem="p", trigger_kind="routine_fired", attempts_dir=adir,
        workspace=workspace, intent=mfst, group_id=top,
    ).read_text(encoding="utf-8")
    assert "## Routine audit verdict" in text
    assert "Roadmap PAST retired it: no consumer" in text
    assert text.index("## Routine audit verdict") < text.index("## Programme")


def test_action_batch_must_act_on_every_fired_root(wconn, workspace):
    from Tooling.pipeline import strategist
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    v, _ = audit.parse_verdict(_fired_verdict_text(root),
                               [{"goal_id": root, "slug": "root"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    noop, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "Noop", "reason": "all fine"}]))
    err = strategist.verify_decisions(
        noop, wconn, problem="p", workspace=workspace,
        trigger_kind="routine_fired", group_id=top)
    assert "root" in err and "audit" in err.lower()
    shelve, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "ConfirmShelve", "target_goal_id": root,
          "reason": "Roadmap PAST: retired; restart when a band consumes it"},
         {"kind": "Inject", "proof": "Theorem. replacement_bound: the "
          "prerequisite the audit named.\n\nProof. Trivial."}]))
    err2 = strategist.verify_decisions(
        shelve, wconn, problem="p", workspace=workspace,
        trigger_kind="routine_fired", group_id=top)
    # 2026-08-30, experiment 1: this assertion used to read `"audit" not
    # in err2` and passed while the gate rejected EVERY correct batch in
    # the field (it read `d.target_goal_id`; the model's field is
    # `target_id`) — the rejection text contained "audit" only on the
    # code path the test never reached. A correct batch verifies clean.
    assert not err2, err2


def test_in_flight_lines_skip_roots_that_are_no_longer_in_flight(conn):
    """Experiment 1 (2026-08-30): the audit listed roots already
    `shelved` as lines in flight, the strategist dutifully fired on them,
    and the action wake was then required to ConfirmShelve goals that
    were shelved already. A root is in flight only while it is live."""
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    live = _line_in_flight(conn, top)
    parked = _goal(conn, "parked", status="shelved")
    _inject(conn, top, parked, batch="live0002")
    done = _goal(conn, "done", status="proved")
    _inject(conn, top, done, batch="live0003")
    conn.commit()
    ids = [ln["goal_id"] for ln in audit.in_flight_lines(conn, "p", top)]
    assert ids == [live]


def test_action_batch_is_not_asked_to_act_on_a_root_no_longer_live(wconn, workspace):
    """Belt and braces for the same class: a fired root that has since
    left the live set (shelved/proved/dead by another path) is not a
    line this batch can act on; only live fired roots are required."""
    from Tooling.pipeline import strategist
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    gone = _goal(wconn, "gone", status="attempting")
    _inject(wconn, top, gone, batch="live0002")
    text = json.dumps({"criteria": {
        "1": ["clear: ok"], "2": ["clear: ok"],
        "3": [{"goal_id": root, "slug": "root", "verdict": "fired", "reason": "no consumer"},
              {"goal_id": gone, "slug": "gone", "verdict": "fired", "reason": "no consumer"}],
        "4": [{"goal_id": root, "slug": "root", "verdict": "clear", "reason": "fresh"},
              {"goal_id": gone, "slug": "gone", "verdict": "clear", "reason": "fresh"}]}})
    v, _ = audit.parse_verdict(text, [{"goal_id": root, "slug": "root"},
                                      {"goal_id": gone, "slug": "gone"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    db.update_goal_status(wconn, gone, "shelved")
    wconn.commit()
    shelve, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "ConfirmShelve", "target_goal_id": root,
          "reason": "Roadmap PAST: retired; restart when a band consumes it"},
         {"kind": "Inject", "proof": "Theorem. replacement_bound.\n\n"
          "Proof. Trivial."}]))
    err = strategist.verify_decisions(
        shelve, wconn, problem="p", workspace=workspace,
        trigger_kind="routine_fired", group_id=top)
    assert not err, err


def test_action_wake_commit_marks_the_verdict_acted(wconn, workspace):
    from Tooling.pipeline import strategist
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(wconn, "p")
    root = _line_in_flight(wconn, top)
    v, _ = audit.parse_verdict(_fired_verdict_text(root),
                               [{"goal_id": root, "slug": "root"}])
    audit.record_verdict(wconn, problem="p", group_id=top,
                         pipeline_id="x", verdict=v, raw="{}")
    ds, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "ConfirmShelve", "target_goal_id": root,
          "reason": "Roadmap PAST: retired"}]))
    strategist.commit_decisions(ds, wconn, problem="p", tick=1,
                                trigger_kind="routine_fired",
                                workspace=workspace, group_id=top)
    assert audit.pending_fired_verdict(wconn, top) is None


def test_validate_json_previews_audit_coverage(tmp_path, monkeypatch):
    from Tooling.knowledge import mcp_tools
    from Tooling.llm import spawn_guard
    from Tooling.pipeline.strategist import audit
    adir = tmp_path / "att"
    adir.mkdir()
    audit.write_roots_snapshot(adir, [
        {"goal_id": 1, "slug": "r1"}, {"goal_id": 2, "slug": "r2"}])
    (adir / "verdict.json").write_text(_fired_verdict_text(1, "r1"),
                                       encoding="utf-8")
    monkeypatch.setenv(spawn_guard.ATTEMPT_DIR_ENV, str(adir))
    out = mcp_tools.validate_json(file="verdict.json")
    assert "r2" in out and "not ruled on" in out
    assert "criterion 3" in out and "criterion 4" in out


def test_verdict_section_shows_only_fired_roots_still_live(conn):
    """The action wake's `## Routine audit verdict` lists the fired
    lines verbatim. A root that left the live set after the audit is not
    a line the batch can act on; showing it invites a ConfirmShelve on
    a goal already shelved (experiment 1, 2026-08-30). Roadmap-level
    findings (no goal) always show."""
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    live = _line_in_flight(conn, top)
    gone = _goal(conn, "gone", status="shelved")
    text = json.dumps({"criteria": {
        "1": ["fired: the Roadmap cannot reach MAIN"], "2": ["clear: ok"],
        "3": [{"goal_id": live, "slug": "root", "verdict": "fired", "reason": "no consumer"},
              {"goal_id": gone, "slug": "gone", "verdict": "fired", "reason": "no consumer"}],
        "4": [{"goal_id": live, "slug": "root", "verdict": "clear", "reason": "fresh"},
              {"goal_id": gone, "slug": "gone", "verdict": "clear", "reason": "fresh"}]}})
    v, _ = audit.parse_verdict(text, [{"goal_id": live, "slug": "root"},
                                      {"goal_id": gone, "slug": "gone"}])
    vid = audit.record_verdict(conn, problem="p", group_id=top,
                               pipeline_id="x", verdict=v, raw="{}")
    row = audit.pending_fired_verdict(conn, top)
    body = "\n".join(audit.render_verdict_section(row, conn))
    assert "`root` (goal_id" in body
    assert "`gone`" not in body
    assert "cannot reach MAIN" in body
