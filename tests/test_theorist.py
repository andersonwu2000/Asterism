"""The Theorist pipeline (theory_wake_design.md §3): author, review,
land — and what happens on every road that is not "accepted".

Mocked `spawn_llm`, everything else real: the Context is compiled from
a live DB, the projection is assembled on disk, the verdict goes
through the real parser and an accepted document lands through the real
`_docs` write fence.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent
from Tooling.pipeline import theorist
from Tooling.pipeline.strategist import commit as _commit
from Tooling.pipeline.theorist import landing, verdict as _verdict
from Tooling.state import db, groups as groups_mod, intent


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(
        json.dumps({"problem": "p", "charter": "Statement: T"}),
        encoding="utf-8")
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    groups_mod.ensure_top_group(c, "p", charter="T")
    c.commit()
    return c


@pytest.fixture
def pintent() -> intent.ProblemIntent:
    return intent.ProblemIntent(problem="p", charter="T")


_REPORT = ("# The unit-imbalance erasure\n\n"
           "## Abstract\n\nIt reduces MAIN to a smaller claim.\n\n"
           "## Theorems and proofs\n\nTheorem 1. ...\n\n"
           "## Load-bearing work\n\nThe wall is X.\n\n"
           "## Leads\n\nConjecture A, tested on n=4.\n")


def _clear(**over):
    base = {k: [f"clear: criterion {k} holds because ..."]
            for k in _verdict.CRITERIA_KEYS}
    base.update(over)
    return {"criteria": base, "reservations": []}


def _fired(key: str = "1", text: str = "the relation is not argued"):
    return _clear(**{key: [f"fired: {text}"]})


def _theorize(conn: sqlite3.Connection, workspace: Path, *,
              objective: str = "S such that S implies MAIN",
              situation: str = "the bridge died at PAST 3",
              actor: str = _commit.ACTOR_STRATEGIST) -> int:
    """File a real `Theorize` and hand back its decision row id."""
    from Tooling.pipeline.strategist import parse_decision
    d, err = parse_decision(json.dumps(
        {"kind": "Theorize", "objective": objective,
         "situation": situation}))
    assert err == "", err
    gid = groups_mod.ensure_top_group(conn, "p")
    out = _commit.commit_decisions(
        [d], conn, problem="p", tick=0, trigger_kind="routine",
        workspace=workspace, group_id=gid, actor=actor)[0]
    return int(out.decision_row_id)


def _script(*, verdicts, report=_REPORT):
    """A scripted `spawn_llm`: the author writes `report.md` every turn,
    the reviewer writes the next verdict in the list."""
    state = {"author": 0, "review": 0, "author_sids": [],
             "review_sids": [], "review_flags": [], "rebuttals": [],
             "seats": []}

    def fake_spawn(**kw):
        kind = kw.get("kind")
        state["seats"].append(kind)
        if kind == "theory_reviewer":
            state["review"] += 1
            state["review_sids"].append(kw.get("session_id"))
            state["review_flags"].append(dict(kw.get("prompt_flags") or {}))
            v = verdicts[min(state["review"] - 1, len(verdicts) - 1)]
            if v is not None:
                (kw["attempts_dir"] / "verdict.json").write_text(
                    json.dumps(v), encoding="utf-8")
            return 0
        state["author"] += 1
        state["author_sids"].append(kw.get("session_id"))
        state["rebuttals"].append(kw.get("retry_context"))
        body = report if isinstance(report, str) else report(state["author"])
        if body is not None:
            (kw["attempts_dir"] / "report.md").write_text(
                body, encoding="utf-8")
        return 0

    return fake_spawn, state


def _run(conn, workspace, pintent, decision_id, pipeline_id="th-1"):
    return theorist.run_theorist(
        conn, problem="p", workspace=workspace, intent=pintent,
        pipeline_id=pipeline_id,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        decision_id=decision_id)


# ---------------------------------------------------------------------
# the accepted road
# ---------------------------------------------------------------------

def test_an_accepted_document_lands_and_settles_its_request(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One author turn, one clear verdict: the document lands under the
    Project's shelf, `theory_documents` records it, and the Theorize row
    settles with the PATH — which is what the next wake reads."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert state["author"] == 1 and state["review"] == 1
    assert state["seats"] == ["theorist", "theory_reviewer"]

    row = conn.execute(
        "SELECT path, status, rounds, group_id, decision_id,"
        " objective, verdict_json FROM theory_documents").fetchone()
    assert row["status"] == "accepted" and row["rounds"] == 1
    assert row["decision_id"] == did
    assert row["objective"] == "S such that S implies MAIN"
    landed = workspace / row["path"]
    assert landed.is_file()
    text = landed.read_text(encoding="utf-8")
    # The provenance the attempts dir cannot keep: it is deleted at
    # pipeline end, so the reviewer's per-criterion sentence lives here.
    assert text.startswith('<!--\nstatus: accepted\n')
    assert "pipeline: th-1" in text and "rounds: 1" in text
    for k in _verdict.CRITERIA_KEYS:
        assert f"criterion {k}: clear:" in text
    assert "# The unit-imbalance erasure" in text
    assert "_docs/agent/" in row["path"]

    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert d["outcome"] == "success"
    assert d["outcome_detail"] == row["path"]


def test_the_landed_name_carries_group_minute_and_title(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`g<group>_<YYYYMMDD-HHMM>_<slug>.md`: the group and the minute
    make two documents on one wall tellable apart in a flat listing,
    the slug makes either of them findable."""
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    name = Path(conn.execute(
        "SELECT path FROM theory_documents").fetchone()[0]).name
    assert name.startswith(f"g{gid}_")
    assert name.endswith("_the_unit_imbalance_erasure.md")
    assert "rejected" not in name


def test_a_refused_documents_name_says_it_was_refused(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner addendum 2026-09-06: a document kept after the rounds were
    argued out must be tellable apart from an accepted one by its NAME.

    The two now sit in one flat directory, and every surface that offers
    a `_docs/agent/` file by path — a citation in a later document, a
    `grep` of the shelf, the reviewer's read-only grant — hands over the
    name before anything can read the header. `rejected` rides between
    the minute and the slug, so the group/minute ordering is untouched
    and the slug still ends the name."""
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_fired("1")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    name = Path(conn.execute(
        "SELECT path FROM theory_documents").fetchone()[0]).name
    assert name.startswith(f"g{gid}_")
    assert "_rejected_" in name
    assert name.endswith("_the_unit_imbalance_erasure.md")


def test_a_second_document_in_the_same_minute_does_not_overwrite_the_first(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The name is group + minute + slug, and none of the three is
    unique. Two wakes on one wall write the SAME title — the author is
    re-asked the same objective — so a second landing inside the same
    minute used to overwrite the first silently, and both rows then
    pointed at one file.

    That was survivable while only the accepted road landed (one
    document per wall, hours apart). It is not now: every run lands, and
    the record the 2026-09-06 ruling exists to keep is exactly the one
    that would be destroyed."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_fired("1")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did, pipeline_id="th-1")

    did2 = _theorize(conn, workspace)
    _run(conn, workspace, pintent, did2, pipeline_id="th-2")

    paths = [r[0] for r in conn.execute(
        "SELECT path FROM theory_documents ORDER BY id")]
    assert len(paths) == 2 and len(set(paths)) == 2, paths
    for p, pid in zip(paths, ("th-1", "th-2")):
        assert (workspace / p).is_file()
        assert f"pipeline: {pid}" in (workspace / p).read_text(
            encoding="utf-8")


def test_the_slug_falls_back_to_the_abstracts_first_sentence(
) -> None:
    """A document with no `# ` line is still findable: the Abstract's
    first sentence is where this structure puts the claim."""
    assert landing.slug_for("# A Title Here\n\nx") == "a_title_here"
    assert landing.slug_for(
        "## Abstract\n\nIt reduces MAIN to a smaller claim. And more.\n"
    ) == "it_reduces_main_to_a_smaller_claim"
    assert landing.slug_for("no headings at all") == "untitled"


# ---------------------------------------------------------------------
# the review loop
# ---------------------------------------------------------------------

def test_a_fired_verdict_buys_a_revision_on_the_same_session(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fired bullets go back VERBATIM, on a resume of the author's
    own session — the exact path the batch wake's rebuttal rides — and
    the reviewer is fresh every round."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("3", "the wall is only named"),
                                    _clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success"
    assert state["author"] == 2 and state["review"] == 2
    assert len(set(state["author_sids"])) == 1
    assert len(set(state["review_sids"])) == 2
    assert state["rebuttals"][0] is None
    assert "[criterion 3] the wall is only named" in state["rebuttals"][1]
    assert conn.execute(
        "SELECT rounds FROM theory_documents").fetchone()[0] == 2
    # the earlier round's objection reaches the reviewer as dialogue
    dialogue = (workspace / ".attempts" / "th-1" / "review" / "r2"
                / "dialogue.md")
    assert dialogue.is_file()
    assert "the wall is only named" in dialogue.read_text(encoding="utf-8")


def test_three_fired_rounds_reject_and_the_document_lands_as_the_record(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four author turns (one cold + three revisions), then the run is
    over — and the document LANDS anyway (owner ruling 2026-09-06).

    A refused document is post-mortem material: what was tried on this
    wall and why it failed is exactly what the next request is written
    against, and a record that lives only in a `dead_attempts` blob is
    a record nobody reads. It lands under the same shelf with the same
    name, marked `status: rejected` and carrying the LAST round's
    ruling verbatim — the fired lines under their criterion numbers,
    not only the clear ones."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("1"), _fired("1"),
                                    _fired("1"), _fired("1")])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "theory_rejected"
    assert state["author"] == 4 and state["review"] == 4

    row = conn.execute(
        "SELECT path, status, rounds, verdict_json FROM theory_documents"
    ).fetchone()
    assert row["status"] == "rejected" and row["rounds"] == 4
    assert "the relation is not argued" in row["verdict_json"]
    assert row["path"] and "_docs/agent/" in row["path"]
    landed = workspace / row["path"]
    assert landed.is_file()
    text = landed.read_text(encoding="utf-8")
    assert text.startswith('<!--\nstatus: rejected\n')
    assert "pipeline: th-1" in text and "rounds: 4" in text
    assert "criterion 1: fired: the relation is not argued" in text
    for k in ("2", "3", "4"):
        assert f"criterion {k}: clear:" in text
    # criterion 2 (Rigour) is clear here, so the reviewer re-derived the
    # theorems and the citability flag must NOT be raised.
    assert "rigour:" not in text
    assert "# The unit-imbalance erasure" in text

    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    # The one road REJECTED_DETAIL is for: a ruling was made and it
    # fired. Named on the enum too, so no consumer has to read prose.
    assert str(d["outcome"]) == "failed:theory_rejected"
    assert theorist.REJECTED_DETAIL in d["outcome_detail"]
    assert "the relation is not argued" in d["outcome_detail"]
    # …and the wake that reads this outcome can OPEN the document.
    assert row["path"] in d["outcome_detail"]
    assert "criterion 1" in d["outcome_detail"]


def test_a_rejection_on_rigour_flags_the_document_as_uncitable(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Citability follows criterion 2 (Rigour), not the status.

    A document refused on 1/3/4 with criterion 2 clear has had its
    theorems re-derived by the reviewer and may be cited as results —
    the previous test pins that road. This is the other one: criterion
    2 fired, so nothing in the document is established, and the header
    and the outcome both have to say so where a citing agent reads
    them."""
    did = _theorize(conn, workspace)
    bad = _fired("2", "Lemma 3's induction step is asserted, not proved")
    fake, _ = _script(verdicts=[bad, bad, bad, bad])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.failure_reason == "theory_rejected"
    row = conn.execute(
        "SELECT path, status FROM theory_documents").fetchone()
    text = (workspace / row["path"]).read_text(encoding="utf-8")
    assert "rigour: defective — see criterion 2" in text
    assert ("criterion 2: fired: Lemma 3's induction step is asserted,"
            " not proved") in text
    detail = conn.execute(
        "SELECT outcome_detail FROM strategist_decisions WHERE id = ?",
        (did,)).fetchone()[0]
    assert "rigour: defective — see criterion 2" in detail


def test_a_settled_request_wakes_the_group(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of settling the row: the batch closes, so the
    group is woken with the answer instead of waiting on a request that
    already finished."""
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    assert not db.is_in_queue(conn, target_id=str(gid), kind="Strategist")
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    assert db.is_in_queue(conn, target_id=str(gid), kind="Strategist")


# ---------------------------------------------------------------------
# a spawn that died is not a review that refused
# ---------------------------------------------------------------------

def _dead_spawn(seat: str, *, rc: int = 1, report: "str | None" = None):
    """A scripted `spawn_llm` where `seat` exits `rc`. The author writes
    `report` first when one is given; every other seat behaves."""
    state = {"author": 0, "review": 0}

    def fake_spawn(**kw):
        kind = kw.get("kind")
        if kind == "theory_reviewer":
            state["review"] += 1
            if seat == kind:
                return rc
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(_clear()), encoding="utf-8")
            return 0
        state["author"] += 1
        if report is not None:
            (kw["attempts_dir"] / "report.md").write_text(
                report, encoding="utf-8")
        return rc if seat == kind else 0

    return fake_spawn, state


def test_a_dead_author_spawn_is_not_reported_as_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-09-05, union_closed g691 twice: the codex stream died on the
    author's idle timeout and the Strategist was told its request "did
    not pass review — reconsider your request". Nothing was reviewed.
    A transport death must name the reachable action instead, and the
    decision's own `outcome` must say which road it was, so a reader
    does not have to parse prose to tell them apart.

    The re-issues are spent first (owner ruling 2026-09-06): the
    framework re-queues an infra death itself, so this message is the
    LAST word, not the first one."""
    did = _theorize(conn, workspace)
    _spend_infra_budget(conn, did)
    fake, state = _dead_spawn("theorist")
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert state["review"] == 0       # nothing was reviewed
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert "did not complete" in d["outcome_detail"]
    assert "re-issue" in d["outcome_detail"]
    # structural, not textual: `failed:<reason>`, the vocabulary
    # `failed:dead` / `failed:stalled` / `failed:group_retired` use.
    assert str(d["outcome"]) == f"failed:{r.failure_reason}"


def test_a_dead_reviewer_spawn_is_not_reported_as_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reviewer's transport can die on the same wall as the
    author's, and its rc says nothing about the document either. Its own
    re-spawn budget and the request's re-issues are both spent first —
    what is under test here is the LAST word."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    _spend_infra_budget(conn, did)
    fake, _ = _dead_spawn("theory_reviewer", report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert "did not complete" in d["outcome_detail"]
    assert str(d["outcome"]) == f"failed:{r.failure_reason}"


def test_an_author_that_writes_nothing_is_a_dead_wake_not_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No document was ever put to the reviewer, so no reviewer refused
    it — the same road, reached without an rc."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()], report=lambda _n: None)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert str(d["outcome"]) == "failed:theory_no_report"


_NET_STDERR = ("rc=1\nReconnecting... 5/5\nstream disconnected before "
               "completion: idle timeout waiting for websocket\n")


def _dies_with_stderr(seat: str, stderr: str):
    """`seat` exits 1 having left `stderr` where the provider writes it."""
    def fake_spawn(**kw):
        kind = kw.get("kind")
        if kind != seat:
            if kind == "theory_reviewer":
                (kw["attempts_dir"] / "verdict.json").write_text(
                    json.dumps(_clear()), encoding="utf-8")
            else:
                (kw["attempts_dir"] / "report.md").write_text(
                    _REPORT, encoding="utf-8")
            return 0
        (kw["attempts_dir"] / "_spawn.stderr").write_text(
            stderr, encoding="utf-8")
        return 1

    return fake_spawn


def test_a_theory_seats_transport_death_is_named_from_its_stderr(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rc is not the evidence — the stderr is. Every other pipeline
    reads it (`pipeline._spawn_failure`: transport prose outranks the rc
    and the duration heuristics), and the theory layer had its own rc-
    only classifier. The cost is not cosmetic: `provider_network` makes
    the dispatcher probe connectivity and PARK, while
    `unclassified_spawn_failure` feeds the consecutive breaker that
    exits the daemon rc=2 needing an operator on site — the exact
    2026-08-18 lesson, and union_closed g691 landed two of these on
    2026-09-05."""
    did = _theorize(conn, workspace)
    monkeypatch.setattr(agent, "spawn_llm",
                        _dies_with_stderr("theorist", _NET_STDERR))
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "provider_network"


def test_the_reviewers_transport_death_is_read_in_its_own_projection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each review round runs in its own projection dir, so the
    reviewer's stderr is not where the author's is. Reading the author's
    dir for the reviewer's death would charge one seat's failure to the
    other's evidence."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    monkeypatch.setattr(agent, "spawn_llm",
                        _dies_with_stderr("theory_reviewer", _NET_STDERR))
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "provider_network"


def test_a_spawn_that_died_after_writing_is_reviewed_not_thrown_away(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """union_closed g691, 2026-09-05: the rollout shows `write_file`
    landing report.md and the codex stream dying immediately after. The
    document existed; the pipeline threw it away on the rc. An rc says
    the TRANSPORT failed — only the reviewer can say whether the
    document is any good, so the document goes to the reviewer."""
    did = _theorize(conn, workspace)
    fake, state = _dead_spawn("theorist", report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert state["review"] == 1
    row = conn.execute(
        "SELECT path, status FROM theory_documents").fetchone()
    assert row["status"] == "accepted"
    assert (workspace / row["path"]).is_file()


def test_a_revision_that_died_without_rewriting_is_still_a_dead_wake(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Salvage is for work that EXISTS. A revision turn that died before
    touching report.md leaves the PREVIOUS round's document on disk, and
    re-reviewing that spends a reviewer on a turn that never happened —
    and would hand the same document back to the same rubric until the
    rounds ran out."""
    did = _theorize(conn, workspace)
    _spend_infra_budget(conn, did)
    state = {"author": 0, "review": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "theory_reviewer":
            state["review"] += 1
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(_fired("1")), encoding="utf-8")
            return 0
        state["author"] += 1
        if state["author"] == 1:
            (kw["attempts_dir"] / "report.md").write_text(
                _REPORT, encoding="utf-8")
            return 0
        return 1                      # died, and wrote nothing new

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert state["author"] == 2 and state["review"] == 1
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert "did not complete" in d["outcome_detail"]


# ---------------------------------------------------------------------
# an infra death is the framework's, not the request's
# ---------------------------------------------------------------------

def _spend_infra_budget(conn: sqlite3.Connection, did: int) -> None:
    """Charge this request every re-issue the framework owes it, so the
    next infra death is the one that settles."""
    conn.execute(
        "UPDATE strategist_decisions SET infra_deaths = ? WHERE id = ?",
        (theorist.INFRA_REDISPATCHES, did))
    conn.commit()


def test_a_quota_death_leaves_the_request_standing(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """union_closed d5922 / d5933, 2026-09-05 20:32Z: two Theorists died
    on rc=126 and both requests were settled `failed:quota_exhausted`
    saying "the request stands — re-issue it". Nothing re-dispatched
    them; the Strategist had to notice on a later wake and re-file. A
    quota window is the framework's problem, so the row stays UNSETTLED
    and `reconcile_stuck_states` re-queues it once the kind's backoff
    lifts (owner ruling 2026-09-06)."""
    did = _theorize(conn, workspace)
    fake, state = _dead_spawn("theorist", rc=126)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.failure_reason == "quota_exhausted"
    assert state["review"] == 0
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert d["outcome"] is None and d["outcome_detail"] is None


def test_a_request_that_has_spent_its_re_issues_is_settled(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bounded, not forever: a provider broken for good must still reach
    a person. Once the framework has re-issued the request
    `INFRA_REDISPATCHES` times, the next infra death settles it with the
    message it always carried."""
    did = _theorize(conn, workspace)
    _spend_infra_budget(conn, did)
    fake, _ = _dead_spawn("theorist", rc=126)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.failure_reason == "quota_exhausted"
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert str(d["outcome"]) == "failed:quota_exhausted"
    assert "re-issue" in d["outcome_detail"]


def test_a_reviewer_that_dies_on_quota_does_not_cost_the_document(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reviewer's provider says nothing about the document. Its rc
    used to end the wake and throw away an author turn that had already
    written a report; the round re-spawns the reviewer instead, on the
    batch judge's own budget (`adversary.INFRA_SPAWN_RETRIES`)."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    state = {"review": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "theory_reviewer":
            state["review"] += 1
            if state["review"] == 1:
                return 126
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(_clear()), encoding="utf-8")
            return 0
        (kw["attempts_dir"] / "report.md").write_text(
            _REPORT, encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert state["review"] == 2
    assert conn.execute(
        "SELECT status FROM theory_documents").fetchone()[0] == "accepted"


def test_the_reviewers_infra_budget_is_bounded(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A systematically dead reviewer still ends the round — and the
    request it was reviewing for stays standing, because the death is
    still the framework's."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    fake, state = _dead_spawn("theory_reviewer", rc=126, report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.failure_reason == "quota_exhausted"
    assert state["review"] == _review.INFRA_SPAWN_RETRIES + 1
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (did,)).fetchone()[0] is None


# ---------------------------------------------------------------------
# the roads that are not a verdict
# ---------------------------------------------------------------------

def test_an_author_that_writes_nothing_settles_the_request_anyway(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NULL outcome means "the theory layer is still working"
    everywhere in the framework, so a pipeline that returned without
    writing one would suppress its group's stall rescue forever."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()], report=lambda _n: None)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed" and r.failure_reason == "theory_no_report"
    d = conn.execute("SELECT outcome FROM strategist_decisions"
                     " WHERE id = ?", (did,)).fetchone()
    assert d["outcome"] is not None
    assert not db.has_active_inflight_inject(
        conn, "p", group_id=groups_mod.ensure_top_group(conn, "p"))


def test_a_reviewer_that_never_produces_a_verdict_costs_two_tries(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One malformed file must not cost the author's document, and a
    reviewer that produced no usable ruling twice is a pipeline-level
    failure."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[None])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "theory_no_verdict"
    assert state["review"] == _verdict.VERDICT_TRIES
    assert state["author"] == 1


def test_a_refused_verdict_is_kept_beside_the_one_that_replaces_it(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused verdict IS the evidence for its refusal: it moves
    aside, it does not vanish, and the second refusal in one round does
    not overwrite the first."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[{"criteria": {"1": ["clear"]}},
                                {"criteria": {"1": ["clear"]}}])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    proj = workspace / ".attempts" / "th-1" / "review" / "r1"
    kept = sorted(p.name for p in proj.glob("verdict_r1_raw*.json"))
    assert kept == ["verdict_r1_raw.json", "verdict_r1_raw2.json"]
    assert not (proj / "verdict.json").exists()


def test_a_refused_verdict_goes_back_to_the_reviewer_that_wrote_it(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry used to mint a BLIND fresh reviewer: the parser's
    message was printed and nothing else, so the same shape error came
    back for every try (the judge's `479fd579`, one seat over). A
    reviewer cannot fix a refusal it was never shown — resume the SAME
    session, carrying the message and where its file went."""
    did = _theorize(conn, workspace)
    mixed = _clear(**{"1": ["clear: it answers the request",
                            "fired: it does not"]})
    calls: list = []

    def fake_spawn(**kw):
        if kw.get("kind") != "theory_reviewer":
            (kw["attempts_dir"] / "report.md").write_text(
                _REPORT, encoding="utf-8")
            return 0
        calls.append(kw)
        (kw["attempts_dir"] / "verdict.json").write_text(
            json.dumps(mixed if len(calls) == 1 else _clear()),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert len(calls) == 2
    assert calls[1]["session_id"] == calls[0]["session_id"], (
        "the retry must resume the reviewer that wrote the refused file")
    assert calls[1]["is_retry"] is True
    ctx = calls[1]["retry_context"] or ""
    assert 'criterion 1 mixes "clear" and "fired"' in ctx, ctx
    assert "verdict.json" in ctx
    assert "verdict_r1_raw.json" in ctx, (
        "the retry must say where the refused file went")


def test_a_resume_that_dies_on_the_provider_falls_back_to_a_cold_reviewer(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resume is worth having only while the session is. A provider
    death on the retry turn (rc=125: that conversation is gone) means
    there is nothing to go back to, so the next spawn is cold — and the
    round still ends on a ruling rather than costing the document."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    mixed = _clear(**{"1": ["clear: it answers the request",
                            "fired: it does not"]})
    calls: list = []

    def fake_spawn(**kw):
        if kw.get("kind") != "theory_reviewer":
            (kw["attempts_dir"] / "report.md").write_text(
                _REPORT, encoding="utf-8")
            return 0
        calls.append(kw)
        if len(calls) == 2:
            return 125
        (kw["attempts_dir"] / "verdict.json").write_text(
            json.dumps(mixed if len(calls) == 1 else _clear()),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert len(calls) == 3
    assert calls[1]["is_retry"] is True
    assert calls[2]["is_retry"] is False
    assert calls[2]["retry_context"] is None
    assert calls[2]["session_id"] != calls[1]["session_id"]


# ---------------------------------------------------------------------
# the reviewer's dossier
# ---------------------------------------------------------------------

def test_the_projection_carries_the_request_and_declares_its_rubric(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`request.md` is its own file — criterion 1 asks whether the
    document answers THIS request, and a request the author could have
    edited on the way past is not a thing to judge against.
    `_verdict_rubric.json` is what stops `validate_json` telling a
    complete four-criterion verdict it is missing criterion 5."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    proj = workspace / ".attempts" / "th-1" / "review" / "r1"
    req = (proj / "request.md").read_text(encoding="utf-8")
    assert "S such that S implies MAIN" in req
    assert "the bridge died at PAST 3" in req
    rubric = json.loads((proj / "_verdict_rubric.json").read_text(
        encoding="utf-8"))
    assert rubric["criteria_keys"] == list(_verdict.CRITERIA_KEYS)
    assert rubric["multi_clear"] is True
    assert (proj / "report.md").read_text(encoding="utf-8").startswith(
        "# The unit-imbalance erasure")
    assert (proj / "PROGRAMME.md").is_file()
    assert (proj / "TREE.md").is_file()


# ---------------------------------------------------------------------
# `theory_reviewer.dossier` — the package in the prompt (ruling 09-07)
#
# The batch judge's flag, one seat over (`tests/test_adversary.py`, same
# section name). `files` is production and must not move a byte;
# `inline` puts the always-read files IN the prompt, invariant-first so
# one review's rounds share a cacheable prefix, and maps the rest.
# ---------------------------------------------------------------------

_NOTE_AGENT = "g1_20260906-0100_the_wall_is_not_settled_here.md"
_NOTE_USER = "owner_note.md"
_REVIEW_MANIFEST_HEAD = "\n\n## This round's dossier — actually present\n"


def _shelve_notes(workspace: Path) -> Path:
    """The Project's document shelf, with one note in each area — the
    directory whose FILENAMES criterion 1 is decided against."""
    docs = workspace / "Problems" / "p" / "_docs"
    (docs / "agent").mkdir(parents=True, exist_ok=True)
    (docs / "user").mkdir(parents=True, exist_ok=True)
    (docs / "agent" / _NOTE_AGENT).write_text(
        "# The wall\n\nTheorem 1. ...\n", encoding="utf-8")
    (docs / "user" / _NOTE_USER).write_text(
        "# Owner note\n\nTry the erasure.\n", encoding="utf-8")
    return docs


def _dossier_prompt(workspace: Path, conn: sqlite3.Connection,
                    monkeypatch: pytest.MonkeyPatch, *, mode: str,
                   attempts_name: str, report: str = _REPORT,
                   dialogue=(), round_no: int = 1) -> str:
    """One review round under `mode`; returns the prompt file's text.

    The RAW file, not the rendered one — `_rendered_review` below
    applies the pass the provider applies, and the two are different
    questions (what the framework wrote vs what the model reads)."""
    from Tooling.pipeline.theorist import review as _review

    monkeypatch.setenv("ASTERISM_THEORY_REVIEWER_DOSSIER", mode)
    attempts = workspace / ".attempts" / attempts_name
    attempts.mkdir(parents=True)
    seen: dict = {}

    def fake_spawn(**kw):
        seen.update(kw)
        (Path(kw["attempts_dir"]) / "verdict.json").write_text(
            json.dumps(_clear()), encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    verdict, err, rc = _review.review(
        round_no=round_no, attempts_dir=attempts, conn=conn,
        workspace=workspace, problem="p",
        group_id=groups_mod.ensure_top_group(conn, "p"),
        objective="S such that S implies MAIN",
        situation="the bridge died at PAST 3", report_body=report,
        dialogue=list(dialogue), pipeline_id=attempts_name,
        final_round=False)
    assert rc == 0 and verdict is not None, err
    flags = dict(seen["prompt_flags"])
    assert (flags["dossier_inline"], flags["dossier_files"]) == \
        (mode == "inline", mode == "files"), \
        "both names travel, always — the renderer is fail-open"
    return Path(seen["prompt_path"]).read_text(encoding="utf-8")


def _rendered_review(text: str, *, mode: str) -> str:
    """The prompt as the MODEL sees it: the conditional blocks resolved
    the way the provider adapter resolves them."""
    from Tooling.agent import render_prompt_template
    from Tooling.pipeline.theorist.review import round_prompt_flags
    return render_prompt_template(
        text, flags={**round_prompt_flags(False),
                     "dossier_inline": mode == "inline",
                     "dossier_files": mode == "files",
                     "native_file_tools": False, "mcp_only_reads": True})


def test_the_reviewers_files_mode_is_byte_for_byte_the_prompt_of_today(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default mode changes NOTHING. The daemon hot-swaps this code
    within a minute of it being saved, onto a board mid-review, so
    `files` has to be the rubric with the placeholders substituted and
    the per-spawn manifest after it — nothing between, nothing added."""
    from Tooling.pipeline import PROMPT_DIR
    from Tooling.pipeline import adversary as adv

    _shelve_notes(workspace)
    text = _dossier_prompt(workspace, conn, monkeypatch, mode="files",
                           attempts_name="rev-files")
    pdir = workspace / "Problems" / "p"
    head = ((PROMPT_DIR / "theorist" / "review.md")
            .read_text(encoding="utf-8")
            .replace(adv.PROOFS_DIR_PLACEHOLDER,
                     (pdir / "proofs").resolve().as_posix())
            .replace(adv.PAPERS_DIR_PLACEHOLDER,
                     (pdir / "_docs").resolve().as_posix()))
    assert text.startswith(head), "the rubric, verbatim, first"
    assert text[len(head):].startswith(_REVIEW_MANIFEST_HEAD), \
        "and the per-spawn manifest immediately after it"
    # No inlined body rides — this is a directory the reviewer opens, as
    # it always was.
    assert _REPORT not in text
    # …and what the MODEL reads carries neither section nor its wording.
    model_sees = _rendered_review(text, mode="files")
    assert "## Dossier (inline)" not in model_sees
    assert "## Table of contents" not in model_sees
    assert "INLINED VERBATIM" not in model_sees


def test_the_reviewers_inline_dossier_ships_the_document_and_maps_the_rest(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`inline`: charter / request / Programme / the document verbatim
    in the fixed invariant-first order; an outline for TREE.md and the
    dialogue; the way IN (never a map) for CATALOG.md and the proofs
    dir; and the shelf listed BY NAME, since criterion 1 is decided
    against what is already on it."""
    from Tooling.pipeline.theorist import review as _review

    _shelve_notes(workspace)
    text = _dossier_prompt(
        workspace, conn, monkeypatch, mode="inline",
        attempts_name="rev-inline", round_no=2,
        dialogue=[{"round": 1, "criticisms": ["[criterion 1] restated"]}])
    proj = (workspace / ".attempts" / "rev-inline" / "review" / "r2")

    assert "## Dossier (inline)" in text
    # ORDER: every inlined file that exists appears once, in the order
    # the constant declares — the round-invariant prefix depends on it.
    present = [n for n in _review.DOSSIER_INLINE_ORDER
               if (proj / n).is_file()]
    assert "report.md" in present and "charter.md" in present
    at = [text.index(f"### {n}\n") for n in present]
    assert at == sorted(at), f"out of order: {present}"
    # VERBATIM: the body is the file's own bytes, no line numbers.
    for name in present:
        body = (proj / name).read_text(encoding="utf-8").rstrip("\n")
        assert body in text, f"{name} is not inlined verbatim"
    # MAPPED, not inlined: TREE.md and the dialogue get an outline.
    assert "## Table of contents (read on demand)" in text
    for name in _review.DOSSIER_OUTLINED:
        assert (proj / name).is_file(), f"{name} is in every dossier"
        assert f"### {name} — " in text
        assert (proj / name).read_text(encoding="utf-8") not in text, \
            f"{name} is mapped, never inlined"
    # The shelf: names and sizes, never bodies.
    assert _NOTE_AGENT in text and _NOTE_USER in text
    assert "Try the erasure." not in text
    # The proofs dir: entry count and the queries, never a listing.
    assert "### proofs dir" in text
    # The per-spawn block is LAST — everything above it is cacheable.
    assert text.index(_REVIEW_MANIFEST_HEAD) > text.index("## Dossier (inline)")
    assert "### " not in text[text.index(_REVIEW_MANIFEST_HEAD):]
    # And the rubric's own `## What you see` says so.
    assert "INLINED VERBATIM" in _rendered_review(text, mode="inline")


def test_the_reviewers_inline_prefix_is_identical_across_rounds(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two rounds differing ONLY in the document and the dialogue share
    every byte up to `### report.md`.

    That is the whole reason the order is fixed: a provider caches a
    prompt by its prefix, so round 2 must not re-pay for the charter,
    the request and the Programme — and the request in particular is the
    one thing that CANNOT change inside a review."""
    _shelve_notes(workspace)
    a = _dossier_prompt(workspace, conn, monkeypatch, mode="inline",
                        attempts_name="rev-p1", report=_REPORT)
    b = _dossier_prompt(
        workspace, conn, monkeypatch, mode="inline",
        attempts_name="rev-p2", round_no=2,
        report=_REPORT + "\n## Leads\n\nA second route.\n",
        dialogue=[{"round": 1, "criticisms": ["[criterion 1] restated"]}])
    cut = "### report.md"
    assert a != b, "the two rounds really do differ"
    assert a.split(cut)[0] == b.split(cut)[0], \
        "the round-invariant prefix moved between rounds"


def test_the_roster_the_shelf_and_the_proofs_dir_get_the_way_in(
    tmp_path: Path,
) -> None:
    """Three directories-worth of evidence, three different answers.

    CATALOG.md is hundreds of sections: its outline IS a roster, so what
    rides is the way in. `{proofs_dir}` is the same shape — the names
    there are `<slug>.lean` and no ruling turns on which exist. The
    document shelf is the OPPOSITE case: criterion 1 asks whether the
    document has something the notes do not already have, so its
    filenames are evidence and they are listed."""
    from Tooling.pipeline.theorist import review as _review

    proj = tmp_path / "r1"
    proj.mkdir()
    (proj / "CATALOG.md").write_text(
        "".join(f"## uc_lemma_{i}\nstatement {i}\n" for i in range(400)),
        encoding="utf-8")
    (proj / "TREE.md").write_text("# Tree\n## Open\n- a\n", encoding="utf-8")
    (proj / "report.md").write_text("# doc\n\nbody\n", encoding="utf-8")
    proofs = tmp_path / "proofs"
    proofs.mkdir()
    (proofs / "a.lean").write_text("theorem a : True := trivial\n",
                                   encoding="utf-8")
    docs = tmp_path / "_docs"
    (docs / "agent").mkdir(parents=True)
    (docs / "user").mkdir()
    (docs / "agent" / _NOTE_AGENT).write_text("# note\n\nsecret body\n",
                                              encoding="utf-8")
    (docs / "agent" / "papers").mkdir()
    (docs / "user" / _NOTE_USER).write_text("# owner\n", encoding="utf-8")

    text = _review.dossier_sections(proj, proofs_dir=proofs,
                                    papers_dir=docs)

    assert "### CATALOG.md — " in text and "A roster" in text
    assert "## uc_lemma_1\n" not in text, "the roster's own map never rides"
    # The mapped file: the outline `inspect` answers with, verbatim.
    from Tooling.knowledge import workspace_query as _wq
    for line in _wq.outline(proj / "TREE.md"):
        assert line in text
    # The shelf: every note by name and size, the sub-directory by count,
    # and not one byte of a body.
    assert f"`agent/{_NOTE_AGENT}`" in text and f"`user/{_NOTE_USER}`" in text
    assert "`agent/papers/` — 0 entr(ies)" in text
    assert "secret body" not in text
    # The proofs dir: entry count and the queries, never a listing.
    assert f"### proofs dir `{proofs.as_posix()}` — 1 entr(ies)" in text
    assert "a.lean" not in text.split("### proofs dir")[1]


def test_an_unreadable_reviewer_dossier_mode_runs_the_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """A config typo must not discard a finished document. It degrades
    to `files` and says so."""
    from Tooling.pipeline import dossier as _dossier
    from Tooling.pipeline.theorist import review as _review

    monkeypatch.setenv("ASTERISM_THEORY_REVIEWER_DOSSIER", "INLINED")
    assert _review.dossier_mode() == _dossier.FILES
    assert "is not one of" in capsys.readouterr().out


def test_the_author_reads_its_group_under_the_theory_trigger(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Context is the group's own, compiled for `theory`: the
    request leads it, and the Programme is a POINTER — the author reads
    the revision where it bears on the wall rather than paying for all
    of it inline."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    ctx = (workspace / ".attempts" / "th-1" / "Context.md"
           ).read_text(encoding="utf-8")
    assert "`trigger_kind`: theory" in ctx
    assert "### Objective" in ctx and "### Situation" in ctx
    assert "S such that S implies MAIN" in ctx
    assert "## Programme" in ctx
    assert "`PROGRAMME.md` beside this file" in ctx
    assert (workspace / ".attempts" / "th-1" / "PROGRAMME.md").is_file()


# ---------------------------------------------------------------------
# the verdict parser's own contract
# ---------------------------------------------------------------------

def test_several_clears_in_one_criterion_are_legal() -> None:
    """A theory document carries several theorems and several leads, so
    a criterion that asks about them is answered one bullet per item.
    The batch judge's "clear takes exactly one entry" ended BOTH arm5F
    runs as `judge_no_verdict` on verdicts that were entirely clear."""
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"4": ["clear: lead A survived n=4",
                 "clear: lead B survived the construction"]})))
    assert err == "" and v is not None
    assert v["verdict"] == "pass"


def test_a_bare_clear_is_refused_in_every_rendering() -> None:
    """Per BULLET, so a bare one cannot hide behind a reasoned
    neighbour — and an object whose prose is empty is the same bare
    word wearing a different shape."""
    for bad in (["clear"],
                ["clear: good reason", "clear"],
                [{"verdict": "clear"}]):
        v, err = _verdict.parse_theory_verdict(
            json.dumps(_clear(**{"2": bad})))
        assert v is None and "bare" in err, bad


def test_a_criterion_is_one_ruling() -> None:
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"2": ["clear: it holds", "fired: except here"]})))
    assert v is None and "mixes" in err


def test_a_missing_criterion_names_the_one_that_is_missing() -> None:
    body = _clear()
    body["criteria"].pop("3")
    v, err = _verdict.parse_theory_verdict(json.dumps(body))
    assert v is None and "criterion 3" in err
    assert "5" not in err


def test_a_bullet_rendered_as_an_object_is_still_a_bullet() -> None:
    """Refusing this rendering cost arm3h_r2 both of its tries: the
    contract is one bullet per objection, and the bullet's SHAPE is not
    the contract."""
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"1": [{"verdict": "fired", "reason": "already in the notes"}]})))
    assert err == "" and v is not None
    assert v["verdict"] == "rebut"
    assert v["criticisms"] == ["[criterion 1] already in the notes"]


def test_a_nested_bullet_list_is_flattened() -> None:
    """The other reasonable reading of "a list per criterion, one bullet
    per objection": the bullets arrive one level deeper. Same contract,
    same ruling — `_bullets` flattens one level and this pins that it
    still does. (Ported from the retired `Tooling/experiments/` suite,
    which was the only place it was checked.)"""
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"3": [["fired: the n=6 census could not be reproduced"]]})))
    assert err == "" and v is not None
    assert v["criticisms"] == [
        "[criterion 3] the n=6 census could not be reproduced"]


def test_a_refused_verdicts_log_line_names_the_offending_shape() -> None:
    """A rejection has to be diagnosable from the run log without
    opening the rollout: the line says the type and the shape the
    reviewer actually wrote, per criterion. Unparseable bytes describe
    themselves rather than throwing."""
    line = _verdict.describe_verdict_shape(json.dumps({"criteria": {
        "1": ["clear: on no record"],
        "3": [{"goal_id": 10670, "verdict": "fired", "reason": "x"}]},
        "reservations": []}))
    assert '"1"' in line and "list[str]" in line
    assert '"3"' in line and "list[dict" in line
    assert "goal_id" in line and "verdict" in line and "reason" in line
    assert "not JSON" in _verdict.describe_verdict_shape("{oops")


# ---------------------------------------------------------------------
# the surfaces that read a decision, a pipeline or a table
# ---------------------------------------------------------------------

def _batch_section(conn, workspace, attempts):
    from Tooling.agent import phase2_context
    return phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts)


def _open_theorize(conn, workspace):
    """One open Theorize plus the pipeline row its dispatch would make."""
    did = _theorize(conn, workspace)
    db.record_pipeline_start(
        conn, pipeline_id="pid-th", kind="Theorist",
        target_id=str(groups_mod.ensure_top_group(conn, "p")),
        target_kind="Group")
    return did


def test_the_status_surfaces_read_a_theory_run_without_crashing(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A new pipeline kind and a new decision kind reach every reader of
    those tables. None of them may die on it — a status command that
    raises is the operator's only window going dark at exactly the
    moment something new is running."""
    from Tooling.core.cli import diagnose, run as _run
    db.insert_goal(conn, problem="p", slug="main",
                   lean_path="Problems/p/Root.lean", statement="T",
                   origin="root", depth=0)
    _open_theorize(conn, workspace)
    payload = diagnose._status_payload(conn, "p")
    assert payload["exists"] is True
    # `daemon status` counts running pipelines; the Theorist is one.
    running, _leases = _run._daemon_counts(workspace)
    assert running >= 1
    status = _run.daemon_status(workspace)
    assert status["in_flight"] >= 1


def test_the_tree_render_is_unmoved_by_a_theory_run(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Theorize produces no goal, so TREE has nothing new to say — and
    saying nothing is the correct answer, not an omission: the document
    is listed under `## Notes on this problem`, which is where a reader
    looking for prose goes."""
    from Tooling.state import tree as _tree
    # The render's header carries a UTC stamp to the SECOND, so two
    # renders taken across a tick differ on the clock alone (full-suite
    # red, 2026-09-06). Freeze it: the claim is about the body.
    monkeypatch.setattr(_tree, "_stamp", lambda: "2026-09-06T00:00:00Z")
    db.insert_goal(conn, problem="p", slug="main",
                   lean_path="Problems/p/Root.lean", statement="T",
                   origin="root", depth=0)
    before = _tree.render(conn, "p")
    _open_theorize(conn, workspace)
    assert _tree.render(conn, "p") == before


def test_the_batch_surfaces_name_the_open_theory_request(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, tmp_path: Path,
) -> None:
    """An open step with no product renders as running — correct, since
    a theory request has no parked state — and the companion carries the
    request itself, because a Theorize has no `brief` column and a step
    shown with "(no brief)" reads as a step about nothing."""
    from Tooling.agent import phase2_context
    _theorize(conn, workspace)
    attempts = tmp_path / "_ctx"
    attempts.mkdir()
    lines = phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts)
    text = "\n".join(lines)
    assert "Dispatched, still running" in text
    companion = (attempts / "BATCHES.md").read_text(encoding="utf-8")
    assert "Theorize — a question for the theory layer" in companion
    assert "**objective** — S such that S implies MAIN" in companion
    assert "**situation** — the bridge died at PAST 3" in companion


def test_a_finished_theory_request_reaches_the_completed_batches(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`## Completed Inject batches` is where a wake reads what its last
    batch left. An accepted document must arrive there by its PATH — the
    thing the next wake opens — and a refused one by its reason."""
    from Tooling.agent import phase2_context
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    attempts = tmp_path / "_ctx2"
    attempts.mkdir()
    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts))
    assert "Completed Inject batches" in text
    assert "THEORY request — objective: S such that S implies MAIN" in text
    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    assert f"document: `{path}`" in text


def test_a_refused_theory_request_says_so_on_the_scoreboard(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_fired("1")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    attempts = tmp_path / "_ctx3"
    attempts.mkdir()
    text = "\n".join(_batch_section(conn, workspace, attempts))
    assert theorist.REJECTED_DETAIL in text
    assert "the relation is not argued" in text


def test_carry_places_the_new_table(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """`asterism carry` refuses to run on a table it cannot place, and
    the placement is DERIVED — `theory_documents` carries a `problem`
    column, so it is problem-keyed with nothing to declare by hand."""
    from Tooling.state import carry as _carry
    kinds = _carry.assert_classified(conn)
    assert kinds["theory_documents"] == _carry.PROBLEM_KEYED


# ---------------------------------------------------------------------
# the checkpoint, and resuming from it
#
# 2026-09-06, union_closed g694: a Theorist wrote a 228k-token document,
# its reviewer died on the five-hour quota, and the (correct) infra
# re-dispatch started a FRESH author that rewrote the whole thing from
# scratch. The author's work was thrown away by a REVIEWER's transport
# death. `_theorize.json` is the resume point that makes that
# impossible: it names the phase the run is in, and a re-dispatch picks
# the run up there instead of at the beginning.
# ---------------------------------------------------------------------

def _phases(monkeypatch: pytest.MonkeyPatch) -> "list[tuple[str, int]]":
    """Record every phase the run checkpoints, in order. The phase
    SEQUENCE is the contract — `awaiting_revision` in particular is
    overwritten by the next round's `authoring` within milliseconds, so
    nothing left on disk afterwards can witness that it was written."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    seen: "list[tuple[str, int]]" = []
    real = _ck.write

    def spy(attempts_dir, **kw):
        seen.append((str(kw["phase"]), int(kw["round_no"])))
        return real(attempts_dir, **kw)

    monkeypatch.setattr(_ck, "write", spy)
    return seen


def _frozen(workspace: Path, pipeline_id: str, *, decision_id: int,
            group_id: int, phase: str, round_no: int,
            author_sid: str = "sid-old", verdicts=(),
            report: str = _REPORT, reviewed_sha: str = "") -> Path:
    """A frozen attempts dir in the shape `.asterism/theory_frozen/`
    holds: the document, the rounds already argued, the checkpoint."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    d = workspace / ".asterism" / "theory_frozen" / pipeline_id
    (d / "review").mkdir(parents=True, exist_ok=True)
    (d / "report.md").write_text(report, encoding="utf-8")
    for i, v in enumerate(verdicts, start=1):
        r = d / "review" / f"r{i}"
        r.mkdir(parents=True, exist_ok=True)
        (r / "report.md").write_text(report, encoding="utf-8")
        if v is not None:
            (r / "verdict.json").write_text(json.dumps(v), encoding="utf-8")
    _ck.write(d, decision_id=decision_id, group_id=group_id, problem="p",
              author_sid=author_sid, provider="claude", model="m",
              phase=phase, round_no=round_no, started_at="t0",
              reviewed_sha=reviewed_sha)
    return d


def _seats(fake):
    """Wrap a scripted spawn so the SEAT ORDER is observable — which
    kind runs first is the whole question a resume answers."""
    seen: "list[dict]" = []

    def spy(**kw):
        seen.append(dict(kw))
        return fake(**kw)

    return spy, seen


def test_the_checkpoint_names_every_phase_the_run_passes_through(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One rebutted round, then a clear one. Every state change is
    written down: the two author turns, the two reviews, the revision
    the fired verdict bought, and the landing."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    did = _theorize(conn, workspace)
    seen = _phases(monkeypatch)
    fake, _ = _script(verdicts=[_fired("1"), _clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert seen == [
        (_ck.PHASE_AUTHORING, 1),
        (_ck.PHASE_AWAITING_REVIEW, 1),
        (_ck.PHASE_AWAITING_REVISION, 1),
        (_ck.PHASE_AUTHORING, 2),
        (_ck.PHASE_AWAITING_REVIEW, 2),
        (_ck.PHASE_LANDING, 2),
    ]


def test_the_checkpoint_carries_what_a_resume_needs_to_find_the_author(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request it answers, the wall it is on, and the SESSION the
    author is thinking in — a resume that cannot name the session can
    only start a new one."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    data = _ck.load(workspace / ".attempts" / "th-1")
    assert data is not None
    assert data["decision_id"] == did
    assert data["group_id"] == gid
    assert data["problem"] == "p"
    assert data["author_sid"] == state["author_sids"][0]
    assert data["provider"] == "claude"
    assert "model" in data
    assert data["started_at"] and data["updated_at"]


def test_a_dead_reviewer_leaves_the_checkpoint_awaiting_its_review(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The incident, in one assertion. The reviewer's quota death is
    non-terminal (`b4622245`) — the decision stays NULL and the request
    is re-queued — and what the re-dispatch must find is a checkpoint
    saying the DOCUMENT IS WRITTEN, not one telling it to write
    another."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import checkpoint as _ck
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    fake, _ = _dead_spawn("theory_reviewer", rc=126, report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.failure_reason == "quota_exhausted"
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (did,)).fetchone()[0] is None
    data = _ck.load(workspace / ".attempts" / "th-1")
    assert data is not None
    assert (data["phase"], data["round"]) == (_ck.PHASE_AWAITING_REVIEW, 1)


def test_the_redispatch_after_a_dead_reviewer_spawns_a_reviewer_first(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And therefore: the next `run_theorist` for that decision does NOT
    author. It reviews what is already written — the 223k tokens the
    incident spent re-writing are the cost of getting this wrong."""
    from Tooling.core import quota_wait as _qw
    from Tooling.pipeline.theorist import review as _review
    monkeypatch.setattr(_review, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(_qw, "park_in_pipeline", lambda *a, **k: False)
    did = _theorize(conn, workspace)
    dead, _ = _dead_spawn("theory_reviewer", rc=126, report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", dead)
    _run(conn, workspace, pintent, did, pipeline_id="th-1")

    fake, _ = _script(verdicts=[_clear()])
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    r = _run(conn, workspace, pintent, did, pipeline_id="th-2")

    assert r.outcome == "success", r.failure_detail
    assert [k["kind"] for k in seen] == ["theory_reviewer"]
    # and it reviewed the document the FIRST run's author wrote
    assert (workspace / ".attempts" / "th-2" / "report.md").read_text(
        encoding="utf-8").strip() == _REPORT.strip()
    row = conn.execute(
        "SELECT rounds, pipeline_id FROM theory_documents").fetchone()
    assert row["rounds"] == 1 and row["pipeline_id"] == "th-2"
    landed = (workspace / conn.execute(
        "SELECT path FROM theory_documents").fetchone()[0]).read_text(
            encoding="utf-8")
    assert "resumed from: th-1" in landed


def test_a_rebutted_round_resumes_the_authors_own_session(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`awaiting_revision`: the reviewer ruled, the author had not
    answered yet. The resumed run takes the author's revision turn on
    the SAME session, with the fired bullets as its retry context."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    _frozen(workspace, "old-1", decision_id=did, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVISION, round_no=1,
            author_sid="sid-old",
            verdicts=[_fired("3", "the wall is only named")])

    fake, _ = _script(verdicts=[_clear()])
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    r = _run(conn, workspace, pintent, did, pipeline_id="th-9")

    assert r.outcome == "success", r.failure_detail
    assert [k["kind"] for k in seen] == ["theorist", "theory_reviewer"]
    author = seen[0]
    assert author["session_id"] == "sid-old"
    assert author["is_retry"] is True
    assert "the wall is only named" in (author["retry_context"] or "")
    # the old run's files are the new run's files
    att = workspace / ".attempts" / "th-9"
    assert (att / "review" / "r1" / "verdict.json").is_file()
    assert _ck.load(att)["resumed_from"] == "old-1"
    # round 1 is spent: this is round 2, and its dialogue carries r1
    assert (att / "review" / "r2" / "dialogue.md").is_file()
    assert conn.execute(
        "SELECT rounds FROM theory_documents").fetchone()[0] == 2


def test_an_unresumable_author_session_falls_back_to_a_fresh_one(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session id the provider can no longer replay (rc=125) must not
    end the run — the document and the ruling are both on disk, so a
    fresh author can be handed them in its PROMPT instead."""
    from Tooling.llm.base import SpawnRC
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    _frozen(workspace, "old-2", decision_id=did, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVISION, round_no=1,
            author_sid="sid-gone",
            verdicts=[_fired("3", "the wall is only named")])

    fake, _ = _script(verdicts=[_clear()])
    calls = {"n": 0}

    def flaky(**kw):
        if kw.get("kind") == "theorist":
            calls["n"] += 1
            if calls["n"] == 1:
                return int(SpawnRC.STALE_SESSION)
        return fake(**kw)

    spy, seen = _seats(flaky)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    r = _run(conn, workspace, pintent, did, pipeline_id="th-10")

    assert r.outcome == "success", r.failure_detail
    assert [k["kind"] for k in seen] == [
        "theorist", "theorist", "theory_reviewer"]
    assert seen[1]["session_id"] not in ("sid-gone", seen[0]["session_id"])
    assert seen[1]["is_retry"] is False
    # the fresh author is handed the run in its prompt, not in a session
    brief = Path(seen[1]["prompt_path"]).read_text(encoding="utf-8")
    assert "report.md" in brief and "the wall is only named" in brief


def test_an_interrupted_authoring_turn_counts_as_a_submission(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prompt tells the author to update `report.md` as it thinks,
    so a draft caught mid-turn IS the submission — the resume reviews it
    rather than asking for it again."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    _frozen(workspace, "old-3", decision_id=did, group_id=gid,
            phase=_ck.PHASE_AUTHORING, round_no=1)

    fake, _ = _script(verdicts=[_clear()])
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    r = _run(conn, workspace, pintent, did, pipeline_id="th-11")
    assert r.outcome == "success", r.failure_detail
    assert [k["kind"] for k in seen] == ["theory_reviewer"]


def test_an_interrupted_revision_that_wrote_nothing_new_resumes_the_author(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The other half of that rule. At round k+1 the stored phase is
    `authoring` from the moment the spawn is launched, and `report.md`
    still holds the document round k was JUDGED on — re-reviewing that
    spends a reviewer on a turn that never happened. The checkpoint
    carries the digest of what was already reviewed, so the two cases
    are told apart."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    d = _frozen(workspace, "old-4", decision_id=1, group_id=gid,
                phase=_ck.PHASE_AUTHORING, round_no=2,
                reviewed_sha=_ck.digest(_REPORT),
                verdicts=[_fired("1")])
    assert _ck.resolve(d, _ck.load(d)) == (_ck.PHASE_AWAITING_REVISION, 1)

    # a draft that IS new goes to review as round 2
    (d / "report.md").write_text(_REPORT + "\n## More\n", encoding="utf-8")
    assert _ck.resolve(d, _ck.load(d)) == (_ck.PHASE_AWAITING_REVIEW, 2)


def test_a_verdict_on_disk_outranks_the_phase_field(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The checkpoint is written BEFORE the spawn it describes, so its
    phase can be one state stale. The round's `verdict.json` is the
    structural signal: it exists iff the reviewer ruled."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    d = _frozen(workspace, "old-5", decision_id=1, group_id=gid,
                phase=_ck.PHASE_AWAITING_REVIEW, round_no=1,
                verdicts=[_clear()])
    assert _ck.resolve(d, _ck.load(d)) == (_ck.PHASE_LANDING, 1)

    d2 = _frozen(workspace, "old-6", decision_id=1, group_id=gid,
                 phase=_ck.PHASE_AWAITING_REVIEW, round_no=1,
                 verdicts=[_fired("1")])
    assert _ck.resolve(d2, _ck.load(d2)) == (_ck.PHASE_AWAITING_REVISION, 1)


def test_a_landing_phase_lands_without_spawning_anything(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reviewer passed it and the process died before the write.
    There is nothing left to ask anyone."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    _frozen(workspace, "old-7", decision_id=did, group_id=gid,
            phase=_ck.PHASE_LANDING, round_no=1, verdicts=[_clear()])

    fake, _ = _script(verdicts=[_clear()])
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    r = _run(conn, workspace, pintent, did, pipeline_id="th-12")
    assert r.outcome == "success", r.failure_detail
    assert seen == []
    assert conn.execute(
        "SELECT status FROM theory_documents").fetchone()[0] == "accepted"


def test_the_round_cap_counts_the_rounds_already_taken(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three revisions is the budget for the REQUEST, not for each
    process that answers it. A run resumed at round 3 has one author
    turn left, not four."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    _frozen(workspace, "old-8", decision_id=did, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVIEW, round_no=3,
            verdicts=[_fired("1"), _fired("1"), None])

    fake, _ = _script(verdicts=[_fired("1")] * 4)
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    _run(conn, workspace, pintent, did, pipeline_id="th-13")

    assert [k["kind"] for k in seen] == [
        "theory_reviewer", "theorist", "theory_reviewer"]
    row = conn.execute(
        "SELECT rounds, status FROM theory_documents").fetchone()
    assert row["rounds"] == 4 and row["status"] == "rejected"


def test_the_newest_checkpoint_for_the_decision_wins(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request can have been answered more than once. The resume takes
    the run that got FURTHEST — the newest checkpoint — and never a
    different decision's."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    other = _theorize(conn, workspace)
    old = _frozen(workspace, "old-9", decision_id=did, group_id=gid,
                  phase=_ck.PHASE_AUTHORING, round_no=1, report="stale\n")
    _ck.write(old, decision_id=did, group_id=gid, problem="p",
              author_sid="a", provider="claude", model="m",
              phase=_ck.PHASE_AUTHORING, round_no=1, started_at="t0",
              updated_at="2020-01-01T00:00:00Z")
    new = _frozen(workspace, "old-10", decision_id=did, group_id=gid,
                  phase=_ck.PHASE_AWAITING_REVIEW, round_no=1)
    _ck.write(new, decision_id=did, group_id=gid, problem="p",
              author_sid="b", provider="claude", model="m",
              phase=_ck.PHASE_AWAITING_REVIEW, round_no=1,
              started_at="t0", updated_at="2030-01-01T00:00:00Z")
    _frozen(workspace, "old-11", decision_id=other, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVIEW, round_no=1, report="wrong\n")

    fake, _ = _script(verdicts=[_clear()])
    spy, seen = _seats(fake)
    monkeypatch.setattr(agent, "spawn_llm", spy)
    _run(conn, workspace, pintent, did, pipeline_id="th-14")
    assert [k["kind"] for k in seen] == ["theory_reviewer"]
    assert _ck.load(workspace / ".attempts" / "th-14")[
        "resumed_from"] == "old-10"


def test_the_attempts_dir_of_an_unanswered_request_survives_its_work_area(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """`WorkArea.__exit__` rmtrees the attempts dir unconditionally —
    which is exactly what deletes the frozen document between the infra
    death and the re-dispatch that is supposed to resume it."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    conn.close()

    for pid, settle in (("keep-me", False), ("drop-me", True)):
        with agent.WorkArea(workspace, pid) as wa:
            _ck.write(wa.attempts, decision_id=did, group_id=gid,
                      problem="p", author_sid="s", provider="claude",
                      model="m", phase=_ck.PHASE_AWAITING_REVIEW,
                      round_no=1, started_at="t0")
            (wa.attempts / "report.md").write_text("doc\n", encoding="utf-8")
            if settle:
                c = db.connect()
                c.execute("UPDATE strategist_decisions SET outcome ="
                          " 'success' WHERE id = ?", (did,))
                c.commit()
                c.close()
    assert (workspace / ".attempts" / "keep-me" / "report.md").is_file()
    assert not (workspace / ".attempts" / "drop-me").exists()


def test_the_checkpoint_basename_is_spelled_in_one_place() -> None:
    """`WorkArea` cannot import the theory package at module level (the
    pipeline package imports `agent`), so it carries the name inline.
    A second spelling is a sweep that stops sparing the dirs."""
    from Tooling.agent import runtime as _runtime
    from Tooling.pipeline.theorist import checkpoint as _ck
    assert _runtime.THEORIZE_CHECKPOINT == _ck.CHECKPOINT_BASENAME


# ---------------------------------------------------------------------
# stamping the two runs frozen by hand on 2026-09-06
# ---------------------------------------------------------------------

def test_theorize_freeze_adopt_stamps_a_frozen_dir(
    workspace: Path, conn: sqlite3.Connection, capsys,
) -> None:
    """`asterism theorize-freeze-adopt <pipeline_id> --decision <id>`:
    the owner's road back for the two runs frozen by hand. It writes
    `_theorize.json` into an existing dir and NOTHING else — the phase
    and the round are READ OFF the dir, so a mistyped one cannot invent
    a state the files do not have."""
    import argparse
    from Tooling.core.cli import maint
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    conn.close()

    d = workspace / ".asterism" / "theory_frozen" / "07cb21a7"
    (d / "review").mkdir(parents=True)
    (d / "report.md").write_text(_REPORT, encoding="utf-8")
    for i in (1, 2, 3):
        r = d / "review" / f"r{i}"
        r.mkdir(parents=True)
        (r / "report.md").write_text(_REPORT, encoding="utf-8")
        if i < 3:
            (r / "verdict.json").write_text(
                json.dumps(_fired("1")), encoding="utf-8")
    (d / "_spawn.stderr").write_text(
        'rc=1\n--- stdout ---\n{"type":"system","subtype":"init",'
        '"session_id":"0c8b82fd-b296-4c32-adde-a7a226ec5451"}\n',
        encoding="utf-8")

    rc = maint.cmd_theorize_freeze_adopt(argparse.Namespace(
        pipeline_id="07cb21a7", decision=did, author_sid=None))
    assert rc == 0
    data = _ck.load(d)
    assert data["decision_id"] == did
    assert data["group_id"] == gid
    assert data["problem"] == "p"
    assert (data["phase"], data["round"]) == (_ck.PHASE_AWAITING_REVIEW, 3)
    assert data["author_sid"] == "0c8b82fd-b296-4c32-adde-a7a226ec5451"
    out = capsys.readouterr().out
    assert "awaiting_review" in out and "round 3" in out


def test_theorize_freeze_adopt_refuses_a_decision_that_is_settled(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Stamping a settled request would resurrect a wall the Strategist
    has already been answered on."""
    import argparse
    from Tooling.core.cli import maint
    from Tooling.pipeline.theorist import checkpoint as _ck
    did = _theorize(conn, workspace)
    conn.execute("UPDATE strategist_decisions SET outcome = 'success'"
                 " WHERE id = ?", (did,))
    conn.commit()
    conn.close()
    d = workspace / ".asterism" / "theory_frozen" / "zz"
    d.mkdir(parents=True)
    (d / "report.md").write_text(_REPORT, encoding="utf-8")

    rc = maint.cmd_theorize_freeze_adopt(argparse.Namespace(
        pipeline_id="zz", decision=did, author_sid=None))
    assert rc == 1
    assert _ck.load(d) is None


# ---------------------------------------------------------------------
# criterion 3's two push halves, and where the FINAL round's line goes
#
# Owner ruling 2026-09-07: `prompts/theorist/review.md` splits criterion
# 3. The defect half always applies; the PUSH half is one of two blocks
# — "fire and require the next step" while a revision is still owed, and
# "write it into `reservations`" on the last round, because no author
# turn follows to answer it. `render_prompt_template` is FAIL-OPEN, so
# the framework must always pass exactly one of the two names, and the
# reservations it produces have to reach a reader.
# ---------------------------------------------------------------------

def _review_prompt() -> str:
    from Tooling.pipeline import PROMPT_DIR
    return (PROMPT_DIR / "theorist" / "review.md").read_text(
        encoding="utf-8")


#: A sentence from each half, distinctive enough to tell them apart.
_MORE_ROUNDS_MARK = "require the next step"
_FINAL_ROUND_MARK = "No revision follows this round"


def test_each_flag_renders_exactly_one_of_criterion_3s_push_halves() -> None:
    """The renderer keeps a block whose flag it was never given, so the
    two names are only exclusive if BOTH are always passed. Rendered
    with neither — the shape a caller that forgot would produce — the
    reviewer reads two contradictory instructions at once."""
    from Tooling.agent.runtime import render_prompt_template
    from Tooling.pipeline.theorist.review import round_prompt_flags

    src = _review_prompt()
    assert _MORE_ROUNDS_MARK in src and _FINAL_ROUND_MARK in src

    mid = render_prompt_template(src, flags=round_prompt_flags(False))
    assert _MORE_ROUNDS_MARK in mid and _FINAL_ROUND_MARK not in mid

    last = render_prompt_template(src, flags=round_prompt_flags(True))
    assert _FINAL_ROUND_MARK in last and _MORE_ROUNDS_MARK not in last

    # The defect half is not conditional — it rules on every round.
    for text in (mid, last):
        assert "Attempts that are only announced are not allowed" in text

    both = render_prompt_template(src, flags=None)
    assert _MORE_ROUNDS_MARK in both and _FINAL_ROUND_MARK in both


def test_only_the_last_review_is_told_that_no_revision_follows(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four rounds argued out (`DEFAULT_ROUNDS` revisions plus the cold
    one). A revision is owed after every round but the last, so exactly
    the last reviewer is shown the `final_round` half."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("3")] * 9)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    assert state["review"] == theorist.DEFAULT_ROUNDS + 1
    assert [f["final_round"] for f in state["review_flags"]] == \
        [False, False, False, True]
    # Both names on every round: the renderer is fail-open, so a round
    # that named only the true one would render the other block too.
    for flags in state["review_flags"]:
        assert flags["more_rounds"] is not flags["final_round"]


def test_a_single_round_cap_makes_the_first_review_the_final_one(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap is the REQUEST's. With no revision on offer the opening
    round is already the last, and telling its reviewer to require a
    next step would be requiring one of nobody."""
    monkeypatch.setenv("ASTERISM_THEORIST_ROUNDS", "0")
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("3")])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    assert state["review"] == 1
    # Criterion 3's pair only — the dossier pair rides in the same dict
    # (`theory_reviewer.dossier`) and is a different question.
    flags = state["review_flags"][0]
    assert (flags["more_rounds"], flags["final_round"]) == (False, True)


def test_a_resumed_round_is_told_what_the_cold_path_would_have_said(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both resume roads enter the loop mid-way, and the flag is derived
    from the loop variable rather than from the turn — so `awaiting_
    review` at round 3 (which owes one more revision) and `awaiting_
    revision` at round 3 (whose next round is the fourth and last) each
    compute exactly what an uninterrupted run would have."""
    from Tooling.pipeline.theorist import checkpoint as _ck
    gid = groups_mod.ensure_top_group(conn, "p")

    did = _theorize(conn, workspace)
    _frozen(workspace, "old-fr1", decision_id=did, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVIEW, round_no=3,
            verdicts=[_fired("3"), _fired("3")])
    fake, state = _script(verdicts=[_fired("3")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did, pipeline_id="th-fr1")
    # round 3 (a revision still owed), then round 4 (the last)
    assert [f["final_round"] for f in state["review_flags"]] == [False, True]

    did2 = _theorize(conn, workspace)
    _frozen(workspace, "old-fr2", decision_id=did2, group_id=gid,
            phase=_ck.PHASE_AWAITING_REVISION, round_no=3,
            verdicts=[_fired("3")] * 3)
    fake2, state2 = _script(verdicts=[_fired("3")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake2)
    _run(conn, workspace, pintent, did2, pipeline_id="th-fr2")
    # the author takes round 3's revision; round 4 is the last review
    assert [f["final_round"] for f in state2["review_flags"]] == [True]


# ---------------------------------------------------------------------
# and the reservations have to reach somebody
# ---------------------------------------------------------------------

_RESERVATION = ("push past the toggle-1 involution: the same argument on "
                "any odd element generalises the count to every finite A "
                "with an odd member — that is the next step")


def _clear_with_reservations(*reservations):
    v = _clear()
    v["reservations"] = list(reservations)
    return v


def test_the_landed_header_carries_the_reservations_verbatim(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The attempts dir the ruling was written in is deleted at pipeline
    end, so an accepted document's reservations survive only here. They
    sit AFTER the criteria lines, one line each, uncut — on the final
    round this is where criterion 3's push half writes the line past the
    author's stop."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear_with_reservations(
        _RESERVATION, "the n = 0 edge case is not stated")])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail

    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    text = (workspace / path).read_text(encoding="utf-8")
    head = text.split("-->", 1)[0].splitlines()
    assert f"reservations: {_RESERVATION}" in head
    assert "reservations: the n = 0 edge case is not stated" in head
    # after the criteria, and inside the comment
    assert head.index(f"reservations: {_RESERVATION}") > max(
        i for i, ln in enumerate(head) if ln.startswith("criterion "))


def test_a_ruling_with_no_reservations_writes_no_line_about_it(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The absence of the line is what says nothing was left over — an
    empty `reservations:` would be one more line to read rather than one
    to find, the same rule the rigour flag follows."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    assert "reservations:" not in (workspace / path).read_text(
        encoding="utf-8")


def test_a_refused_document_still_carries_its_fired_lines(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal's own header is unchanged by the new line: status,
    the criteria that fired, every bullet — and the reservations below
    them when the ruling carried any."""
    did = _theorize(conn, workspace)
    ruling = _fired("1")
    ruling["reservations"] = [_RESERVATION]
    fake, _ = _script(verdicts=[ruling] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"

    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    text = (workspace / path).read_text(encoding="utf-8")
    assert text.startswith("<!--\nstatus: rejected\n")
    assert "criteria fired: 1" in text
    assert "criterion 1: fired: the relation is not argued" in text
    assert f"reservations: {_RESERVATION}" in text


def test_a_header_line_cannot_end_the_comment_it_lives_in() -> None:
    """Every line below `status:` is the reviewer's own text, which no
    parser constrains — a `-->` inside one would close the comment early
    and spill the framework's bookkeeping into the document's prose."""
    head = landing.header(
        group_id=1, pipeline_id="p", rounds=1,
        verdict_lines=["criterion 1: clear: it holds --> see below"],
        reservations=["reservations: push on --> the odd element"])
    assert head.count("-->") == 1
    assert head.endswith("-->")


def test_an_accepted_theory_return_shows_its_reservations_to_the_wake(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`## Completed Inject batches` is the surface a wake reads its last
    batch from. An accepted document's reservations fired no criterion,
    so they are in neither `criticisms` nor a refusal detail — without
    this the final round's line past the author's stop would reach
    nobody. The PATH stays the first line, and the advice is not cut."""
    from Tooling.agent import phase2_context
    long_one = (_RESERVATION + " " + "and here is the reason " * 80).strip()
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear_with_reservations(long_one)])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    attempts = tmp_path / "_ctx_res"
    attempts.mkdir()
    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts))
    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    assert f"document: `{path}`" in text
    assert theorist.RESERVATIONS_HEADING in text
    assert long_one in text          # bearing content is never capped


def test_the_notes_roster_says_an_accepted_document_left_reservations(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outcome above lives as long as the batch is on the
    scoreboard; the roster lists the document for good. It carries the
    COUNT and points at the header — the text itself is in the file the
    reader is being sent to."""
    from Tooling.agent import context as _context
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear_with_reservations(_RESERVATION)])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    text = "\n".join(_context._section_owner_notes(pintent, workspace, conn))
    assert "1 reservation(s) — in its header" in text
