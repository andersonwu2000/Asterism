"""`Tooling.experiments.replay_judge` — re-judge a historical proposal in
a rewound scratch workspace (experiment 3, 2026-08-30)."""
from __future__ import annotations

import json

from Tooling.experiments import replay_judge as rj
from Tooling.pipeline.strategist.model import parse_decisions


def test_reconstructed_decisions_parse_with_the_inject_prose_under_proof():
    """The DB keeps an Inject's prose in `brief`; the parser reads it
    from `proof`. A reconstruction that used the column name would hand
    the judge an Inject with no argument — and judge that."""
    rows = [
        {"decision_kind": "ConfirmShelve", "target_id": 9061, "brief": None,
         "reason": "parked", "payload": "{}"},
        {"decision_kind": "Inject", "target_id": None,
         "brief": "### Brick `x`\n\nMint exactly one theorem…", "reason": None,
         "payload": json.dumps({"pipeline": "Formalizer", "step_index": 0, "batch_size": 1})},
    ]
    objs = rj.reconstruct_decisions(rows)
    decisions, err = parse_decisions(json.dumps(objs))
    assert not err and decisions is not None
    shelve, inject = decisions
    assert shelve.kind == "ConfirmShelve" and shelve.target_id == 9061
    assert inject.kind == "Inject" and inject.brief.startswith("### Brick `x`")
    assert inject.payload.get("pipeline") == "Formalizer"
    assert "step_index" not in inject.payload and "batch_size" not in inject.payload, \
        "framework-stamped batch bookkeeping is not author input"


def _rev_db(tmp_path, *, batch_id, decisions=()):
    import sqlite3
    p = tmp_path / "src.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE programme_revisions (id INTEGER PRIMARY KEY,"
              " problem TEXT, body TEXT, batch_id TEXT, dialogue TEXT)")
    c.execute("CREATE TABLE strategist_decisions (id INTEGER PRIMARY KEY,"
              " decision_kind TEXT, target_id INT, brief TEXT, reason TEXT,"
              " payload TEXT, batch_id TEXT)")
    c.execute("INSERT INTO programme_revisions VALUES (1362, 'p', 'BODY',"
              " ?, '[]')", (batch_id,))
    for d in decisions:
        c.execute("INSERT INTO strategist_decisions (decision_kind, target_id,"
                  " brief, reason, payload, batch_id) VALUES (?,?,?,?,?,?)",
                  (d["decision_kind"], d.get("target_id"), d.get("brief"),
                   d.get("reason"), d.get("payload", "{}"), batch_id))
    c.commit(); c.close()
    return p


def test_a_rejected_revision_replays_with_an_empty_decisions_projection(tmp_path):
    """A proposal rebutted to exhaustion never files a batch, so its
    `programme_revisions.batch_id` is NULL — and `load_proposal` exited
    on it. That is backwards: the rejected family is exactly the one a
    rubric change most needs re-judged, and 66 of the live DB's rows are
    in it (row 1362, the 2026-09-04 replay's coverage-loss case, among
    them — its decisions had to be dug out of a codex rollout and
    injected through a seam cut into a private copy of this module,
    `criterion2_replay_2026-09-04.md` §五.4/§五.5).

    The decisions are not in the DB and not recoverable from it: the
    `dialogue` column carries rounds of (proposal, criticisms, verdict)
    and nothing else — checked across all 66 rows, two key shapes,
    neither with a decision in it. Reading them out of the proposal's
    PROSE would be the free-text detection the framework forbids. So
    the replay runs with an empty projection and SAYS SO."""
    src = _rev_db(tmp_path, batch_id=None)
    p = rj.load_proposal(src, 1362)
    assert p.problem == "p" and p.body == "BODY"
    assert p.decisions == []
    assert p.batch_id is None
    assert "no decisions" in p.note.lower() or "never" in p.note.lower(), p.note


def test_a_committed_revision_still_carries_its_filed_decisions(tmp_path):
    """The accepting path is unchanged: a revision with a batch_id
    replays against the decisions that batch filed, and says so."""
    src = _rev_db(tmp_path, batch_id="b1", decisions=[
        {"decision_kind": "Inject", "brief": "### Brick `x`"}])
    p = rj.load_proposal(src, 1362)
    assert p.batch_id == "b1"
    assert [d["kind"] for d in p.decisions] == ["Inject"]
    assert p.note == ""
